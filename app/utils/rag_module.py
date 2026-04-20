
from fastapi import HTTPException, Path
from openai import vector_stores
import pandas as pd
from app.schemas.sqlitedb import get_sqlite_conn

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

def load_file(filepath, role):
    
    extension = filepath.split(".")[-1].lower()

    try: 
        if extension == "csv":
            file_df = pd.read_csv(filepath)
            documents = []

            # convert each row to a document with metadata
            for row in file_df.to_dict(orient="records"):
                # convert row of CSV file dict to string content for embedding
                content = "\n".join(f"{key}: {value}" for key, value in row.items())
                documents.append(
                    Document(
                        page_content=content,
                        metadata={"role": role.lower(), "source": Path(filepath).name}
                    )
                )
            return documents
        
        elif extension in ["txt", "md"]:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            return [
                Document(
                    page_content=content,
                    metadata={"role": role.lower(), "source": Path(filepath).name}
                )
            ]
        
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")
    
    except Exception as e:
        print(f"Error loading file {filepath}: {e}")
        return None

def embed_documents_to_vectorstore(docs):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    vectorstore.add_documents(splits)

    print("Documents embedded and saved to vectorstore.")
    print("Total documents:", len(vectorstore.get()["documents"]))

# This function is defined to index any existing documents in the database that haven't been embedded yet.
def index_unembedded_document():
    
    sqlite_conn = get_sqlite_conn()
    sqlite_cur = sqlite_conn.cursor()

    # fetch documents present in Sqlite DB that haven't been embedded yet
    sqlite_cur.execute("SELECT id, filepath, role FROM documents WHERE embedded = 0")
    documents_to_index = sqlite_cur.fetchall()

    all_documents = []
    loaded_doc_ids = []

    for doc_id, filepath, role in documents_to_index:
        
        docs = load_file(filepath, role)

        if docs:
            if isinstance(docs, list):
                all_documents.extend(docs)
            else:
                all_documents.append(docs)
        
        # keep track of successfully loaded documents
        loaded_doc_ids.append(doc_id)   
        
    # mark document as embedded
    if all_documents:

        try:
            embed_documents_to_vectorstore(all_documents)

            for doc_id in loaded_doc_ids:
                sqlite_cur.execute("UPDATE documents SET embedded = 1 WHERE id = ?", (doc_id,))

            sqlite_conn.commit()
        except Exception as e:
            print(f"Error occurred while embedding documents: {e}")
            sqlite_conn.rollback()

