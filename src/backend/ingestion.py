import os
import json
import zipfile
import tempfile
from pathlib import Path
from typing import List

from loguru import logger
from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever

from .config import settings

# --- PATHS ---
CURRENT_DIR = Path(__file__).parent.resolve()
DATA_DIR = CURRENT_DIR / "data"
REGISTRAR_PROMPT_PATH = DATA_DIR / "intake_registrar_prompt.txt"

class PolicyIngestor:
    def __init__(self):
        """
        Initializes the Ingestor with Content-Based Naming and Hybrid Search support.
        """
        logger.debug("Initializing optimized PolicyIngestor...")
        
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model=settings.EMBEDDING_MODEL, 
            google_api_key=settings.GOOGLE_API_KEY
        )
        
        self.tagger_llm = ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0
        )

        self.persist_dir = os.path.join(os.getcwd(), settings.CHROMA_PERSIST_DIR)
        
        self.vectorstore = Chroma(
            collection_name=settings.CHROMA_COLLECTION, 
            embedding_function=self.embeddings,
            persist_directory=self.persist_dir 
        )

        if REGISTRAR_PROMPT_PATH.exists():
            self.registrar_template = REGISTRAR_PROMPT_PATH.read_text()
        else:
            logger.error(f"Registrar prompt missing at {REGISTRAR_PROMPT_PATH}")
            self.registrar_template = "Identify this doc. Return JSON: {{'formal_title': '...', 'category': '...'}}. Text: {text}"

    def _get_actual_metadata(self, first_page_text: str) -> dict:

        try:
            prompt = self.registrar_template.format(text=first_page_text[:3000])
            res = self.tagger_llm.invoke(prompt)
            clean_json = res.content.strip().replace("```json", "").replace("```", "")
            return json.loads(clean_json)
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
            return {"formal_title": "Unknown Policy", "category": "General"}

    def ingest_pdf(self, file_path: str, original_name: str) -> int:
        """
        Processes a single PDF with Soft Filtering and Metadata Enrichment.
        """
        try:
            loader = PyPDFLoader(file_path)
            pages = loader.load()
            if not pages: return 0

            
            doc_info = self._get_actual_metadata(pages[0].page_content)
            actual_title = doc_info.get("formal_title", original_name)
            category = doc_info.get("category", "General")

            
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP
            )
            chunks = splitter.split_documents(pages)

            for chunk in chunks:
                chunk.metadata.update({
                    "doc_title": actual_title,
                    "category": category,
                    "source_file": original_name
                })
                chunk.page_content = (
                    f"[[POLICY: {actual_title}]]\n"
                    f"[[CATEGORY: {category}]]\n"
                    f"{chunk.page_content}"
                )

            self.vectorstore.add_documents(chunks)
            logger.success(f"Ingested: {actual_title} ({len(chunks)} chunks)")
            return len(chunks)

        except Exception as e:
            logger.error(f"Failed to ingest {original_name}: {e}")
            return 0

    def ingest_zip(self, zip_path: str) -> int:
        """
        Processes ZIP files sequentially for hosting stability.
        """
        total_chunks = 0
        with zipfile.ZipFile(zip_path, 'r') as z:
            pdf_files = [f for f in z.namelist() if f.lower().endswith(".pdf") and not f.startswith('__MACOSX')]
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                z.extractall(tmp_dir)
                for f_name in pdf_files:
                    full_path = os.path.join(tmp_dir, f_name)
                    count = self.ingest_pdf(full_path, f_name)
                    total_chunks += count
                    
        return total_chunks

    def get_retriever(self):
        """
        Requirement: Accuracy via Hybrid Search (Vector + BM25).
        """
        
        vector_retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": settings.RETRIEVAL_K}
        )

        all_docs = self.vectorstore.get()
        if not all_docs['documents']:
            return vector_retriever
            
        from langchain_core.documents import Document
        docs = [Document(page_content=txt, metadata=md) 
                for txt, md in zip(all_docs['documents'], all_docs['metadatas'])]
        
        bm25_retriever = BM25Retriever.from_documents(docs)
        bm25_retriever.k = settings.RETRIEVAL_K

        ensemble_retriever = EnsembleRetriever(
            retrievers=[bm25_retriever, vector_retriever],
            weights=[0.3, 0.7] 
        )
        
        return ensemble_retriever