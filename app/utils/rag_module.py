from fastapi import HTTPException
from pathlib import Path
from groq import Groq
import pandas as pd

from dotenv import load_dotenv
import os

from app.schemas.sqlitedb import get_sqlite_conn
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain
from langchain_cohere import CohereRerank
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
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

# # Create the embedding function
# hf_embeddings = embedding_functions.HuggingFaceEmbeddingFunction(
#     api_key=hf_api_key,
#     model_name="sentence-transformers/all-MiniLM-L6-v2"
# )

# vectorstore = Chroma(
#     # name="my_huggingface_collection",
#     persist_directory="chroma_db",
#     embedding_function=hf_embeddings
# )

# Create the embedding function using LangChain
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# Create a ChromaDB collection with LangChain compatibility
vectorstore = Chroma(
    persist_directory="chroma_db",
    embedding_function=embeddings
)

def load_file(filepath, role):
    """Load file with comprehensive error handling and path validation."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Ensure filepath is absolute to avoid working directory issues
    if not os.path.isabs(filepath):
        filepath = os.path.abspath(filepath)
    
    logger.info(f"[LOAD_FILE] Loading from absolute path: {filepath}")
    
    # Verify file exists before attempting to load
    if not os.path.exists(filepath):
        logger.error(f"[LOAD_FILE] File does not exist: {filepath}")
        return None
    
    extension = filepath.split(".")[-1].lower()

    try: 
        if extension == "csv":
            logger.info(f"[LOAD_FILE] Loading CSV file: {filepath}")
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
            logger.info(f"[LOAD_FILE] Successfully loaded {len(documents)} rows from CSV")
            return documents
        
        elif extension in ["txt", "md"]:
            logger.info(f"[LOAD_FILE] Loading markdown/text file: {filepath}")
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            if not content or not content.strip():
                logger.warning(f"[LOAD_FILE] File is empty: {filepath}")
                return None
                
            logger.info(f"[LOAD_FILE] Successfully loaded {len(content)} characters from file")
            return [
                Document(
                    page_content=content,
                    metadata={"role": role.lower(), "source": Path(filepath).name}
                )
            ]
        
            # logger.info(f"[LOAD_FILE] Successfully loaded {len(content)} characters from file")
            # return [{
            #         "page_content":content,
            #         "metadata": {"role": role.lower(), "source": Path(filepath).name}
            # }]
        
        else:
            logger.error(f"[LOAD_FILE] Unsupported file type: {extension}")
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")
    
    except Exception as e:
        logger.error(f"[LOAD_FILE] Error loading file {filepath}: {type(e).__name__}: {str(e)}", exc_info=True)
        return None

def embed_documents_to_vectorstore(docs):
    """Add documents to vectorstore with LangChain-compatible embedding function."""
    import logging
    logger = logging.getLogger(__name__)
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    vectorstore.add_documents(splits)
    logger.info(f"[VECTORSTORE] ✅ Successfully added to vectorstore")

    # print("Documents embedded and saved to vectorstore.")
    # print("Total documents:", len(vectorstore.get()["documents"]))

    total_docs = len(vectorstore.get().get("documents", []))
    logger.info(f"[VECTORSTORE] Total documents in vectorstore: {total_docs}")

# This function is defined to index any existing documents in the vectorstore that haven't been embedded yet.
def index_unembedded_document():
    """Embed all unembedded documents in the vector store with comprehensive logging and error handling."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        sqlite_conn = get_sqlite_conn()
        sqlite_cur = sqlite_conn.cursor()

        # fetch documents present in Sqlite DB that haven't been embedded yet
        sqlite_cur.execute("SELECT id, filepath, role FROM documents WHERE embedded = 0")
        documents_to_index = sqlite_cur.fetchall()
        
        if not documents_to_index:
            logger.info("[EMBEDDING] No unembedded documents found")
            return
        
        logger.info(f"[EMBEDDING] Found {len(documents_to_index)} unembedded documents to process")

        all_documents = []
        loaded_doc_ids = []
        failed_doc_ids = []

        # Load all documents
        for doc_id, filepath, role in documents_to_index:
            try:
                logger.info(f"[EMBEDDING] Loading document ID={doc_id}: {filepath}")
                docs = load_file(filepath, role)

                if docs:
                    if isinstance(docs, list):
                        # Filter out empty documents
                        valid_docs = [d for d in docs if d and d.page_content and d.page_content.strip()]
                        if valid_docs:
                            all_documents.extend(valid_docs)
                            logger.info(f"[EMBEDDING] Loaded {len(valid_docs)} valid chunks from {filepath}")
                            loaded_doc_ids.append(doc_id)
                        else:
                            logger.warning(f"[EMBEDDING] No valid content in {filepath}")
                            failed_doc_ids.append(doc_id)
                    else:
                        if docs.page_content and docs.page_content.strip():
                            all_documents.append(docs)
                            logger.info(f"[EMBEDDING] Loaded 1 document from {filepath}")
                            loaded_doc_ids.append(doc_id)
                        else:
                            logger.warning(f"[EMBEDDING] Empty document content: {filepath}")
                            failed_doc_ids.append(doc_id)
                else:
                    logger.warning(f"[EMBEDDING] Failed to load document: {filepath}")
                    failed_doc_ids.append(doc_id)
                    
            except Exception as load_error:
                logger.error(f"[EMBEDDING] Error loading {filepath}: {type(load_error).__name__}: {str(load_error)}")
                failed_doc_ids.append(doc_id)
        
        # Embed documents if any were loaded
        if all_documents:
            try:
                logger.info(f"[EMBEDDING] Embedding {len(all_documents)} document chunks to vectorstore...")
                embed_documents_to_vectorstore(all_documents)
                logger.info(f"[EMBEDDING] Successfully added to vectorstore")

                # Mark successfully loaded documents as embedded
                for doc_id in loaded_doc_ids:
                    sqlite_cur.execute("UPDATE documents SET embedded = 1 WHERE id = ?", (doc_id,))
                    logger.info(f"[EMBEDDING] Marked doc_id {doc_id} as embedded")

                sqlite_conn.commit()
                logger.info(f"[EMBEDDING] ✅ Successfully embedded {len(loaded_doc_ids)} documents. Failed: {len(failed_doc_ids)}")
                
            except Exception as embed_error:
                logger.error(f"[EMBEDDING] Error during vectorstore embedding: {type(embed_error).__name__}: {str(embed_error)}", exc_info=True)
                sqlite_conn.rollback()
                raise
        else:
            logger.warning(f"[EMBEDDING] ❌ No documents loaded successfully. Failed: {len(failed_doc_ids)}/{len(documents_to_index)}")
            
    except Exception as e:
        logger.error(f"[EMBEDDING] Fatal error in index_unembedded_document: {type(e).__name__}: {str(e)}", exc_info=True)
        raise


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
    model_name="llama-3.3-70b-versatile",
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

    #compression of retriever to get more relevant results
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=reranker, 
        base_retriever=retriever
    )

    return compression_retriever


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
                "role": {"$in": [user_role, "general"]}
            }
        })
    
    # wrap with re-ranker using cohere reranking model
    if cohere_api_key:
        retriever = wrap_with_reranker(retriever, cohere_api_key, 4)
        
    return create_retrieval_chain(retriever, chatting_chain)



# # ========== MAIN EXECUTION ==========
# if __name__ == "__main__":
#     index_unembedded_document() 

#     user_role = "hr" 
#     rag_chain = get_rag_chain(user_role)

    
#     query = "give me Campaign Highlights from marketing summary."
#     response = rag_chain.invoke({"input": query})

#     print((response["answer"]))
#     for doc in response.get("context", []):
#         print(f"Source: {doc.metadata['source']}, Role: {doc.metadata.get('role')}")