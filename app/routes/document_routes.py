import os
from pathlib import Path as PathlibPath
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import logging
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from app.schemas.duckdb import get_duckdb_conn
from app.schemas.sqlitedb import get_sqlite_conn
from app.utils.rag_module import index_unembedded_document
from app.utils.audit_context import AuditContext, get_audit_context

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = "static/uploads/"


def check_c_level_access(
    audit: AuditContext,
    *,
    action: str = "document.upload",
    resource: str = "document.upload",
    detail: str = "Only C-Level can perform this action.",
    query_mode: str = "administration",
) -> None:
    """Authorize a C-Level action and audit denied requests."""
    if str(audit.role).casefold() != "c-level":
        audit.emit(
            action=action,
            resource=resource,
            authorization_decision="denied",
            result="failure",
            outcome_status="denied",
            query_mode=query_mode,
        )
        raise HTTPException(status_code=403, detail=detail)


def _get_embedding_status_payload() -> dict:
    """Return embedding status without exposing filesystem paths."""
    sqlite_conn = get_sqlite_conn()
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute("""
        SELECT filename, embedded, role FROM documents
        ORDER BY embedded DESC, filename ASC
    """)

    docs = sqlite_cur.fetchall()
    embedded = [{"filename": d[0], "role": d[2]} for d in docs if d[1] == 1]
    unembedded = [{"filename": d[0], "role": d[2]} for d in docs if d[1] == 0]

    return {
        "total": len(docs),
        "embedded_count": len(embedded),
        "unembedded_count": len(unembedded),
        "embedded_docs": embedded,
        "unembedded_docs": unembedded,
    }


async def _retry_unembedded_documents() -> dict:
    """Retry indexing and return the current aggregate embedding counts."""
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as executor:
        await loop.run_in_executor(executor, index_unembedded_document)

    status = _get_embedding_status_payload()
    return {
        "embedded_count": status["embedded_count"],
        "unembedded_count": status["unembedded_count"],
    }


