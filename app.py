import streamlit as st
import os
import requests
import tempfile
import base64
from urllib.parse import urlparse

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain_community.llms import Ollama
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv

# Load environment variables (for OLLAMA_BASE_URL if needed)
load_dotenv()

# --- Configuration ---
# Directory to store downloaded PDFs
PDF_DOWNLOAD_DIR = "downloaded_pdfs"
os.makedirs(PDF_DOWNLOAD_DIR, exist_ok=True)

# ChromaDB persistence directory
CHROMA_DB_DIR = "chroma_db"

# Pre-defined PDF links
PREDEFINED_PDF_LINKS = {
    "Dell": [
        "https://i.dell.com/sites/csdocuments/Product_Docs/en/Dell-EMC-PowerEdge-Rack-Servers-Quick-Reference-Guide.pdf",
        "https://www.delltechnologies.com/asset/en-us/products/servers/technical-support/poweredge-r660xs-technical-guide.pdf",
        "https://i.dell.com/sites/csdocuments/shared-content_data-sheets_documents/en/aa/poweredge_r740_r740xd_technical_guide.pdf",
        "https://dl.dell.com/topicspdf/openmanage-server-administrator-v95_users-guide_en-us.pdf",
        "https://dl.dell.com/manuals/common/dellemc-server-config-profile-refguide.pdf",
    ],
    "IBM": [
        "https://www.redbooks.ibm.com/redbooks/pdfs/sg248513.pdf",
        "https://www.ibm.com/docs/SSLVMB_28.0.0/pdf/IBM_SPSS_Statistics_Server_Administrator_Guide.pdf",
        "https://public.dhe.ibm.com/software/webserver/appserv/library/v60/ihs_60.pdf",
        "https://www.ibm.com/docs/en/storage-protect/8.1.25?topic=pdf-files",
    ],
    "Cisco": [
        "https://www.cisco.com/c/dam/global/shared/assets/pdf/cisco_enterprise_campus_infrastructure_design_guide.pdf",
        "https://www.cisco.com/c/dam/en_us/about/ciscoitatwork/downloads/ciscoitatwork/pdf/Cisco_IT_Wireless_LAN_Design_Guide.pdf",
        "https://www.cisco.com/c/dam/en_us/about/ciscoitatwork/downloads/ciscoitatwork/pdf/Cisco_IT_IP_Addressing_Best_Practices.pdf",
        "https://www.cisco.com/c/en/us/td/docs/net_mgmt/network_registrar/7-2/user/guide/cnr72book.pdf",
    ],
    "Juniper": [
        "https://www.juniper.net/documentation/us/en/software/junos/junos-overview/junos-overview.pdf",
        "https://archive.org/download/junos-srxsme/JunOS%20SRX%20Documentation%20Set/network-management.pdf",
        "https://csrc.nist.gov/CSRC/media/projects/cryptographic-module-validation-program/documents/security-policies/140sp3779.pdf",
    ],
    "Fortinet (FortiGate)": [
        "https://fortinetweb.s3.amazonaws.com/docs.fortinet.com/v2/attachments/b94274f8-1a11-11e9-9685-f8bc1258b856/FortiOS-5.6-Firewall.pdf",
        "https://docs.fortinet.com/document/fortiweb/6.0.7/administration-guide-pdf",
        "https://www.andovercg.com/datasheets/fortigate-fortinet-200.pdf",
        "https://www.commoncriteriaportal.org/files/epfiles/Fortinet%20FortiGate_EAL4_ST_V1.5.pdf",
    ],
    "EUC": [
        "https://www.dell.com/en-us/lp/dt/end-user-computing", # This is a webpage, not a PDF. Will be skipped.
        "https://www.nutanix.com/solutions/end-user-computing", # This is a webpage, not a PDF. Will be skipped.
        "https://eucscore.com/docs/tools.html", # This is a webpage, not a PDF. Will be skipped.
        "https://apparity.com/euc-resources/spreadsheet-euc-documents/", # This is a webpage, not a PDF. Will be skipped.
    ],
}

# --- Helper Functions ---

