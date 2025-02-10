!pip install requests_ntlm
!pip install PyPDF2
!pip install transformers
!pip install streamlit

import os
import requests
from requests_ntlm import HttpNtlmAuth
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from PyPDF2 import PdfReader
import streamlit as st

# SharePoint URL and credentials
SHAREPOINT_URL = "https://hclo365.sharepoint.com"
SITE_URL = "/sites/SONDocumentation"
DOCUMENT_LIBRARY_URL = "/Shared%20Documents"
USERNAME = "jatin.malhotra@hcl.com"
PASSWORD = "MiraMairaa321!"

# LLM model and tokenizer
MODEL_NAME = "bert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

# Function to authenticate with SharePoint
def authenticate():
    auth = HttpNtlmAuth(USERNAME, PASSWORD)
    return auth

# Function to get PDF files from SharePoint document library
def get_pdf_files(auth):
    url = f"{SHAREPOINT_URL}{SITE_URL}{DOCUMENT_LIBRARY_URL}/_api/web/GetFolderByServerRelativeUrl('{DOCUMENT_LIBRARY_URL}')/Files"
    headers = {"Accept": "application/json;odata=verbose"}
    response = requests.get(url, auth=auth, headers=headers)
    files = response.json()["d"]["results"]
    pdf_files = [file for file in files if file["__metadata"]["type"] == "SP.File" and file["Name"].endswith(".pdf")]
    return pdf_files

# Function to read PDF file contents using LLM
def read_pdf_contents(pdf_file):
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    inputs = tokenizer(text, return_tensors="pt")
    outputs = model(**inputs)
    return outputs.last_hidden_state[:, 0, :]

# Streamlit app
st.title("PDF Search and Analysis")

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Get user input
user_input = st.text_input("Enter your query:", "")

# Process user input
if st.button("Submit"):
    auth = authenticate()
    pdf_files = get_pdf_files(auth)
    for pdf_file in pdf_files:
        pdf_contents = read_pdf_contents(pdf_file)
        st.session_state.chat_history.append({"user": user_input, "response": str(pdf_contents)})

# Display chat history
st.write("Chat History:")
for chat in st.session_state.chat_history:
    st.write(f"User: {chat['user']}")
    st.write(f"Response: {chat['response']}")
    st.write("")
