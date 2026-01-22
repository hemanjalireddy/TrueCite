# TrueCite: AI Compliance Auditor

**For Readily Take-Home Assignment**

TrueCite is an automated compliance auditing tool designed to verify healthcare policies against regulatory requirements. It uses a Retrieval Augmented Generation (RAG) architecture to ingest policy documents, extract audit questions from PDF forms, and autonomously determine compliance with cited evidence.

## The Stack
* **Language:** Python 3.10
* **Manager:** Poetry
* **Interface:** Streamlit
* **AI Engine:** Google Vertex AI (Gemini 1.5 Flash) + LangChain
* **Retrieval:** Ensemble (BM25 + ChromaDB) + Metadata Injection
* **Infrastructure:** Docker + Google Cloud Run

## Key Capabilities

### 1. 🧠 Automated Question Extraction
* **Endpoint:** `/audit/run`
* **Function:** Automatically parses unstructured "Audit Requirement" PDFs (e.g., standard regulatory forms) to identify and list all compliance questions.
* **Tech:** Uses an extraction engine to separate specific requirements from general form text.

### 2. ⚡ Real-Time Streaming Audit
* **Architecture:** Async generator pattern with Heartbeat mechanism.
* **Function:** Processes long lists of audit questions sequentially without connection timeouts.
* **Experience:** The frontend receives results item-by-item via NDJSON streaming, allowing users to see progress instantly rather than waiting for the entire batch to finish.

### 3. 👁️ Transparent "Chain of Thought" (CoT)
* **Data Model:** Returns specific `thinking`, `status`, and `rationale` fields.
* **Function:** Unlike "Black Box" AI, TrueCite exposes its internal reasoning step-by-step. It classifies findings into **Compliant**, **Non-Compliant**, **Partial**, or **Missing Info**.

### 4. 📚 Bulk Policy Knowledge Base
* **Endpoint:** `/ingest/policies`
* **Function:** Accepts ZIP archives of PDF policies.
* **Tech:** Implements "Soft Filtering" where policy titles are injected into vector chunks (`[[POLICY: Name]]`) to ensure the AI can distinguish between similar rules in different documents.

### 5. 🔍 Hybrid Retrieval System
* **Function:** Combines Vector Search (semantic meaning) with BM25 (keyword matching) to ensure that specific ID numbers (like "APL 25-008") are caught even if semantic similarity is low.

## Setup & Deployment

### 1. Configure Environment Variables
You need a Google Cloud API Key with **Vertex AI** enabled.

1.  Copy the template:
    ```bash
    cp .env.templ .env
    ```
2.  Open `.env` and paste your API key:
    ```ini
    GOOGLE_API_KEY="your-secret-key-here"
    ```

### 2. Local Docker Run
```bash
docker-compose up --build 
```

Access the frontend at http://localhost:8501.