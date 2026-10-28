# Image-to-Excel AI Agent

Extract text from document images using local OCR (PaddleOCR) or cloud AI Vision (Google Gemini), structure fields with configurable AI providers, review results in a Streamlit UI, and export to Excel.

**Current status:** Stage 6 — Streamlit UI (upload, review, export).

## Requirements

- **Python 3.11 or 3.12** (recommended). PaddleOCR and related wheels may not support 3.14 yet; use a 3.12 venv for full development.
- Windows, macOS, or Linux.

## Quick start (Stage 1)

```powershell
cd E:\mani-projects\image-to-excel-agent
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
copy .env.example .env
# Edit .env with your API keys (never commit .env)
pytest
```

If you do not install the package in editable mode, run:

```powershell
$env:PYTHONPATH = "src"
pytest
```

## Environment variables

See [.env.example](.env.example). API keys are read only from the environment; they are never shown in the UI or written to Excel.

## Project layout

```
src/
  app.py              # Streamlit entry (Stage 6)
  config.py           # Settings via pydantic-settings
  models/document.py  # Documents, schemas, extraction results
  utils/fingerprints.py
tests/
```

### PaddleOCR on Windows

PaddleOCR needs **paddlepaddle**, which currently ships wheels for **Python 3.11–3.12** (not 3.14):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements.txt
pip install -e .
# If Paddle fails on Windows only: pip install protobuf==3.20.2 --force-reinstall
pytest
```

Unit tests use a fake OCR engine and do not require paddlepaddle. Optional integration test:

```powershell
pytest -m integration
```

## Run the app (Stage 6)

```powershell
cd E:\mani-projects\image-to-excel-agent
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
copy .env.example .env
# Set GEMINI_API_KEY and/or GROQ_API_KEY
# Local OCR uses PaddleOCR (Python 3.11–3.12). Cloud OCR uses Gemini Vision directly.
streamlit run src/app.py
```

Tabs: **Upload & process** (OCR Engine: Auto / Gemini Vision / PaddleOCR), **Review & edit**, **Export** (new/append Excel with overwrite confirmation).

## Deploy free on Streamlit Community Cloud

**Important:** PaddlePaddle needs **Python 3.11 or 3.12**. Community Cloud may default to **3.14**, which breaks install. You must pick **3.12** (or 3.11) in the deploy UI — `.python-version` alone is **not** enough.

1. Push this repo to GitHub (`.env` must **not** be committed).
2. Open [share.streamlit.io](https://share.streamlit.io) → **Create app** (or delete the app and redeploy to change Python later).
3. **Main file path:** `streamlit_app.py` (or `app.py` / `src/app.py`)
4. **Branch:** `main`
5. Click **Advanced settings** → **Python version** → **3.12** (or 3.11) → **Save**.
6. **Secrets** (same Advanced settings or app Settings) — paste (with your real keys):

```toml
GEMINI_API_KEY = "your-gemini-key"
GROQ_API_KEY = "your-groq-key"
GEMINI_MODEL = "gemini-3.8-flash"
GROQ_MODEL = "openai/gpt-oss-120b"
AI_PROVIDER_ORDER = "gemini,groq"
```

See [.streamlit/secrets.toml.example](.streamlit/secrets.toml.example). Cloud injects these as environment variables (same names as `.env`).

6. **Deploy.** First OCR run downloads Paddle models (can take several minutes). Free tier RAM is limited — if the app crashes on upload, use an [Oracle Always Free VM](https://www.oracle.com/cloud/free/) instead.

**Repo files used by Cloud:** `requirements.txt` (includes `-e .` and `paddlepaddle==2.6.2`), `packages.txt` (system libs for OCR: `libgl1`, `libglib2.0-0`, `libgomp1`), `.python-version`.

If install still fails with `cp314` or `No matching distribution found for paddlepaddle`, the app is on Python 3.14 — **delete the app**, redeploy, and set **Python 3.12** in Advanced settings.

If the app builds but the browser shows **500** / logs show `Expected ASGI message 'http.response.start'`, reboot after pulling the latest `requirements.txt` (pins `streamlit>=1.61.1` and `starlette<1.4.0`).

## Layout (Stage 5)

```
src/services/excel_service.py   preview_rows(), export_documents()
```

- Stable metadata columns plus `{field}` and `{field}_review` per schema
- `export_review_status`: `validated` or `needs_review`
- Preserves OCR text and source filename; never writes API keys
- **new** mode refuses to overwrite unless `overwrite_confirmed=True`
- **append** mode keeps existing sheets/rows; atomic save via temp file + replace

```python
from config import get_settings
from services import export_documents, preview_rows

settings = get_settings()
table = preview_rows(state.documents, schema)
export_documents("exports/batch.xlsx", state.documents, schema, settings, mode="append")
```

## Layout (Stage 4)

```
src/providers/     Gemini + Groq adapters, health tracker, failover router
src/services/      StructuringService uses router (retries + failover)
```

Cloud structuring sends **OCR text only** (not image bytes). Configure `GEMINI_API_KEY` and/or `GROQ_API_KEY` in `.env`.

`DEFAULT_AI_PROVIDER=auto` uses `AI_PROVIDER_ORDER` (default `gemini,groq`), skips providers in rate-limit cooldown, retries transient errors with bounded exponential backoff, honors `Retry-After`, and fails over only on recoverable errors.

```python
from config import AIProviderName, get_settings
from providers.registry import create_provider
from services import StructuringService

settings = get_settings()
structuring = StructuringService(create_provider(settings.default_ai_provider, settings))
doc = structuring.structure_document(doc, extraction_schema)
```

## Security notes

- Do not commit `.env`, uploads, or exported `.xlsx` files.
- OCR runs locally; only OCR text (not images) is sent to cloud AI providers by default (Stage 3+).
- Rotate any API key that was pasted into chat or committed by mistake.

## License

MIT (add a LICENSE file if you distribute this project).
