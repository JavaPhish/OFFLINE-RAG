# Local RAG Frontend (React + Vite)

Quick start (from repo root):

1. Change to the frontend folder and install deps:

```bash
cd frontend
npm install
```

2. Start dev server (defaults to http://localhost:5173):

```bash
npm run dev
```

3. Use the UI to send queries to the FastAPI backend at `http://127.0.0.1:8000/query` (ensure backend is running).

Notes:
- If the backend requires an API token, fill it in the UI token field.
- The UI is intentionally minimal — feel free to extend it to add uploads or local file browsing.
