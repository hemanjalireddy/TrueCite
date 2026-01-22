import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field
from loguru import logger


from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

from .config import settings

CURRENT_DIR = Path(__file__).parent.resolve()
PROMPT_FILE_PATH = CURRENT_DIR / "data" / "audit_prompt.txt"

class AuditResult(BaseModel):
    question: str
    thinking: str = Field(description="The step-by-step reasoning (CoT)")
    answer: str = Field(description="The final rationale and citations")
    status: str = Field(description="Compliant, Non-Compliant, Partial, or Missing Info")
    sources: List[str] = Field(description="List of filenames cited")

class AuditEngine:
    def __init__(self , model_name: str = settings.LLM_MODEL):
        """
        Initializes the LLM and loads the Prompt Template from disk.
        """
        logger.debug(f"Initializing AuditEngine with LLM={model_name}")

       
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.0,
            google_api_key=settings.GOOGLE_API_KEY
        )

        try:
            if not PROMPT_FILE_PATH.exists():
                raise FileNotFoundError(f"Prompt file not found at: {PROMPT_FILE_PATH}")
                
            with open(PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
                prompt_text = f.read()
            
            self.prompt = ChatPromptTemplate.from_template(prompt_text)
            logger.debug(f"Loaded audit prompt from {PROMPT_FILE_PATH}")
            
        except Exception as e:
            logger.critical(f"Failed to load prompt file: {e}")
            raise e

    def format_docs(self, docs):
        """
        Prepares documents for the LLM. 
        Crucially, this injects the 'source_file' metadata into the text 
        so the LLM can see it and cite it.
        """
        formatted_chunks = []
        for doc in docs:
            source = doc.metadata.get("source_file", "Unknown Source")
            content = doc.page_content.replace("\n", " ")
            formatted_chunks.append(f"[Source: {source}]\n{content}\n")
        
        return "\n---\n".join(formatted_chunks)

    async def run_audit(self, question: str, retriever) -> AuditResult:
        logger.info(f"Auditing: {question}")
        
        try:
            docs = await retriever.ainvoke(question)
            context_text = self.format_docs(docs)
            
            chain = self.prompt | self.llm | StrOutputParser()
            response_text = await chain.ainvoke({"context": context_text, "question": question})

            parsed = self._parse_structured_response(response_text)

            unique_sources = list(set([d.metadata.get("source_file") for d in docs]))

            result = AuditResult(
                question=question,
                thinking=parsed["thinking"],
                status=parsed["status"],
                answer=f"{parsed['rationale']}\n\n{parsed['citation']}",
                sources=unique_sources
            )
            
            logger.success(f"Audit complete. Status: {result.status}")
            return result

        except Exception as e:
            logger.error(f"Audit failed: {e}")
            return AuditResult(
                question=question, 
                thinking="Error during reasoning.",
                answer=f"Error running audit: {str(e)}", 
                status="Error", 
                sources=[]
            )

    def _parse_structured_response(self, text: str) -> dict:
        """Splits the raw LLM string into components based on our Prompt Schema."""
        sections = {
            "thinking": "No thinking provided.",
            "status": "Unknown",
            "rationale": "",
            "citation": ""
        }
        
        try:
            if "**THINKING**:" in text:
                sections["thinking"] = text.split("**THINKING**:")[1].split("**STATUS**:")[0].strip()
            
            if "**STATUS**:" in text:
                sections["status"] = text.split("**STATUS**:")[1].split("**RATIONALE**:")[0].strip()
            
            if "**RATIONALE**:" in text:
                sections["rationale"] = text.split("**RATIONALE**:")[1].split("**EVIDENCE CITATION**:")[0].strip()
            
            if "**EVIDENCE CITATION**:" in text:
                sections["citation"] = text.split("**EVIDENCE CITATION**:")[1].strip()
        except Exception as e:
            logger.warning(f"Parsing partial response: {e}")
            
        return sections