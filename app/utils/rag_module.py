from fastapi import HTTPException, Path
from groq import Groq
import pandas as pd

from dotenv import load_dotenv
import os
import chromadb
import chromadb.utils.embedding_functions as embedding_functions

from app.schemas.sqlitedb import get_sqlite_conn
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain
from langchain_cohere import CohereRerank
# from langchain.retrievers import ContextualCompressionRetriever
# from langchain_community.retrievers import ContextualCompressionRetriever


load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_PROJECT"] = "RAG"

langchain_key = os.getenv("LANGCHAIN_API_KEY")
groq_api_key = os.getenv("GROQ_API_KEY")
cohere_api_key = os.getenv("COHERE_API_KEY")
hf_api_key = os.getenv("HF_API_KEY")

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

# Create the embedding function
hf_embeddings = embedding_functions.HuggingFaceEmbeddingFunction(
    api_key=hf_api_key,
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Create a ChromaDB collection with this function
client = chromadb.Client()
vectorstore = client.get_or_create_collection(
    name="my_huggingface_collection",
    # schema="chroma_db",
    embedding_function=hf_embeddings
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


# PROMPT TEMPLATE
system_prompt = (
    "You are an assistant for summarizing and answering queries from internal company documents.\n"
    "Always use the retrieved context to answer the query, even if partial.\n"
    "Do not guess. If data is not found, explain what you searched for.\n"
    "When responding:\n"
    "- Add **Source** from document metadata if possible.\n"
    "- Use headers\n"
    "- Use bullet points\n"
    "- For CSV-style data, format in table with two columns\n"
    "\n{context}"
)

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}"),
])

# Model
model = ChatGroq(
    groq_api_key=groq_api_key,
    model_name="gpt-oss-20b",
    temperature=0.2
)

chatting_chain = create_stuff_documents_chain(llm=model, prompt=chat_prompt)

# Re-ranker function to re-rank retrieved documents based on relevance to the query
def wrap_with_reranker(retriever, cohere_api_key, top_n=4):

    # Create Cohere's reranker with the vector DB using the base retriever
    reranker = CohereRerank(
        cohere_api_key=cohere_api_key, 
        model="rerank-english-v3.0", 
        top_n=top_n
    )

    return reranker;

    # compression of retriever to get more relevant results
    # compression_retriever = ContextualCompressionRetriever(
    #     base_compressor=reranker, 
    #     base_retriever=retriever
    # )

    # return compression_retriever


def get_rag_chain(user_role: str, cohere_api_key: str = None):
    user_role = user_role.lower()

    # c-level users can access all documents and have more detailed responses
    if user_role == "c-level":
        # retieve k most relevant documents
        retriever = vectorstore.as_retriever(search_kwargs = {"k": 4})
    
    # genral role users can only access documents tagged with genral
    elif user_role == "general":
        retriever = vectorstore.as_retriever(search_kwargs = {
            "k": 4,
            "filter": {"role": "general"}
        })
    # remaining users can see corresposnding tagged docuemnts alongside general dcouments
    else:
        retriever = vectorstore.as_retriever(search_kwargs = {
            "k": 4,
            "filter": {
                "$in": {"role": [user_role, "general"]}
            }
        })
    
    # wrap with re-ranker using cohere reranking model
    if cohere_api_key:
        retriever = wrap_with_reranker(retriever, cohere_api_key)
    return create_retrieval_chain(retriever, chatting_chain)



# ========== MAIN EXECUTION ==========
if __name__ == "__main__":
    index_unembedded_document() 

    user_role = "hr" 
    rag_chain = get_rag_chain(user_role)

    
    query = "give me Campaign Highlights from marketing summary."
    response = rag_chain.invoke({"input": query})

    print((response["answer"]))
    for doc in response.get("context", []):
        print(f"Source: {doc.metadata['source']}, Role: {doc.metadata.get('role')}")