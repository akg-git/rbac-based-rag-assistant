from fastapi import HTTPException, Path
from groq import Groq
import pandas as pd
from app.schemas.sqlitedb import get_sqlite_conn

from dotenv import load_dotenv
import os

from langchain_core.embeddings import OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma


load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "RAG"

langchain_key = os.getenv["LANGCHAIN_API_KEY"]
groq_api_key = os.getenv("GROQ_API_KEY")
cohere_api_key = os.environ["COHERE_API_KEY"]

if not groq_api_key:
    # raise SystemExit(f"Missing GROQ_API_KEY in {ENV_FILE}")
    raise SystemExit(f"Missing GROQ_API_KEY in ENV FILE")
elif not langchain_key:
    raise SystemExit(f"Missing LANGCHAIN_API_KEY in ENV FILE")
elif not cohere_api_key:
    raise SystemExit(f"Missing COHERE_API_KEY in ENV FILE")

groq_client = Groq(api_key=groq_api_key)

# initialize vectorstore at module level
# ==============================
# ====Split,load,embed==========
# ==============================

openai_embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(
    collection_name="my_collection",
    persist_directory="chroma_db",
    embedding_function=openai_embeddings
)


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

# This function is defined to index any existing documents in the vectorstore that haven't been embedded yet.
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

