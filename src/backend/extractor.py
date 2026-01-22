import json
from pathlib import Path
from typing import List
from loguru import logger
from pydantic import BaseModel, Field

from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .config import settings

CURRENT_DIR = Path(__file__).parent.resolve()
PROMPT_PATH = CURRENT_DIR / "data" / "extraction_prompt.txt"

class QuestionList(BaseModel):
    questions: List[str] = Field(description="List of extracted audit questions")

class AuditQuestionExtractor:
    def __init__(self):
        """
        Initializes the LLM and loads the extraction prompt from disk.
        """
        self.llm = ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL,
            temperature=0.0,
            google_api_key=settings.GOOGLE_API_KEY
        )
        
        self.parser = JsonOutputParser(pydantic_object=QuestionList)

        try:
            if not PROMPT_PATH.exists():
                raise FileNotFoundError(f"Extraction prompt not found at {PROMPT_PATH}")

            with open(PROMPT_PATH, "r", encoding="utf-8") as f:
                prompt_text = f.read()

            self.prompt = ChatPromptTemplate.from_template(prompt_text)
            logger.debug("Loaded extraction prompt successfully.")

        except Exception as e:
            logger.error(f"Failed to load prompt: {e}")
            raise e

    def extract_from_file(self, file_path: str) -> List[str]:
        """
        Loads a PDF, sends it to Gemini, and returns a list of questions.
        """
        logger.info(f"Extracting questions from: {file_path}")
        try:
           
            loader = PyPDFLoader(file_path)
            pages = loader.load()
            
            
            full_text = "\n".join([p.page_content for p in pages])

            
            chain = self.prompt | self.llm | self.parser

            
            result = chain.invoke({
                "context": full_text,
                "format_instructions": self.parser.get_format_instructions()
            })

            questions = result.get("questions", [])
            logger.success(f"Extracted {len(questions)} questions from {Path(file_path).name}")
            return questions

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return []