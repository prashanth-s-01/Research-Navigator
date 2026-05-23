import os
import streamlit as st
from api.client import health_check, upload_pdf, ask_question, BackendClientError
from utils.notifications import show_error, show_success, show_warning

st.set_page_config(page_title="Research Navigator", layout="wide")
st.title("Research Navigator")

backend_status = None
try:
    backend_status = health_check()
except BackendClientError as exc:
    show_error(str(exc))

if backend_status:
    st.write("Backend status:", backend_status.get("status"))
    st.write("API version:", backend_status.get("version"))

with st.expander("Upload a PDF", expanded=True):
    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])
    if uploaded_file is not None:
        temp_path = os.path.join("/tmp", uploaded_file.name)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        try:
            result = upload_pdf(temp_path)
            if result.get("success"):
                show_success(result.get("message", "Upload succeeded."))
                st.session_state.document_id = result.get("document_id")
            else:
                show_warning(result.get("message", "Upload returned no success message."))
        except BackendClientError as exc:
            show_error(str(exc))

st.markdown("---")

st.subheader("Ask a question")
question = st.text_area("Enter your question about the uploaded document:")
submitted = st.button("Ask question")

document_id = st.session_state.get("document_id") if "document_id" in st.session_state else None
if document_id:
    st.info(f"Using document ID: {document_id}")
else:
    st.warning("Upload a PDF first to generate a document ID.")

if submitted:
    if not document_id:
        show_warning("Please upload a PDF before asking a question.")
    elif not question.strip():
        show_warning("Please enter a question.")
    else:
        try:
            answer = ask_question(document_id, question)
            if answer.get("success"):
                st.markdown("### Answer")
                st.write(answer.get("answer"))
                st.markdown("### Citations")
                st.write(answer.get("citations") or "No citations available yet.")
                st.markdown("### Retrieval Trace")
                st.text(answer.get("trace") or "No trace available yet.")
            else:
                show_warning(answer.get("answer", "No answer returned."))
        except BackendClientError as exc:
            show_error(str(exc))
