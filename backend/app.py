from __future__ import annotations

from contextlib import asynccontextmanager
import base64
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from urllib import request, error
from uuid import uuid4

VENDOR_DIR = Path(__file__).parent / ".vendor"
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from compliance import parse_label_text, run_compliance, serialize_rules
from demo_data import DEMO_FIELDS, DEMO_LABEL


BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "niyam_scans.sqlite3"

ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Niyam Package Compliance API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ScanRequest(BaseModel):
    label_text: str = ""
    fields: dict = Field(default_factory=dict)
    images: list[str] = Field(default_factory=list, description="Data URLs for one or two package sides")
    use_vision: bool = False


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


def init_db() -> None:
    with db() as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS scans (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, product_name TEXT,
            score INTEGER NOT NULL, risk_index INTEGER NOT NULL, payload TEXT NOT NULL
        )""")


def gemini_extract(images: list[str]) -> tuple[str, dict]:
    """Optional vision extractor using Gemini REST; no key means caller falls back to OCR/manual text."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "", {}
    parts = [{"text": "Extract visible package declarations. Return only JSON with fields: product_name, manufacturer, manufacturer_address, packer, packer_address, importer, importer_address, country_of_origin, net_quantity, mrp, mfg_date, best_before, fssai_license, ingredients, nutrition, veg_nonveg, allergens, consumer_care {address,phone,email}. Do not invent information; use null when unreadable."}]
    for image in images[:2]:
        if not image.startswith("data:") or "," not in image:
            continue
        header, encoded = image.split(",", 1)
        mime = header.split(";")[0].replace("data:", "") or "image/jpeg"
        parts.append({"inline_data": {"mime_type": mime, "data": encoded}})
    if len(parts) == 1:
        return "", {}
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = json.dumps({"contents": [{"parts": parts}], "generationConfig": {"response_mime_type": "application/json", "temperature": 0}}).encode()
    req = request.Request(endpoint, data=payload, headers={"Content-Type": "application/json", "x-goog-api-key": api_key}, method="POST")
    for attempt in range(2):
        try:
            with request.urlopen(req, timeout=25) as response:
                body = json.loads(response.read().decode())
            break
        except error.HTTPError as exc:
            if exc.code == 503 and attempt == 0:
                time.sleep(0.6)
                continue
            if exc.code in {401, 403}:
                raise HTTPException(status_code=502, detail="Vision credentials were rejected. Check the server-side Gemini key.") from exc
            if exc.code == 404:
                raise HTTPException(status_code=502, detail="The configured Gemini model is unavailable. Check GEMINI_MODEL.") from exc
            raise HTTPException(status_code=502, detail=f"Vision service unavailable (HTTP {exc.code}).") from exc
        except error.URLError as exc:
            raise HTTPException(status_code=502, detail=f"Vision service unavailable: {exc.reason}") from exc
    try:
        extracted = json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
        return json.dumps(extracted, ensure_ascii=False), extracted
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Vision response could not be converted to evidence fields.") from exc


def store_report(report: dict) -> str:
    scan_id = str(uuid4())
    payload = {**report, "scan_id": scan_id}
    with db() as connection:
        connection.execute(
            "INSERT INTO scans VALUES (?, ?, ?, ?, ?, ?)",
            (scan_id, report["generated_at"], report["fields"].get("product_name"), report["summary"]["score"], report["summary"]["risk_index"], json.dumps(payload)),
        )
    return scan_id


def remove_empty_values(value):
    """Keep only AI fields supported by evidence; nulls must never become label text."""
    if isinstance(value, dict):
        return {key: cleaned for key, item in value.items() if (cleaned := remove_empty_values(item)) is not None}
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := remove_empty_values(item)) is not None]
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return value


def has_visible_declaration(fields: dict) -> bool:
    return any(isinstance(value, str) and value.strip() for value in fields.values()) or any(
        isinstance(value, dict) and has_visible_declaration(value) for value in fields.values()
    )


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "vision_configured": bool(os.getenv("GEMINI_API_KEY"))}


@app.get("/api/rules")
def rules() -> dict:
    return {"rules": serialize_rules(), "note": "Rules are mapped as inspection-aid signals; current category-specific notifications still require human review."}


@app.post("/api/scan")
def scan(payload: ScanRequest) -> dict:
    vision_text, vision_fields = gemini_extract(payload.images) if payload.use_vision and payload.images else ("", {})
    vision_fields = remove_empty_values(vision_fields)
    if payload.use_vision and payload.images and not payload.label_text.strip() and not has_visible_declaration(vision_fields):
        raise HTTPException(status_code=422, detail="Niyam could not read label declarations from this image. Retake a close, glare-free photo or add the label transcript; no inspection was saved.")
    supplied = {**vision_fields, **payload.fields}
    supplied["captured_sides"] = len(payload.images) if payload.images else supplied.get("captured_sides", 1)
    raw_text = payload.label_text
    fields = parse_label_text(raw_text, supplied)
    report = run_compliance(fields)
    report["scan_id"] = store_report(report)
    report["extraction"] = {
        "source": "vision" if vision_fields else ("transcript" if payload.label_text else "structured review"),
        "vision_configured": bool(os.getenv("GEMINI_API_KEY")),
        "captured_sides": fields.get("captured_sides", 0),
    }
    return report


@app.post("/api/demo")
def demo() -> dict:
    fields = parse_label_text(DEMO_LABEL, DEMO_FIELDS)
    report = run_compliance(fields)
    # The jury demo is a reusable preview, not an inspection record.
    # Only real /api/scan submissions belong in the local inspection ledger.
    report["scan_id"] = "demo-preview"
    report["extraction"] = {"source": "demo evidence", "vision_configured": bool(os.getenv("GEMINI_API_KEY")), "captured_sides": 2}
    return report


@app.get("/api/history")
def history(limit: int = 12) -> dict:
    safe_limit = min(max(limit, 1), 50)
    with db() as connection:
        rows = connection.execute("SELECT id, created_at, product_name, score, risk_index FROM scans ORDER BY created_at DESC LIMIT ?", (safe_limit,)).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/api/scan/{scan_id}")
def get_scan(scan_id: str) -> dict:
    with db() as connection:
        row = connection.execute("SELECT payload FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="This inspection case was not found in the local ledger.")
    return json.loads(row["payload"])


@app.get("/api/stats")
def stats() -> dict:
    with db() as connection:
        total = connection.execute("SELECT COUNT(*) FROM scans").fetchone()[0]
        average_score = connection.execute("SELECT ROUND(AVG(score)) FROM scans").fetchone()[0] if total else None
        high_risk = connection.execute("SELECT COUNT(*) FROM scans WHERE risk_index >= 35").fetchone()[0]
    return {"total_scans": total, "average_score": average_score, "high_risk": high_risk}


DIST_DIR = BASE_DIR.parent / "dist"
if DIST_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")
