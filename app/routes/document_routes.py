
import os
from fastapi import APIRouter, File, Form, Path, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd

from app.schemas.duckdb import get_duckdb_conn
from app.schemas.sqlitedb import get_sqlite_conn
from app.utils.rag_module import index_unembedded_document

router = APIRouter()

UPLOAD_DIR = "static/uploads/"

@router.post("/upload-docs/")
async def upload_docs(file: UploadFile = File(...), role: str = Form(...)):

    try: 
        # extract the file details
        filename = file.filename
        extension = filename.split(".")[-1].lower()
        # extension = Path(filename).suffix.lower()

        # save the file to the appropriate directory based on the role
        role_dir = os.path.join(UPLOAD_DIR, role)
        os.makedirs(role_dir, exist_ok=True)
        filepath = os.path.join(role_dir, filename)

        # read the file content and save it to the specified path for future indexing
        data = await file.read()

        with open(filepath, "wb") as f:
            f.write(data)
        
        # convert to string content for validation
        
        if extension == "csv":
            from io import BytesIO
            df = pd.read_csv(BytesIO(data))
            content = df.to_string(index=False)

            #load from DuckDB
            file_df = pd.read_csv(filepath)
            table_name = Path(filepath).stem.replace("-", "_").lower()

            #save metadata to DuckDB
            headers = file_df.columns.tolist()
            headers_str = ", ".join(headers)

            duck_conn = get_duckdb_conn()
            duck_conn.execute(
                """
                CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM file_df
                """
            )

            # save metadata to DuckDB table tables_metadata
            duck_conn.execute(
                """
                INSERT INTO tables_metadata (table_name, roles) VALUES (?, ?)
                """,
                (table_name, role)
            )

            # commit the changes to DuckDB
            duck_conn.commit()

        elif extension in ["txt", "md"]:
            content = data.decode("utf-8")
            headers_str = None

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")

        # save metadata to SQLite
        sqlite_conn = get_sqlite_conn()
        sqlite_cur = sqlite_conn.cursor()

        sqlite_cur.execute(
            """
            INSERT INTO documents (filename, filepath, role, headers_str, embedded) VALUES (?, ?, ?, ?, ?)
            """,
            (filename, filepath, role, headers_str, 0)
        )
        sqlite_conn.commit()

        # Calling indexing process to embed the document into the vector store.
        index_unembedded_document()
        print("Files are indexed successfully.")
        return JSONResponse(content={"message": f"{filename} uploaded successfully for role '{role}'."})
    
    except FileNotFoundError as fnfe:
        raise FileNotFoundError(status_code=404, detail=f"File not found: {fnfe}")
    except Exception as e:
        print("Rolling back due to error:", e)
        sqlite_conn.rollback()
        raise Exception(status_code=500, detail=f"An error occurred while uploading the file: {e}")
    
    finally:
        # ensure connections are closed after operation
        duck_conn.close()
        sqlite_conn.close()


