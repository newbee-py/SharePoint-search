import os
import requests
from requests_ntlm import HttpNtlmAuth
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from PyPDF2 import PdfReader
import streamlit as st
import json
import warnings

warnings.filterwarnings("ignore")

# SharePoint URL and credentials (REPLACE WITH YOUR ACTUAL VALUES)
SHAREPOINT_URL = "https://hclo365.sharepoint.com"
SITE_URL = "/sites/SONDocumentation"
DOCUMENT_LIBRARY_URL = "/Shared%20Documents"
USERNAME = "jatin.malhotra@hcl.com"
PASSWORD = "MiraMairaa321!"

# LLM model and tokenizer (REPLACE WITH YOUR FINE-TUNED MODEL PATH)
MODEL_PATH = "path/to/save/your/model"  # Path to your fine-tuned BERT model
MODEL_NAME = "bert-base-uncased" # Only used if no MODEL_PATH
try:
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
except:
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

# Function to authenticate with SharePoint
def authenticate():
    auth = HttpNtlmAuth(USERNAME, PASSWORD)
    return auth

# Function to get PDF files from SharePoint document library
def get_pdf_files(auth):
    url = f"{SHAREPOINT_URL}{SITE_URL}{DOCUMENT_LIBRARY_URL}/_api/web/GetFolderByServerRelativeUrl('{DOCUMENT_LIBRARY_URL}')/Files"
    headers = {"Accept": "application/json;odata=verbose"}
    try:
        response = requests.get(url, auth=auth, headers=headers)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        files = response.json()["d"]["results"]
        pdf_files = [file for file in files if file["__metadata"]["type"] == "SP.File" and file["Name"].endswith(".pdf")]
        return pdf_files
    except requests.exceptions.RequestException as e:
        print(f"Error accessing SharePoint: {e}")
        return []
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error processing SharePoint response: {e}")
        return []

# Function to read PDF file contents
def read_pdf_contents(pdf_file):
    try:
        pdf_reader = PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

# Function to process user query (REPLACE WITH YOUR ACTUAL LOGIC)
def process_query(text, query):
    try:
        inputs = tokenizer(query, text, return_tensors="pt", truncation=True, padding=True)
        outputs = model(**inputs)
        # Example for sentiment analysis (adapt as needed):
        predicted_class = outputs.logits.argmax().item()
        return predicted_class  # Or the corresponding sentiment label, etc.
    except Exception as e:
        print(f"Error processing query: {e}")
        return "Error processing query."  # Or some other appropriate error message

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
    if pdf_files: # Check if any PDF files were retrieved
        for pdf_file in pdf_files:
            pdf_contents = read_pdf_contents(pdf_file)
            if pdf_contents: # Check if PDF content was extracted
                result = process_query(pdf_contents, user_input)
                st.session_state.chat_history.append({"user": user_input, "response": str(result)})
            else:
                st.write(f"Could not read content from: {pdf_file.get('Name', 'Unknown file')}")
    else:
        st.write("No PDF files found in the specified SharePoint folder.")


# Display chat history
st.write("Chat History:")
for chat in st.session_state.chat_history:
    st.write(f"User: {chat['user']}")
    st.write(f"Response: {chat['response']}")
    st.write("")
