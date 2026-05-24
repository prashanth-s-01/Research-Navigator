import streamlit as st


def show_error(message: str) -> None:
    st.error(message)


def show_warning(message: str) -> None:
    st.warning(message)


def show_success(message: str) -> None:
    st.success(message)


def show_retry_info(message: str) -> None:
    st.info(f"Retry guidance: {message}")
