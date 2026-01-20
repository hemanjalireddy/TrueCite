# TrueCite: AI Compliance Auditor

**For Readily Take-Home Assignment**

TrueCite is an automated compliance auditing tool designed to verify healthcare policies against regulatory requirements.

## The Stack
* **Language:** Python 3.10
* **Manager:** Poetry
* **Interface:** Streamlit
* **AI Engine:** Google Vertex AI + LangChain
* **Retrieval:** Ensemble (BM25 + ChromaDB) + FlashRank Re-ranking
* **Infrastructure:** Docker + Google Cloud Run

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