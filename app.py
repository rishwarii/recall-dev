"""Recall local meeting-prep UI.

Windows: $env:PYTHONIOENCODING = "utf-8"
  python app.py
Then open http://127.0.0.1:5000
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from flask import Flask, render_template, request

KEYS_CSV = Path(__file__).with_name("aws-access-keys.csv")


def _hydrate_env() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("AWS_REGION", "us-east-1")
    os.environ.setdefault("EMBED_BACKEND", "bedrock")
    if os.environ.get("AWS_ACCESS_KEY_ID") or not KEYS_CSV.exists():
        return
    with KEYS_CSV.open(newline="", encoding="utf-8") as f:
        row = next(csv.DictReader(f), None)
    if not row:
        return
    os.environ["AWS_ACCESS_KEY_ID"] = row["Access key ID"].strip()
    os.environ["AWS_SECRET_ACCESS_KEY"] = row["Secret access key"].strip()


_hydrate_env()
if not os.environ.get("DATABASE_URL"):
    raise SystemExit("Set DATABASE_URL in this PowerShell session before running app.py")

from agent import ask_memory, list_companies, prep_meeting, remember_note  # noqa: E402

app = Flask(__name__)


def _run(fn, *args):
    try:
        return render_template("index.html", result=fn(*args))
    except Exception as exc:
        return (f"<h1>Action failed</h1><pre>{exc}</pre><p><a href='/'>Back</a></p>", 500)


@app.get("/")
def home():
    try:
        companies = list_companies()
    except Exception:
        companies = []
    return render_template("index.html", result=None, companies=companies)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/prep")
def prep():
    company = (request.form.get("company") or "Acme Corp").strip()
    goal = (request.form.get("goal") or "pricing changes and open follow-ups").strip()
    return _run(prep_meeting, company, goal)


@app.post("/ask")
def ask():
    company = (request.form.get("company") or "Acme Corp").strip()
    goal = (request.form.get("goal") or "What did they change about pricing?").strip()
    return _run(ask_memory, company, goal)


@app.post("/remember")
def remember():
    company = (request.form.get("company") or "Acme Corp").strip()
    note = (request.form.get("note") or "").strip()
    return _run(remember_note, company, note)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
