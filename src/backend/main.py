import os
import shutil
import tempfile
import json
import asyncio
from typing import List, Union

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from .ingestion import PolicyIngestor
from .auditor import AuditEngine
from .extractor import AuditQuestionExtractor

app = FastAPI(title="TrueCite API", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("Initializing TrueCite Engines...")
global_ingestor = PolicyIngestor()
auditor_engine = AuditEngine()
extractor_engine = AuditQuestionExtractor()
logger.success("Engines Ready.")

class SingleAuditRequest(BaseModel):
    question: str

class AuditResponse(BaseModel):
    question: str
    thinking: str
    answer: str
    status: str
    sources: List[str]

def save_upload_file(upload_file: UploadFile) -> str:
    suffix = os.path.splitext(upload_file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(upload_file.file, tmp)
        return tmp.name

@app.get("/")
def health_check():
    return {"status": "active"}

@app.post("/ingest/policies")
async def ingest_policies(file: UploadFile = File(...)):
    temp_path = save_upload_file(file)
    try:
        count = global_ingestor.ingest_zip(temp_path)
        return {"message": "Ingestion successful", "chunks_indexed": count}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.post("/audit/ask", response_model=AuditResponse)
async def ask_single_question(request: SingleAuditRequest):
    """Manual Chat Endpoint"""
    retriever = global_ingestor.get_retriever()
    if not retriever:
        raise HTTPException(status_code=400, detail="No policies indexed.")
    
    result = await auditor_engine.run_audit(request.question, retriever)
    return AuditResponse(
        question=result.question,
        thinking=result.thinking,
        answer=result.answer,
        status=result.status,
        sources=result.sources
    ) 

@app.post("/audit/run")
async def run_bulk_audit_stream(file: UploadFile = File(...)):
    """
    Takes one Audit PDF, extracts questions, and streams results.
    """
    retriever = global_ingestor.get_retriever()
    if not retriever:
        raise HTTPException(status_code=400, detail="No policies indexed. Please upload policies first.")

    path = save_upload_file(file)
    
    try:
        logger.info(f"Extracting questions from {file.filename}...")
        questions = extractor_engine.extract_from_file(path)
        
        if not questions:
            raise HTTPException(status_code=400, detail="Could not extract any questions.")

        async def audit_generator():
            yield json.dumps({"type": "meta", "total": len(questions)}) + "\n"

            for q_text in questions:
         
                yield " " 
                try:
                    res = await auditor_engine.run_audit(q_text, retriever)
                    
                    data = {
                        "type": "result",
                        "question": res.question,
                        "thinking": res.thinking,
                        "answer": res.answer,
                        "status": res.status,
                        "sources": res.sources
                    }
                    yield json.dumps(data) + "\n"
                except Exception as e:
                    logger.error(f"Error auditing question: {e}")
                    yield json.dumps({
                        "type": "result",
                        "question": q_text,
                        "thinking": "Error during processing.",
                        "answer": f"Internal Server Error: {str(e)}",
                        "status": "Error",
                        "sources": []
                    }) + "\n"

        return StreamingResponse(audit_generator(), media_type="application/x-ndjson")

    finally:
        if os.path.exists(path):
            os.remove(path)