@router.post("/upload-docs")
async def upload_docs(
    file: UploadFile = File(...),
    role: str = Form(...),
    audit: AuditContext = Depends(get_audit_context),
):
    username = audit.username
    role = audit.role

    try: 
        if not username:
            audit.emit(
                action="document.upload",
                resource="document.upload",
                authorization_decision="denied",
                result="failure",
                outcome_status="denied",
                query_mode="document",
            )
            raise HTTPException(status_code=401, detail="Authentication required.")

        check_c_level_access(audit)

        sqlite_conn = get_sqlite_conn()
        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("SELECT 1 FROM roles WHERE role_name = ?", (role,))
        if not sqlite_cur.fetchone():
            audit.emit(
                action="document.upload",
                resource=f"document.upload:{role}",
                authorization_decision="denied",
                result="failure",
                outcome_status="denied",
                query_mode="document",
            )
            raise HTTPException(status_code=400, detail="Invalid role specified.")

        # extract the file details
        filename = file.filename
        extension = filename.split(".")[-1].lower()
        # extension = Path(filename).suffix.lower()

        # save the file to the appropriate directory based on the role
        role_dir = os.path.join(UPLOAD_DIR, role)
        os.makedirs(role_dir, exist_ok=True)
        
        # Use ABSOLUTE path to avoid working directory issues
        filepath = os.path.abspath(os.path.join(role_dir, filename))
        logger.info(f"[UPLOAD] Absolute filepath: {filepath}")

        # read the file content and save it to the specified path for future indexing
        data = await file.read()

        with open(filepath, "wb") as f:
            f.write(data)
        
        # Ensure file is flushed to disk
        if os.path.exists(filepath):
            logger.info(f"[UPLOAD] File verified on disk: {filepath}")
        else:
            raise HTTPException(status_code=500, detail=f"File write verification failed: {filepath}")
        
        # convert to string content for validation
        
        if extension == "csv":
            from io import BytesIO
            df = pd.read_csv(BytesIO(data))
            content = df.to_string(index=False)

            #load from DuckDB
            file_df = pd.read_csv(filepath)
            table_name = PathlibPath(filepath).stem.replace("-", "_").lower()

            #save metadata to DuckDB
            headers = file_df.columns.tolist()
            headers_str = ", ".join(headers)

            duck_conn = get_duckdb_conn()
            
            try:
                # Properly create table from CSV file path
                duck_conn.execute(
                    f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto(?)",
                    [filepath]
                )
                logger.info(f"[UPLOAD] Created DuckDB table: {table_name}")

                # save metadata to DuckDB table tables_metadata
                duck_conn.execute(
                    "INSERT INTO tables_metadata (table_name, role) VALUES (?, ?)",
                    (table_name, role)
                )
                logger.info(f"[UPLOAD] Added metadata for table: {table_name}, role: {role}")
                
                # commit the changes to DuckDB
                duck_conn.commit()
            except Exception as e:
                logger.error(f"[UPLOAD] Error creating DuckDB table: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")
            finally:
                duck_conn.close()

        elif extension in ["txt", "md"]:
            content = data.decode("utf-8")
            headers_str = None

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")

        # save metadata to SQLite
        sqlite_conn = get_sqlite_conn()
        sqlite_cur = sqlite_conn.cursor()

        logger.info(f"[UPLOAD] Saving document metadata: {filename}")
        sqlite_cur.execute(
            """
            INSERT INTO documents (filename, filepath, role, headers_str, embedded) VALUES (?, ?, ?, ?, ?)
            """,
            (filename, filepath, role, headers_str, 0)
        )
        sqlite_conn.commit()
        logger.info(f"[UPLOAD] Document metadata saved for: {filename}")

        # Calling indexing process to embed the document into the vector store
        # Run in thread pool to avoid blocking async context
        try:
            logger.info(f"[UPLOAD] Starting embedding process for: {filename}")
            
            # Run embedding in thread executor
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, index_unembedded_document)
            
            logger.info(f"[UPLOAD] Embedding completed successfully for: {filename}")
            
            # Verify embedding was successful
            sqlite_cur.execute("SELECT embedded FROM documents WHERE filename = ? LIMIT 1", (filename,))
            embedded_status = sqlite_cur.fetchone()
            
            if embedded_status and embedded_status[0] == 1:
                logger.info(f"[UPLOAD] ✅ Document {filename} confirmed embedded in vectorstore")
                audit.emit(
                    action="document.upload",
                    resource=f"document.upload:{filename}",
                    authorization_decision="allowed",
                    result="success",
                    outcome_status="authorized",
                    query_mode="document",
                )
                return JSONResponse(content={
                    "message": f"✅ {filename} uploaded and embedded successfully for role '{role}'.",
                    "embedded": True
                })
            else:
                logger.warning(f"[UPLOAD] Document not marked as embedded: {filename}")
                audit.emit(
                    action="document.upload",
                    resource=f"document.upload:{filename}",
                    authorization_decision="allowed",
                    result="success",
                    outcome_status="authorized",
                    query_mode="document",
                )
                return JSONResponse(
                    status_code=202,
                    content={
                        "message": f"✅ {filename} uploaded. Embedding in progress...",
                        "embedded": False
                    }
                )
        except Exception as embed_error:
            logger.error(f"[UPLOAD] Embedding failed for {filename}: {type(embed_error).__name__}: {str(embed_error)}", exc_info=True)

            retry_attempted = False
            retry_error = None
            try:
                embedding_status = _get_embedding_status_payload()
                if embedding_status["unembedded_count"] > 0:
                    retry_attempted = True
                    await _retry_unembedded_documents()
            except Exception as retry_exception:
                retry_error = retry_exception
                logger.error(
                    "[UPLOAD] Automatic embedding retry failed for %s: %s: %s",
                    filename,
                    type(retry_exception).__name__,
                    str(retry_exception),
                    exc_info=True,
                )

            sqlite_cur.execute(
                "SELECT embedded FROM documents WHERE filename = ? ORDER BY id DESC LIMIT 1",
                (filename,),
            )
            embedded_after_retry = sqlite_cur.fetchone()
            if embedded_after_retry and embedded_after_retry[0] == 1:
                audit.emit(
                    action="document.upload",
                    resource=f"document.upload:{filename}",
                    authorization_decision="allowed",
                    result="success",
                    outcome_status="authorized",
                    query_mode="document",
                )
                return JSONResponse(content={
                    "message": f"{filename} uploaded and embedded successfully after retry.",
                    "embedded": True,
                    "retry_attempted": retry_attempted,
                })

            audit.emit(
                action="document.upload",
                resource=f"document.upload:{filename}",
                authorization_decision="allowed",
                result="failure",
                outcome_status="failed",
                query_mode="document",
            )
            return JSONResponse(
                status_code=202,
                content={
                    "message": f"⚠️ {filename} uploaded but embedding failed: {str(embed_error)[:100]}",
                    "error": str(embed_error),
                    "embedded": False,
                    "retry_attempted": retry_attempted,
                    "retry_failed": retry_error is not None
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPLOAD] Unexpected error: {type(e).__name__}: {str(e)}", exc_info=True)
        audit.emit(
            action="document.upload",
            resource="document.upload",
            authorization_decision="allowed",
            result="failure",
            outcome_status="failed",
            query_mode="document",
        )
        try:
            if 'sqlite_conn' in locals():
                sqlite_conn.rollback()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"An error occurred while uploading the file: {str(e)[:100]}")


