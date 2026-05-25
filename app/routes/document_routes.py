import os
from pathlib import Path as PathlibPath
from fastapi import APIRouter, File, Form, Path, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.schemas.duckdb import get_duckdb_conn
from app.schemas.sqlitedb import get_sqlite_conn
from app.utils.rag_module import index_unembedded_document

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = "static/uploads/"

@router.post("/upload-docs")
async def upload_docs(file: UploadFile = File(...), role: str = Form(...)):

    try: 
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
                    "INSERT INTO tables_metadata (table_name, roles) VALUES (?, ?)",
                    (table_name, role)
                )
                logger.info(f"[UPLOAD] Added metadata for table: {table_name}, role: {role}")
                
                # commit the changes to DuckDB
                duck_conn.commit()
            except Exception as e:
                logger.error(f"[UPLOAD] Error creating DuckDB table: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")

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
                return JSONResponse(content={
                    "message": f"✅ {filename} uploaded and embedded successfully for role '{role}'.",
                    "embedded": True
                })
            else:
                logger.warning(f"[UPLOAD] Document not marked as embedded: {filename}")
                return JSONResponse(
                    status_code=202,
                    content={
                        "message": f"✅ {filename} uploaded. Embedding in progress...",
                        "embedded": False
                    }
                )
        except Exception as embed_error:
            logger.error(f"[UPLOAD] Embedding failed for {filename}: {type(embed_error).__name__}: {str(embed_error)}", exc_info=True)
            return JSONResponse(
                status_code=202,
                content={
                    "message": f"⚠️ {filename} uploaded but embedding failed: {str(embed_error)[:100]}",
                    "error": str(embed_error),
                    "embedded": False
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[UPLOAD] Unexpected error: {type(e).__name__}: {str(e)}", exc_info=True)
        try:
            if 'sqlite_conn' in locals():
                sqlite_conn.rollback()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"An error occurred while uploading the file: {str(e)[:100]}")


@router.get("/retry-embed")
async def retry_embed_documents():
    """
    Manual endpoint to retry embedding for all unembedded documents.
    Useful for debugging and recovery.
    """
    try:
        logger.info("[RETRY] Starting manual embedding retry...")
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(executor, index_unembedded_document)
        
        logger.info("[RETRY] Embedding retry completed")
        
        # Count embedded documents
        sqlite_conn = get_sqlite_conn()
        sqlite_cur = sqlite_conn.cursor()
        sqlite_cur.execute("SELECT COUNT(*) FROM documents WHERE embedded = 1")
        embedded_count = sqlite_cur.fetchone()[0]
        
        sqlite_cur.execute("SELECT COUNT(*) FROM documents WHERE embedded = 0")
        unembedded_count = sqlite_cur.fetchone()[0]
        
        return JSONResponse(content={
            "message": "Retry embedding completed",
            "embedded_count": embedded_count,
            "unembedded_count": unembedded_count
        })
        
    except Exception as e:
        logger.error(f"[RETRY] Error during retry: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Retry failed: {str(e)[:100]}")


@router.get("/embedding-status")
async def get_embedding_status():
    """
    Check embedding status for all documents.
    """
    try:
        sqlite_conn = get_sqlite_conn()
        sqlite_cur = sqlite_conn.cursor()
        
        sqlite_cur.execute("""
            SELECT filename, embedded, filepath FROM documents 
            ORDER BY embedded DESC, filename ASC
        """)
        
        docs = sqlite_cur.fetchall()
        
        embedded = [{"filename": d[0], "filepath": d[2]} for d in docs if d[1] == 1]
        unembedded = [{"filename": d[0], "filepath": d[2]} for d in docs if d[1] == 0]
        
        return JSONResponse(content={
            "total": len(docs),
            "embedded": len(embedded),
            "unembedded": len(unembedded),
            "embedded_docs": embedded,
            "unembedded_docs": unembedded
        })
        
    except Exception as e:
        logger.error(f"[STATUS] Error getting status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


