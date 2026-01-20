import os
import uuid
import zipfile
import tempfile
import shutil
from typing import Optional, List

from loguru import logger
from langchain_community.document_loaders import PyPDFLoader
from langchain_chroma import Chroma
from langchain_google_vertexai import VertexAIEmbeddings
from langchain.storage import InMemoryStore
from langchain.retrievers import ParentDocumentRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter

from true_cite.config import settings

class PolicyIngestor:
    def __init__(
        self, 
        embedding_model: str = settings.EMBEDDING_MODEL,
        chroma_collection: str = settings.CHROMA_COLLECTION
    ):
        """
        Initializes the Vector Database.
        """
        logger.debug(f"Initializing PolicyIngestor with model={embedding_model}, collection={chroma_collection}")
        
        self.embedding = VertexAIEmbeddings(model_name=embedding_model)

        self.persist_dir = tempfile.mkdtemp()
        
        self.vectorstore = Chroma(
            collection_name=chroma_collection, 
            embedding_function=self.embedding,
            persist_directory=self.persist_dir 
        )

        self.docstore = InMemoryStore()

        self.retriever = ParentDocumentRetriever(
            vectorstore=self.vectorstore,
            docstore=self.docstore,
            child_splitter=RecursiveCharacterTextSplitter(chunk_size=settings.CHUNK_SIZE),
            parent_splitter=RecursiveCharacterTextSplitter(chunk_size=settings.PARENT_CHUNK_SIZE)
        )
        logger.info("PolicyIngestor initialized successfully.")

    def ingest_pdf(self, file_path: str, source_name: str = None) -> int:
        """
        Reads a single PDF and adds it to the knowledge base.
        Returns the number of chunks added.
        """
        if not source_name:
            source_name = os.path.basename(file_path)

        logger.info(f"Processing: {source_name}...")

        try:
            
            loader = PyPDFLoader(file_path)
            raw_docs = loader.load()

            
            for doc in raw_docs:
                doc.metadata["source_file"] = source_name
            
           
            self.retriever.add_documents(raw_docs, ids=[str(uuid.uuid4()) for _ in raw_docs])
            
            logger.success(f"Ingested {len(raw_docs)} pages from {source_name}")
            return len(raw_docs)

        except Exception as e:
            logger.error(f"Error ingesting {source_name}: {e}")
            return 0

    def ingest_zip(self, zip_path: str) -> int:
        """
        Extracts and processes
        """
        total_pages = 0
        logger.info(f"Processing ZIP archive: {zip_path}")

        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                all_files = z.namelist()
                
                pdf_files = [f for f in all_files if f.lower().endswith(".pdf")]
                logger.info(f"Found {len(pdf_files)} PDFs in archive.")

                
                with tempfile.TemporaryDirectory() as temp_dir:
                    for file_name in pdf_files:
                        try:
                            
                            extracted_path = z.extract(file_name, path=temp_dir)
                            
                            
                            pages = self.ingest_pdf(extracted_path, source_name=file_name)
                            total_pages += pages
                            
                            
                            if os.path.exists(extracted_path):
                                os.remove(extracted_path)
                        except Exception as e:
                            logger.warning(f"Skipped file {file_name} inside zip: {e}")
            
            logger.info(f"ZIP Processing Complete. Ingested {total_pages} pages total.")
            return total_pages

        except Exception as e:
            logger.error(f"Failed to process ZIP {zip_path}: {e}")
            return 0

    def get_retriever(self):
        return self.retriever