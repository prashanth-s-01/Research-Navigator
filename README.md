# Research Navigator

Research Navigator is an AI-powered research paper assistant built with FastAPI, Streamlit, Docker, and Groq. It provides a modular architecture for PDF upload, document indexing, and question answering.

## Project Goals

- Accept PDF uploads
- Build hierarchical indexes with PageIndex
- Answer questions about documents
- Show retrieval traces
- Provide citation-aware answers
- Handle provider failures gracefully
- Deploy on Render

## Architecture

- Frontend: Streamlit
- Backend: FastAPI
- LLM Provider: Groq API
- Model: `llama-3.3-70b-versatile`
- Deployment: Docker / Docker Compose / Render

## Repository Structure

```
research-navigator/
├── docker-compose.yml
├── README.md
├── .env.example
├── shared/
│   ├── pdfs/
│   └── indexes/
├── frontend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   ├── api/
│   │   └── client.py
│   └── utils/
│       └── notifications.py
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── main.py
    ├── api/
    │   ├── health.py
    │   ├── upload.py
    │   └── query.py
    ├── services/
    │   ├── indexing_service.py
    │   ├── retrieval_service.py
    │   ├── llm_service.py
    │   └── storage_service.py
    ├── models/
    │   └── schemas.py
    ├── config/
    │   └── settings.py
    └── utils/
        ├── file_utils.py
        ├── logging_utils.py
        └── exception_handlers.py
```

## Local Development

1. Copy `.env.example` to `.env` and configure `GROQ_API_KEY`.
2. Start the app with:
   ```bash
   docker-compose up --build
   ```
3. Visit `http://localhost:8501` for the Streamlit frontend.
4. Use `http://localhost:8000/health` to confirm backend health.

## Render Deployment

Render can run the backend with:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

And the frontend with:

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

## Notes

This scaffold includes a production-style structure, containerized services, and a starter API with centralized error handling. PageIndex and Groq integration will be implemented in the next development phase.
