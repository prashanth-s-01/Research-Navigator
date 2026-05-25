import os
import pathlib
import tempfile
import streamlit as st
from api.client import BackendClientError, ask_question, health_check, upload_pdf
from utils.notifications import (
    show_error,
    show_info,
    show_retry_info,
    show_success,
    show_warning,
)

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))

st.set_page_config(page_title="Research Navigator", layout="wide", initial_sidebar_state="expanded")


def init_session_state() -> None:
    if "document_id" not in st.session_state:
        st.session_state.document_id = None
    if "upload_status" not in st.session_state:
        st.session_state.upload_status = None
    if "query_result" not in st.session_state:
        st.session_state.query_result = None
    if "notes" not in st.session_state:
        st.session_state.notes = []


def render_sidebar() -> None:
    with st.sidebar:
        st.header("Research Navigator")
        st.markdown("A Streamlit frontend for PageIndex + Groq retrieval.")
        st.markdown("---")
        st.markdown("**Backend URL**")
        st.code(BACKEND_URL)
        st.markdown("**Upload limit**")
        st.write(f"{MAX_UPLOAD_SIZE_MB} MB")
        st.markdown("---")
        st.info("Use the Upload section to submit a PDF, then ask questions in the Query section.")


def display_api_error(exc: BackendClientError) -> None:
    if exc.error_type in {"RATE_LIMIT", "TIMEOUT", "PROVIDER_DOWNTIME"}:
        show_error(exc.args[0])
        show_retry_info("The backend or Groq API is temporarily unavailable. Please try again in a few moments.")
    elif exc.error_type == "TOKEN_LIMIT_EXCEEDED":
        show_warning(exc.args[0])
        show_retry_info("Try a shorter question or upload a smaller document.")
    elif exc.error_type == "INVALID_API_KEY":
        show_error(exc.args[0])
        show_info("Check your API key configuration in the backend environment.")
    elif exc.error_type in {"INVALID_FILE_TYPE", "INVALID_PDF_FORMAT", "EMPTY_FILE", "FILE_TOO_SMALL", "FILE_TOO_LARGE"}:
        show_warning(exc.args[0])
    elif exc.error_type in {"METADATA_NOT_FOUND", "INDEX_NOT_AVAILABLE", "PAGEINDEX_TREE_TIMEOUT"}:
        show_warning(exc.args[0])
        show_retry_info("The document index is still being prepared. Please wait a moment and ask again.")
    else:
        show_error(exc.args[0])


def render_trace(trace_data) -> None:
    if not trace_data:
        st.info("No trace available yet.")
        return

    if isinstance(trace_data, str):
        st.text(trace_data)
        return

    st.markdown("### Retrieval Trace")
    st.text("Root")
    for index, line in enumerate(trace_data, start=1):
        indent = "    " * index
        st.text(f"{indent}└── {line}")


def render_citations(citations) -> None:
    if not citations:
        st.info("No citations available yet.")
        return

    st.markdown("### Citations")
    for citation in citations:
        section = citation.get("section", "Unknown section")
        page = citation.get("page")
        label = f"- **{section}**"
        if page is not None:
            label += f", page {page}"
        st.write(label)


def render_answer(answer_text: str) -> None:
    st.markdown("### Answer")
    if answer_text and answer_text.strip():
        st.write(answer_text)
    else:
        show_info("No answer could be generated from the retrieved document context.")


def upload_section() -> None:
    with st.expander("Upload a PDF", expanded=True):
        st.write("Upload a PDF to build a document index and start asking questions.")
        with st.form("upload_form"):
            uploaded_file = st.file_uploader("Select a PDF file", type=["pdf"])
            uploaded_button = st.form_submit_button("Upload PDF")

        if uploaded_button:
            if uploaded_file is None:
                show_warning("Please select a PDF file before uploading.")
                return
            if uploaded_file.type != "application/pdf":
                show_warning("Only PDF files are supported. Please upload a valid PDF.")
                return
            if uploaded_file.size == 0:
                show_warning("The selected file is empty. Please upload a valid PDF.")
                return
            if uploaded_file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
                show_warning(f"The selected file is too large. Maximum size is {MAX_UPLOAD_SIZE_MB} MB.")
                return

            temp_dir = pathlib.Path(tempfile.gettempdir())
            temp_path = temp_dir / uploaded_file.name
            temp_path.write_bytes(uploaded_file.getbuffer())

            try:
                with st.spinner("Uploading PDF and creating document index..."):
                    result = upload_pdf(str(temp_path))
                document_id = result.get("document_id")
                if document_id:
                    st.session_state.document_id = result.get("document_id")
                    st.session_state.upload_status = result.get("message", "Upload succeeded.")
                    st.session_state.query_result = None
                    show_success(st.session_state.upload_status)
                else:
                    show_warning(result.get("message", "Upload returned no success message."))
            except BackendClientError as exc:
                display_api_error(exc)

        if st.session_state.document_id:
            st.markdown("**Uploaded document:**")
            st.write(st.session_state.document_id)
            if st.session_state.upload_status:
                st.info(st.session_state.upload_status)


def query_section() -> None:
    with st.expander("Ask a question", expanded=True):
        st.write("Ask questions about the uploaded PDF and inspect the generated answer, trace, and citations.")
        document_id = st.session_state.document_id

        if not document_id:
            st.warning("Upload a PDF first to enable querying.")
            return

        with st.form("query_form"):
            question = st.text_area("Question", height=150)
            submit_question = st.form_submit_button("Ask Question")

        if submit_question:
            if not question or not question.strip():
                show_warning("Please enter a question before submitting.")
                return

            try:
                with st.spinner("Querying backend..."):
                    result = ask_question(document_id, question.strip())
                if result.get("success"):
                    st.session_state.query_result = result
                    show_success("Question answered successfully.")
                else:
                    show_warning(result.get("message", "No answer returned."))
            except BackendClientError as exc:
                display_api_error(exc)


def render_results() -> None:
    result = st.session_state.query_result
    if not result:
        return

    st.markdown("---")
    render_answer(result.get("answer", ""))
    render_trace(result.get("trace"))
    render_citations(result.get("citations", []))


def main() -> None:
    init_session_state()
    render_sidebar()

    st.header("Research Navigator")
    st.write("Upload PDFs, ask questions, and inspect retrieval traces and citations.")

    try:
        with st.spinner("Checking backend status..."):
            backend_status = health_check()
        show_success("Backend is reachable.")
        st.write("Backend status:", backend_status.get("status"))
        st.write("API version:", backend_status.get("version"))
    except BackendClientError as exc:
        display_api_error(exc)

    upload_section()
    query_section()
    render_results()


if __name__ == "__main__":
    main()
