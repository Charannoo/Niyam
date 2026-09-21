<div align="center">

# Niyam

### Package Compliance Intelligence — *evidence-first inspection for pre-packaged commodities in India*

Niyam turns front/back package photos into a traceable, rule-by-rule compliance triage. It is not another OCR tool — it links **two-sided evidence → legal declarations → risk**, and it never pretends it saw something it didn't.

[Tech](#tech-stack) · [How it works](#how-it-works) · [Quick start](#quick-start) · [Deploy](#deploy) · [Legal basis](docs/LEGAL_BASIS.md)

</div>

---

## Why Niyam is more than Google Lens

| | Google Lens | **Niyam** |
|---|---|---|
| Reads text on a label | ✅ | ✅ |
| Treats front + back as **one inspection case** | — | ✅ **Two-sided evidence chain** |
| Names the **rule citation** behind each decision | — | ✅ `LMPC Rules, 2011 · Rule 6(1)(e)` |
| Retains **uncertainty** instead of guessing | — | ✅ Unreadable = `Needs review`, never a false violation |
| Tells the officer the **next photo to capture** | — | ✅ `Capture next` intelligence |
| Routes **food** and **import** checks only when relevant | — | ✅ FSSAI lane + importer context |
| Keeps a **local inspection ledger** for store sweeps | — | ✅ Scan history & risk prioritisation |

> “Google Lens tells you what text it can see. Niyam turns two-sided evidence into a traceable, rule-by-rule inspection queue — without pretending that OCR alone can issue a legal notice.”

## How it works

```
  Capture (front + back)  →  Map evidence → 18 contextual checks  →  Triage (score, risk, action)
         │                           │                                     │
         └─ OCR / manual transcript  └─ optional Gemini Vision              └─ Capture-next, verdict per rule
```

Every inspection case records what was **found**, what is **uncertain**, which side is **missing**, and what the officer must **capture next** — all retained in a local ledger.

## Tech stack

- **Frontend** — React 18 + Vite, mobile-first installable **PWA** (camera capture, offline shell)
- **Backend** — FastAPI + uvicorn, SQLite inspection ledger
- **Vision (optional)** — Gemini API for evidence extraction from package photos
- **Rules engine** — pure-Python, tested, citation-mapped (no AI keys required)

## Quick start

```powershell
# terminal 1 — API (uses the prepared local runtime vendor)
$env:PYTHONPATH = "$PWD\backend\.vendor"
python -m uvicorn app:app --app-dir backend --reload --port 8000

# terminal 2 — UI
npm install
npm run dev
```

Open `http://127.0.0.1:5173` and press **Run jury-ready demo** for a complete two-side evidence report — no API keys needed.

### Optional Gemini Vision

Set `GEMINI_API_KEY` (and optionally `GEMINI_MODEL`) before starting the API, then enable **Use configured vision extraction** in the app. Without the key, paste the OCR/manual transcript — the rules engine remains fully usable offline.

## Verification

```powershell
python tests\test_compliance.py
npm run build
```

## Deploy

Single-container build — the FastAPI server serves both the API and the built PWA from one origin:

```powershell
docker build -t niyam .
docker run -d --name niyam -p 8000:8000 niyam    # open http://<host>:8000
```

Full platform guidance (Render / Railway / VPS, same-origin vs separate origins, CORS handling) is in [docs/LEGAL_BASIS.md](docs/LEGAL_BASIS.md) alongside the statutory mapping, source link, and jury-safe positioning.

## Repository layout

```
backend/        FastAPI app, rules engine, demo data
src/            React PWA
public/         PWA manifest, icons, service worker
docs/           legal-basis & jury positioning
tests/          compliance-engine safety checks
Dockerfile      single-container production image
```

## License & responsibility

Niyam is a prototype for the Smart India Hackathon (SIH 2026). It is a **decision-support aid, never automated enforcement** — statutory inspection always ends with an officer’s review of the physical package and current category-specific notifications.

© 2026 Niyam · SIH26034