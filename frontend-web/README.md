# ClaimLens AI — Web Frontend (React / TypeScript)

Frontend for the **synthetic/local demonstration only**.

## Development mode


Start the FastAPI backend from the repository root in a first terminal, after setting up the Python environment and initializing the synthetic corpus:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, start the React development server:

```powershell
cd frontend-web
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/health` and `/analysis` to the local FastAPI backend; this avoids permissive CORS settings.

## Production build

From the frontend-web/ directory, build the application:

```powershell
npm run build
```

Return to the repository root with cd .., then start FastAPI using the command shown above. The compiled React application will be served by FastAPI on the same origin as the API.If `frontend-web/dist/` exists, FastAPI serves the compiled frontend at `http://127.0.0.1:8000/`, so **only one server** is required for the demo.

The frontend never makes an indemnification decision itself. It displays a deterministic, conservative backend assessment, sources, and pending questions.

## Limitations

The deterministic rule catalogue covers two limited claim families (bicycle theft and candle-related damage) across three synthetic policy editions, with selected negative and causal counterexamples. It is **not** a general insurance decision engine or production-deployable authenticated service. The server may be resource-heavy because of Docling/transformer model dependencies.
