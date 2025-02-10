import os
import requests
from requests_ntlm import HttpNtlmAuth
from transformers import AutoTokenizer, AutoModelForCausalLM
from PyPDF2 import PdfReader
import streamlit as st
import json
import warnings
from sentence_transformers import SentenceTransformer
import chromadb  # Importing ChromaDB
import torch
import datetime

warnings.filterwarnings("ignore")

# Error logging
ERROR_LOG_FILE = "error_log.txt"

def log_error(error_message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(ERROR_LOG_FILE, "a") as f:
        f.write(f"{timestamp}: {error_message}\n")

# SharePoint URL and credentials (REPLACE WITH YOUR ACTUAL VALUES)
SHAREPOINT_URL = "https://hclo365.sharepoint.com"
SITE_URL = "/sites/SONDocumentation"
DOCUMENT_LIBRARY_URL = "/Shared%20Documents"
USERNAME = "jatin.malhotra@hcl.com"
PASSWORD = "MiraMairaa321!"

# LLM model and tokenizer (For response generation)
LLM_MODEL_NAME = "google/flan-t5-xl"  # Or your preferred LLM
try:
    llm_tokenizer = AutoTokenizer.from_pretrained(LLM_MODEL_NAME)
    llm_model = AutoModelForCausalLM.from_pretrained(LLM_MODEL_NAME).to("cuda" if torch.cuda.is_available() else "cpu")
except Exception as e:
    log_error(f"Error loading LLM model: {e}")
    st.error("Error loading LLM. Check error logs.")
    st.stop()  # Stop Streamlit execution


# Embedding model
EMBEDDING_MODEL_NAME = "all-mpnet-base-v2"  # Or another good embedding model
try:
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
except Exception as e:
    log_error(f"Error loading embedding model: {e}")
    st.error("Error loading embedding model. Check error logs.")
    st.stop()

# Vector database (ChromaDB example)
chroma_client = chromadb.Client()
chroma_collection = chroma_client.create_collection(name="my_collection")

# Function to authenticate with SharePoint
def authenticate():
    auth = HttpNtlmAuth(USERNAME, PASSWORD)
    return auth

# Function to recursively get PDF files from SharePoint
def get_pdf_files(auth, folder_url=DOCUMENT_LIBRARY_URL):
    all_pdfs = []  # Corrected: Initialize as an empty list
    try:
        url = f"{SHAREPOINT_URL}{SITE_URL}{folder_url}/_api/web/GetFolderByServerRelativeUrl('{folder_url}')/Files"
        headers = {"Accept": "application/json;odata=verbose"}
        response = requests.get(url, auth=auth, headers=headers)
        response.raise_for_status()
        files = response.json()["d"]["results"]
        for file in files:
            if file["__metadata"]["type"] == "SP.File" and file["Name"].endswith(".pdf"):
                all_pdfs.append(file)

        # Get subfolders and recursively call get_pdf_files
        subfolder_url = f"{SHAREPOINT_URL}{SITE_URL}{folder_url}/_api/web/GetFolderByServerRelativeUrl('{folder_url}')/Folders"
        subfolder_response = requests.get(subfolder_url, auth=auth, headers=headers)
        subfolder_response.raise_for_status()
        subfolders = subfolder_response.json()["d"]["results"]
        for subfolder in subfolders:
            all_pdfs.extend(get_pdf_files(auth, subfolder["ServerRelativeUrl"]))

        return all_pdfs
    except requests.exceptions.RequestException as e:
        log_error(f"Error accessing SharePoint: {e}")
        return [] # Return empty list in case of errors
    except (json.JSONDecodeError, KeyError) as e:
        log_error(f"Error processing SharePoint response: {e}")
        return [] # Return empty list in case of errors

# Function to read PDF file contents
def read_pdf_contents(pdf_file):
    try:
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        log_error(f"Error reading PDF: {e}")
        return ""

# Function to chunk text
def chunk_text(text, chunk_size=500, overlap=50):
    chunks = []  # Corrected: Initialize as an empty list
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

# Function to embed and add to vector database
def embed_and_add(text_chunks):
    for chunk in text_chunks:
        embedding = embedding_model.encode(chunk).tolist()
        chroma_collection.add(documents=[chunk], embeddings=[embedding])

# Function to query the vector database
def query_database(query, k=5):  # k = number of similar chunks to retrieve
    query_embedding = embedding_model.encode(query).tolist()
    results = chroma_collection.query(query_embeddings=[query_embedding], n_results=k)
    return [res["document"] for res in results["documents"]]

# Function to generate response (with error handling)
def generate_response(query, context):
    try:
        prompt = f"Context:\n{context}\n\nQuestion:\n{query}\n\nAnswer:"
        inputs = llm_tokenizer(prompt, return_tensors="pt").to(llm_model.device)  # Ensure input is on same device as model
        outputs = llm_model.generate(**inputs, max_new_tokens=200)  # Adjust max_new_tokens
        response = llm_tokenizer.decode(outputs, skip_special_tokens=True)
        return response
    except Exception as e:
        log_error(f"Error generating response: {e}")
        return "Error generating response. Check error logs."

# Streamlit app
st.title("PDF Search and Analysis")

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Get user input
user_input = st.text_input("Enter your query:", "")

# Process user input
if st.button("Submit"):
    try:
        auth = authenticate()
        pdf_files = get_pdf_files(auth)

        if pdf_files:
            all_text_chunks = []  # List to hold all chunks from all PDFs
            for pdf_file in pdf_files:
                try: # Try to read each file, handle errors gracefully
                    pdf_contents = read_pdf_contents(pdf_file)
                    if pdf_contents:
                        text_chunks = chunk_text(pdf_contents)
                        all_text_chunks.extend(text_chunks)  # Add chunks to the list
                except Exception as e:
                    log_error(f"Error processing a PDF file: {e}")
                    st.write(f"Error processing a PDF file: {e}")