def download_pdf(url, output_path):
    """Downloads a PDF from a given URL to the specified output path."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        st.success(f"Downloaded: {os.path.basename(output_path)}")
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error downloading {url}: {e}")
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred while downloading {url}: {e}")
        return False

def load_and_split_pdf(file_path):
    """Loads a PDF and splits it into text chunks."""
    try:
        loader = PyPDFLoader(file_path)
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        texts = text_splitter.split_documents(documents)
        st.success(f"Processed {len(texts)} chunks from {os.path.basename(file_path)}")
        return texts
    except Exception as e:
        st.error(f"Error processing PDF {os.path.basename(file_path)}: {e}")
        return []

@st.cache_resource
def get_ollama_embeddings():
    """Initializes and caches OllamaEmbeddings."""
    # Ensure Ollama is running and the model (e.g., "nomic-embed-text") is pulled.
    # If OLLAMA_BASE_URL is set, it will connect to that URL.
    # Otherwise, it defaults to http://localhost:11434
    return OllamaEmbeddings(model="nomic-embed-text") # You might need to change this model based on what you have pulled

@st.cache_resource
def get_ollama_llm():
    """Initializes and caches Ollama LLM."""
    # Ensure Ollama is running and the model (e.g., "llama2") is pulled.
    # If OLLAMA_BASE_URL is set, it will connect to that URL.
    # Otherwise, it defaults to http://localhost:11434
    return Ollama(model="llama2") # You might need to change this model based on what you have pulled

def initialize_vector_store(documents, embeddings):
    """Initializes or updates the Chroma vector store."""
    if documents:
        # If vector store already exists, add documents to it
        if 'vector_store' in st.session_state and st.session_state.vector_store is not None:
            st.session_state.vector_store.add_documents(documents)
            st.info("Added new documents to existing vector store.")
        else:
            # Create a new vector store
            st.session_state.vector_store = Chroma.from_documents(
                documents=documents,
                embedding=embeddings,
                persist_directory=CHROMA_DB_DIR
            )
            st.info("Created new vector store.")
        st.session_state.vector_store.persist()
        st.success("Vector store updated successfully!")
    else:
        st.warning("No documents to add to the vector store.")

def get_rag_chain(vector_store, llm):
    """Creates the RAG conversational chain with memory."""
    if vector_store is None:
        st.error("Vector store is not initialized. Please upload documents first.")
        return None

    # Initialize chat history in session state if not present
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Use ConversationBufferMemory for chat history
    memory = ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        output_key='answer'
    )

    # Load existing chat history into memory
    for message in st.session_state.chat_history:
        if message["role"] == "user":
            memory.chat_memory.add_user_message(message["content"])
        else:
            memory.chat_memory.add_ai_message(message["content"])

    conversation_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vector_store.as_retriever(),
        memory=memory,
        return_source_documents=True,
        return_generated_question=True,
    )
    return conversation_chain

def display_pdf(file_path):
    """Displays a PDF file in the Streamlit app using base64 encoding."""
    try:
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="700px" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Could not display PDF: {e}")

# --- Streamlit UI ---
st.set_page_config(layout="wide", page_title="RAG Application with PDF Viewer")

st.title("📄 RAG Application with Document Chat")

# Initialize session state for messages and vector store
if "messages" not in st.session_state:
    st.session_state.messages = []
if "vector_store" not in st.session_state:
    st.session_state.vector_store = None
if "pdf_display_path" not in st.session_state:
    st.session_state.pdf_display_path = None

# Initialize LLM and Embeddings once
try:
    embeddings = get_ollama_embeddings()
    llm = get_ollama_llm()
except Exception as e:
    st.error(f"Failed to initialize Ollama. Please ensure Ollama is running and the models are pulled. Error: {e}")
    st.stop() # Stop the app if Ollama cannot be initialized

# Sidebar for document upload and ingestion
with st.sidebar:
    st.header("Upload Documents & Ingest Data")

    # File Uploader
    uploaded_files = st.file_uploader(
        "Upload PDF files for RAG",
        type="pdf",
        accept_multiple_files=True,
        key="pdf_uploader"
    )

    if uploaded_files:
        if st.button("Process Uploaded PDFs"):
            all_new_docs = []
            for uploaded_file in uploaded_files:
                # Save uploaded file to a temporary location
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    temp_file_path = tmp_file.name
                
                # Process the PDF
                new_docs = load_and_split_pdf(temp_file_path)
                all_new_docs.extend(new_docs)
                
                # Optionally display the first uploaded PDF
                if not st.session_state.pdf_display_path:
                    st.session_state.pdf_display_path = temp_file_path
                
                # Clean up the temporary file
                # os.remove(temp_file_path) # Keep for display if needed, clean up later or on exit

            if all_new_docs:
                initialize_vector_store(all_new_docs, embeddings)
                st.success("All uploaded PDFs processed and added to the knowledge base!")
            else:
                st.warning("No new documents were extracted from uploaded PDFs.")

    st.markdown("---")
    st.subheader("Pre-fed Database Ingestion")
    
    selected_company = st.selectbox("Select a company to ingest documents:", 
                                    [""] + list(PREDEFINED_PDF_LINKS.keys()))

    if st.button("Ingest Pre-defined Documents"):
        if selected_company:
            st.info(f"Ingesting documents for {selected_company}...")
            all_ingested_docs = []
            for url in PREDEFINED_PDF_LINKS[selected_company]:
                # Check if it's a PDF link
                if url.lower().endswith(".pdf"):
                    file_name = os.path.basename(urlparse(url).path)
                    output_path = os.path.join(PDF_DOWNLOAD_DIR, file_name)
                    if download_pdf(url, output_path):
                        docs = load_and_split_pdf(output_path)
                        all_ingested_docs.extend(docs)
                        # Set the first successfully downloaded PDF for display
                        if not st.session_state.pdf_display_path:
                            st.session_state.pdf_display_path = output_path
                else:
                    st.warning(f"Skipping non-PDF link: {url}")
            
            if all_ingested_docs:
                initialize_vector_store(all_ingested_docs, embeddings)
                st.success(f"All documents for {selected_company} ingested successfully!")
            else:
                st.warning(f"No PDF documents found or successfully ingested for {selected_company}.")
        else:
            st.warning("Please select a company to ingest documents.")

# Main content area: PDF Viewer and Chat Interface
col1, col2 = st.columns([0.6, 0.4]) # Adjust column width as needed

with col1:
    st.subheader("MANISH SINGH-PDF Viewer")
    if st.session_state.pdf_display_path:
        display_pdf(st.session_state.pdf_display_path)
    else:
        st.info("Upload a PDF or ingest pre-defined documents to view it here.")

with col2:
    st.subheader("Chat with your Documents")

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("Ask a question about the documents..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if st.session_state.vector_store is None:
                st.warning("Please upload or ingest documents first to enable chat functionality.")
                st.session_state.messages.append({"role": "assistant", "content": "Please upload or ingest documents first to enable chat functionality."})
            else:
                with st.spinner("Thinking..."):
                    qa_chain = get_rag_chain(st.session_state.vector_store, llm)
                    if qa_chain:
                        try:
                            response = qa_chain({"question": prompt})
                            ai_response = response["answer"]
                            st.markdown(ai_response)
                            st.session_state.messages.append({"role": "assistant", "content": ai_response})

                            # Optionally display sources
                            if response.get("source_documents"):
                                st.markdown("---")
                                st.markdown("**Sources:**")
                                for i, doc in enumerate(response["source_documents"]):
                                    # Try to get the file path from metadata or just show content
                                    source_info = doc.metadata.get('source', 'Unknown source')
                                    page_info = doc.metadata.get('page', 'N/A')
                                    st.markdown(f"- **Source {i+1}:** {source_info}, Page: {page_info}")
                                    # st.markdown(f"  Snippet: {doc.page_content[:200]}...") # Uncomment to show snippets
                        except Exception as e:
                            st.error(f"Error during RAG chain execution: {e}")
                            st.session_state.messages.append({"role": "assistant", "content": f"An error occurred: {e}"})
                    else:
                        st.session_state.messages.append({"role": "assistant", "content": "RAG chain could not be initialized."})

