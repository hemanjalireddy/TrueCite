import streamlit as st
import requests
import os
import pandas as pd
import json
from io import BytesIO

API_URL = os.getenv("API_URL", "http://backend:8000")

st.set_page_config(page_title="TrueCite Audit", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    .thinking-box {
        background-color: #f0f2f6;
        border-radius: 5px;
        padding: 10px;
        font-style: italic;
        color: #555;
        border-left: 5px solid #d1d5db;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ TrueCite: Audit Dashboard")

with st.sidebar:
    st.header("1. Knowledge Base")
    policy_file = st.file_uploader("Upload Policy ZIP", type="zip")
    if st.button("Index Policies") and policy_file:
        with st.status("Indexing...", expanded=True):
            files = {"file": (policy_file.name, policy_file.getvalue(), "application/zip")}
            try:
                res = requests.post(f"{API_URL}/ingest/policies", files=files)
                if res.status_code == 200:
                    st.success(f"Done! {res.json().get('chunks_indexed')} chunks added.")
                else:
                    st.error("Ingestion failed.")
            except Exception as e:
                st.error(f"Error: {e}")

tab1, tab2 = st.tabs(["💬 Manual Chat", "🚀 Live Audit Stream"])

with tab1:
    question = st.text_input("Ask a question about your policies:")
    if st.button("Ask") and question:
        with st.spinner("Analyzing knowledge base..."):
            try:
                res = requests.post(f"{API_URL}/audit/ask", json={"question": question})
                if res.status_code == 200:
                    data = res.json()
                    
                    st.subheader(f"Status: {data['status']}")
                    
                    with st.expander("View Auditor Reasoning"):
                        st.markdown(f"*{data.get('thinking', 'No reasoning available.')}*")
                    
                    # Display Final Answer
                    st.info(f"**Findings:**\n\n{data['answer']}")
                    st.caption(f"Sources identified: {', '.join(data['sources'])}")
                else:
                    st.error("Could not retrieve answer.")
            except Exception as e:
                st.error(f"Connection Error: {e}")


with tab2:
    st.header("Bulk Audit from PDF")
    uploaded_file = st.file_uploader("Upload 'Audit Requirements PDF'", type=["pdf"])
    
    if uploaded_file and st.button("Start Live Audit"):
        progress_bar = st.progress(0)
        status_box = st.empty()
        results_area = st.container()
        results_data = [] 

        try:
            status_box.info("Reading PDF and extracting questions...")
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            
            # Connect to stream
            with requests.post(f"{API_URL}/audit/run", files=files, stream=True) as response:
                if response.status_code == 200:
                    total_q = 0
                    processed = 0
                    status_box.info("Audit started! Processing questions one by one...")
                    
                    for line in response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8').strip()
                            if not decoded_line or decoded_line.startswith(":"):
                                continue

                            data = json.loads(decoded_line)
                            
                            if data.get("type") == "meta":
                                total_q = data['total']
                            
                            elif data.get("type") == "result":
                                processed += 1
                                results_data.append(data)
                                
                                # Update Progress
                                if total_q > 0:
                                    progress_bar.progress(processed / total_q)
                                
                                # Show Result Card
                                icon = {"Compliant": "✅", "Non-Compliant": "❌", "Partial": "⚠️", "Missing Info": "❓"}.get(data['status'], "ℹ️")
                                
                                with results_area.expander(f"{icon} {data['question'][:100]}..."):
                
                                    st.markdown(f"**Auditor Logic:**")
                                    st.markdown(f"<div class='thinking-box'>{data.get('thinking')}</div>", unsafe_allow_html=True)
                                    
                                    # 2. Show Answer and Status
                                    st.markdown(f"**Verdict:** {data['status']}")
                                    st.write(data['answer'])
                                    st.divider()
                                    st.caption(f"Cited Files: {', '.join(data['sources'])}")

                    status_box.success(f"Audit Complete! Processed {processed} requirements.")
                    
                    # Excel Export (Include Thinking in the report)
                    if results_data:
                        df = pd.DataFrame(results_data)
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False)
                        st.download_button("Download Full Audit Report (Excel)", output.getvalue(), "Compliance_Report.xlsx")
                else:
                    st.error(f"Server Error: {response.text}")

        except Exception as e:
            st.error(f"Connection Error: {e}")