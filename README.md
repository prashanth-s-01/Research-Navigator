# Research Navigator

Research Navigator is a Streamlit + FastAPI app for uploading research PDFs, building PageIndex document indexes, and asking citation-aware questions with Groq-generated answers.

## Current Capabilities

- Upload PDF files from the Streamlit UI.
- Enforce a 10 MB upload limit in both frontend and backend validation.
- Save uploaded PDFs under `shared/pdfs/`.
- Start PageIndex indexing automatically after the upload request succeeds.
- Persist index artifacts under `shared/indexes/<document_id>/`.
- Ask questions against an indexed document.
- Generate answers with Groq using retrieved PageIndex context.
- Show answer text, retrieval trace, and citations in the frontend.
- Surface backend validation and provider errors with user-facing retry guidance.

## User Flow

1. Open the frontend at `http://localhost:8501`.
2. Choose a PDF in the upload form.
3. Press **Upload PDF**.
4. The frontend sends the file to `POST /upload/pdf`.
5. The backend validates and saves the PDF, then schedules PageIndex indexing in the background.
6. The frontend stores the returned `document_id` and enables the question form.
7. Ask a question once indexing has completed.

Indexing is not triggered when a PDF is merely selected in the file picker. It starts only after the **Upload PDF** button submits the file. If a question is asked before indexing finishes, the backend may return an index-not-ready error such as `METADATA_NOT_FOUND`.

## Architecture

- Frontend: Streamlit
- Backend: FastAPI
- Indexing and retrieval: PageIndex
- Answer generation: Groq
- Default Groq model: `llama-3.3-70b-versatile`
- Local runtime: Docker Compose
- Shared storage: `./shared` mounted into backend and frontend containers

## API Endpoints

- `GET /health`
  - Returns backend status and API version.
- `POST /upload/pdf`
  - Accepts a PDF multipart upload.
  - Returns `document_id`, original filename, byte size, status, and message.
  - Starts background indexing after saving the file.
- `POST /query/`
  - Accepts `document_id` and `question`.
  - Returns `success`, `answer`, `trace`, and `citations`.

## Repository Structure

```text
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
    │   ├── prompt_utils.py
    │   └── storage_service.py
    ├── models/
    │   └── schemas.py
    ├── config/
    │   └── settings.py
    └── utils/
        ├── exception_handlers.py
        ├── file_utils.py
        ├── logging_utils.py
        └── retry_utils.py
```

## Local Development

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Configure required API keys in `.env`:

   ```text
   GROQ_API_KEY=...
   PAGEINDEX_API_KEY=...
   ```

3. Start the app:

   ```bash
   docker compose up --build
   ```

4. Open the Streamlit frontend:

   ```text
   http://localhost:8501
   ```

5. Check backend health:

   ```text
   http://localhost:8000/health
   ```

## Configuration

Important environment variables:

- `GROQ_API_KEY`: required for answer generation.
- `PAGEINDEX_API_KEY`: required for indexing and retrieval.
- `GROQ_MODEL`: defaults to `llama-3.3-70b-versatile`.
- `PAGEINDEX_MODE`: defaults to `mcp`.
- `PAGEINDEX_POLL_ATTEMPTS`: defaults to `20`.
- `PAGEINDEX_POLL_INTERVAL_SECONDS`: defaults to `2`.
- `MAX_UPLOAD_SIZE_MB`: defaults to `10`.
- `STORAGE_PATH`: defaults to `/app/shared` in the backend container.

Docker Compose sets `MAX_UPLOAD_SIZE_MB=10` for the backend container so backend validation matches the frontend limit.

## Storage Artifacts

Uploaded PDFs are saved as:

```text
shared/pdfs/<document_id>.pdf
```

Indexing artifacts are saved as:

```text
shared/indexes/<document_id>/
├── status.json
├── metadata.json
├── tree.json
├── summaries.json
└── raw_tree.json
```

Failed or in-progress indexing may only have `status.json`. A completed index should include `metadata.json`, which contains the PageIndex document identifier used during querying.

## Troubleshooting

- `InsufficientCredits`
  - PageIndex rejected indexing because the configured account lacks credits. Refill credits or switch `PAGEINDEX_API_KEY`, then re-upload or rerun indexing.
- `METADATA_NOT_FOUND`
  - The document was uploaded, but indexing has not completed or failed before metadata was written.
- `FILE_TOO_LARGE`
  - The uploaded PDF exceeds the 10 MB limit.
- `INVALID_PDF_FORMAT`
  - The file extension or PDF signature validation failed.

Backend logs are available with:

```bash
docker compose logs backend
```

Frontend logs are available with:

```bash
docker compose logs frontend
```

## Deployment Notes

The backend can be run with:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The frontend can be run with:

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

For non-Docker deployments, make sure the frontend `BACKEND_URL` points at the deployed backend and both services can access compatible storage if shared artifacts are required.
