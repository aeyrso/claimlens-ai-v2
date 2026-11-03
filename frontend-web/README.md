# ClaimLens AI — Web Frontend (React / TypeScript)

Frontend for the **synthetic/local demonstration only**.

## Development mode

Start the FastAPI backend on `127.0.0.1:8000` from the repository root.

```powershell
cd frontend-web
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/health` and `/analysis` to the local FastAPI backend; this avoids permissive CORS settings.

## Production build

```powershell
npm run build
```

Then start FastAPI from the repository root. If `frontend-web/dist/` exists, FastAPI serves the compiled frontend at `http://127.0.0.1:8000/`, so **only one server** is required for the demo.

The frontend never makes an indemnification decision itself. It displays a deterministic, conservative backend assessment, sources, and pending questions.

## Limitations

The deterministic rule catalogue only covers two scenarios across three synthetic policy editions. It is **not** a general insurance decision engine or production-deployable authenticated service. The server may be resource-heavy because of Docling/transformer model dependencies.
