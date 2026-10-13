from langgraph_workflow import build_agent
from langgraph_workflow import build_agent
import os
import streamlit as st
import torch

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

# Optional LangSmith tracing via Streamlit Secrets
if "LANGSMITH_API_KEY" in st.secrets:
    os.environ["LANGSMITH_API_KEY"] = st.secrets["LANGSMITH_API_KEY"]
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = "Financial-RAG-Agent"

st.set_page_config(
    page_title="AI Financial Advisor",
    page_icon="📊",
    layout="wide"
)

st.title("📊 AI Financial Advisor Agent")
st.caption(
    "A retrieval-augmented financial assistant powered by "
    "Hugging Face, FAISS, and LangGraph."
)

st.info(
    "Demonstration only: ACME Renewable Energy is a fictional company. "
    "This prototype is not a substitute for professional financial advice."
)

REPORT = """
ACME Renewable Energy - Fictional Annual Report

For FY 2025-26, company revenue was INR 120 crore.
For FY 2024-25, company revenue was INR 100 crore.
Operating expenses were INR 78 crore.
Operating profit was INR 42 crore.
Total debt was INR 50 crore.

The main business risks include changing government policies,
project delays, and equipment cost fluctuations.

The report does not specify the number of employees.
"""

@st.cache_resource(show_spinner="Loading financial report and search index...")
def build_retriever():
    document = Document(
        page_content=REPORT,
        metadata={"source": "ACME_Fictional_Annual_Report"}
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=350,
        chunk_overlap=50
    )
    chunks = splitter.split_documents([document])

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vector_store = FAISS.from_documents(chunks, embeddings)
    return vector_store.as_retriever(search_kwargs={"k": 3})


@st.cache_resource(show_spinner="Loading answer-generation model...")
def load_model():
    name = "google/flan-t5-small"
    tokenizer = AutoTokenizer.from_pretrained(name)
    model = AutoModelForSeq2SeqLM.from_pretrained(name)
    model.eval()
    return tokenizer, model


retriever = build_retriever()
tokenizer, model = load_model()
agent = build_agent(retriever, tokenizer, model)

st.subheader("Ask the financial report")

question = st.text_input(
    "Your question",
    placeholder="Example: What was the revenue in FY 2025-26?"
)

examples = [
    "What was the revenue in FY 2025-26?",
    "What was the total debt?",
    "What were the operating expenses?",
    "What are the main business risks?",
    "How many employees does the company have?"
]

with st.expander("Try a sample question"):
    st.write("\n".join(f"• {q}" for q in examples))

if st.button("Ask the AI Agent", type="primary"):
    if not question.strip():
        st.warning("Please enter a question first.")
    else:
        try:
            with st.spinner("Analyzing the financial report..."):
                result = agent.invoke({"question": question})

            st.subheader("Agent's Answer")
            st.write(result.get("answer", "No answer returned."))

            if result.get("sources"):
                st.caption(
                    "Source: " + ", ".join(result["sources"])
                )

            with st.expander("View retrieved evidence"):
                st.write(result.get("context", ""))
        except Exception as exc:
            st.error(
                "The app encountered an error. Please retry. "
                "If the problem persists, check the app logs."
            )
            st.exception(exc)