@router.post("/admin/embedding/retry")
async def retry_embed_documents(
    audit: AuditContext = Depends(get_audit_context),
):
    """
    Retry embedding for all unembedded documents.

    This is an administrative operation because it performs external model
    calls and writes to the vector store.
    """
    check_c_level_access(
        audit,
        action="document.embedding.admin",
        resource="document.embedding",
        detail="Administrator access required.",
        query_mode="document",
    )
    try:
        logger.info("[RETRY] Starting manual embedding retry...")
        retry_counts = await _retry_unembedded_documents()
        
        logger.info("[RETRY] Embedding retry completed")
        
        audit.emit(
            action="document.embedding.retry",
            resource="document.embedding",
            authorization_decision="allowed",
            result="success",
            outcome_status="authorized",
            query_mode="document",
        )
        return JSONResponse(content={
            "message": "Retry embedding completed",
            **retry_counts,
        })
        
    except Exception as e:
        logger.error(f"[RETRY] Error during retry: {type(e).__name__}: {str(e)}", exc_info=True)
        audit.emit(
            action="document.embedding.retry",
            resource="document.embedding",
            authorization_decision="allowed",
            result="failure",
            outcome_status="failed",
            query_mode="document",
        )
        raise HTTPException(status_code=500, detail="Retry failed.")


@router.get("/admin/embedding-status")
async def get_embedding_status(
    audit: AuditContext = Depends(get_audit_context),
):
    """
    Check embedding status for all documents without exposing server paths.
    """
    check_c_level_access(
        audit,
        action="document.embedding.admin",
        resource="document.embedding",
        detail="Administrator access required.",
        query_mode="document",
    )
    try:
        status = _get_embedding_status_payload()

        audit.emit(
            action="document.embedding.status",
            resource="document.embedding",
            authorization_decision="allowed",
            result="success",
            outcome_status="authorized",
            query_mode="document",
        )
        return JSONResponse(content={
            "total": status["total"],
            "embedded": status["embedded_count"],
            "unembedded": status["unembedded_count"],
            "embedded_docs": status["embedded_docs"],
            "unembedded_docs": status["unembedded_docs"],
        })
        
    except Exception as e:
        logger.error(f"[STATUS] Error getting status: {str(e)}", exc_info=True)
        audit.emit(
            action="document.embedding.status",
            resource="document.embedding",
            authorization_decision="allowed",
            result="failure",
            outcome_status="failed",
            query_mode="document",
        )
        raise HTTPException(status_code=500, detail="Status check failed.")


