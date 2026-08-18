"""Recall Phase 2 — research + meeting brief on top of write_facts/recall.

Wikipedia (no API key) gathers public facts; Bedrock Titan Text Express
turns recalled memory into a brief. If the text model is not enabled,
we still emit a structured brief from memory so the demo never dies.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

from memory import (
    _bedrock_runtime,
    get_connection,
    init_schema,
    recall,
    resolve_company,
    write_facts,
)

WIKI_UA = "RecallMeetingPrep/1.0 (hackathon; compounding-memory agent)"
BRIEF_MODEL = os.environ.get("BRIEF_MODEL", "amazon.titan-text-express-v1")

SEED_FACTS = {
    "Acme Corp": [
        "Acme Corp shipped a self-serve pricing tier last month.",
        "Acme Corp raised a Series B led by a fintech VC.",
        "Acme's CTO previously founded a developer-tools startup.",
        "You promised to send Acme your API documentation - still open.",
    ]
}


def _http_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": WIKI_UA})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))


def research_company(name: str) -> tuple[list[str], str | None]:
    """Public facts from Wikipedia search + summary. Returns (facts, source_url)."""
    q = urllib.parse.quote(name)
    search = _http_json(
        "https://en.wikipedia.org/w/api.php?action=opensearch&limit=1&namespace=0"
        f"&format=json&search={q}"
    )
    titles = search[1] if isinstance(search, list) and len(search) > 1 else []
    if not titles:
        return [], None
    title = titles[0]
    tq = urllib.parse.quote(title.replace(" ", "_"))
    summary = _http_json(f"https://en.wikipedia.org/api/rest_v1/page/summary/{tq}")
    if not isinstance(summary, dict):
        return [], None
    extract = (summary.get("extract") or "").strip()
    url = (summary.get("content_urls") or {}).get("desktop", {}).get("page")
    if not extract:
        return [], url
    facts = []
    for sentence in re.split(r"(?<=[.!?])\s+", extract):
        sentence = sentence.strip()
        if len(sentence) > 40:
            facts.append(f"{name}: {sentence}")
        if len(facts) >= 4:
            break
    return facts, url


def _existing_texts(conn, entity_id) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT fact_text FROM memory_facts WHERE entity_id = %s",
            (entity_id,),
        )
        return {row[0] for row in cur.fetchall()}


def _write_new(conn, entity_id, facts: list[str], source_url: str | None) -> list[str]:
    have = _existing_texts(conn, entity_id)
    fresh = [f for f in facts if f not in have]
    if fresh:
        write_facts(conn, "company", entity_id, fresh, source_url=source_url)
    return fresh


def _bedrock_brief(company: str, goal: str, remembered: list[str]) -> str | None:
    bullets = "\n".join(f"- {t}" for t in remembered) or "- (none yet)"
    prompt = (
        f"You are a meeting-prep chief of staff. Write a tight one-page brief.\n"
        f"Company: {company}\n"
        f"Meeting goal: {goal}\n"
        f"Facts already in persistent memory:\n{bullets}\n\n"
        "Sections, in this order, short bullets only:\n"
        "1) What we already know\n"
        "2) Open promises / still owe them\n"
        "3) Likely talking points\n"
        "4) Suggested opening line\n"
        "Use only the facts given. Do not invent."
    )
    client = _bedrock_runtime()
    models = [BRIEF_MODEL, "amazon.titan-text-lite-v1"]
    body = json.dumps(
        {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 512,
                "temperature": 0.2,
                "topP": 0.9,
            },
        }
    )
    last_err = None
    for model_id in models:
        try:
            resp = client.invoke_model(modelId=model_id, body=body)
            payload = json.loads(resp["body"].read())
            results = payload.get("results") or []
            text = ""
            if results:
                text = results[0].get("outputText", "").strip()
            if not text:
                text = (payload.get("outputText") or "").strip()
            if text:
                return text
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        raise last_err
    return None


def _template_brief(company: str, goal: str, remembered: list[tuple[str, float]]) -> str:
    open_items = [
        t for t, _ in remembered if re.search(r"promised|still open|owe|follow-up", t, re.I)
    ]
    others = [t for t, _ in remembered if t not in open_items]
    know = [f"  • {t}" for t in others] or ["  • Nothing stored yet."]
    owed = [f"  • {t}" for t in open_items] or ["  • None flagged."]
    return "\n".join(
        [
            f"MEETING BRIEF — {company}",
            f"Goal: {goal}",
            "",
            "What we already know",
            *know,
            "",
            "Open promises / still owe them",
            *owed,
            "",
            "Suggested opening",
            f'  • "Last time we talked about {company} — I want to pick up where we left off."',
        ]
    )


def _counts(conn, entity_id) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM memory_facts WHERE entity_id = %s",
            (entity_id,),
        )
        return cur.fetchone()[0]


def _open_loops(conn, entity_id) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT fact_text FROM memory_facts
            WHERE entity_id = %s
              AND (
                fact_text ILIKE '%%still open%%'
                OR fact_text ILIKE '%%promised%%'
                OR fact_text ILIKE '%%owe them%%'
                OR fact_text ILIKE '%%follow-up%%'
              )
            ORDER BY created_at DESC
            """,
            (entity_id,),
        )
        return [row[0] for row in cur.fetchall()]


def list_companies() -> list[dict]:
    with get_connection() as conn:
        init_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.name, COUNT(m.id) AS n
                FROM companies c
                LEFT JOIN memory_facts m ON m.entity_id = c.id
                GROUP BY c.name
                ORDER BY n DESC, c.name
                """
            )
            return [{"name": n, "facts": int(k)} for n, k in cur.fetchall()]


def _pack(
    company: str,
    goal: str,
    cid,
    total: int,
    already_knew,
    seeded,
    researched,
    source,
    research_error,
    recalled,
    brief: str,
    brief_source: str,
    open_items: list[str],
    mode: str,
) -> dict:
    return {
        "company": company,
        "company_id": str(cid),
        "goal": goal,
        "total_facts": total,
        "already_knew": already_knew,
        "seeded": seeded,
        "researched": researched,
        "source_url": source,
        "research_error": research_error,
        "recalled": recalled,
        "brief": brief,
        "brief_source": brief_source,
        "open_items": open_items,
        "mode": mode,
        "companies": list_companies(),
    }


def ask_memory(company: str, question: str) -> dict:
    """Semantic recall only — no research, no writes."""
    with get_connection() as conn:
        init_schema(conn)
        cid = resolve_company(conn, company)
        hits = recall(conn, cid, question or company, k=5)
        opens = _open_loops(conn, cid)
        total = _counts(conn, cid)
        return _pack(
            company,
            question,
            cid,
            total,
            [{"text": t, "distance": float(d)} for t, d in hits],
            [],
            [],
            None,
            None,
            [{"text": t, "distance": float(d)} for t, d in hits],
            "",
            "recall-only",
            opens,
            "ask",
        )


def remember_note(company: str, note: str) -> dict:
    """Persist a new meeting note via write_facts."""
    facts = [line.strip() for line in note.splitlines() if line.strip()]
    with get_connection() as conn:
        init_schema(conn)
        cid = resolve_company(conn, company)
        written = _write_new(conn, cid, facts, "meeting-note")
        hits = recall(conn, cid, facts[0] if facts else company, k=5)
        opens = _open_loops(conn, cid)
        total = _counts(conn, cid)
        return _pack(
            company,
            "Logged a new note",
            cid,
            total,
            [{"text": t, "distance": float(d)} for t, d in hits],
            written,
            [],
            None,
            None,
            [{"text": t, "distance": float(d)} for t, d in hits],
            "\n".join([f"Saved {len(written)} new fact(s)."] + written)
            if written
            else "That note was already in memory.",
            "write_facts",
            opens,
            "remember",
        )


def prep_meeting(company: str, goal: str, domain: str | None = None) -> dict:
    """Research if needed, persist new facts, recall, generate a brief."""
    with get_connection() as conn:
        init_schema(conn)
        cid = resolve_company(conn, company, domain)
        before = recall(conn, cid, goal or company, k=8)
        seeded = _write_new(conn, cid, SEED_FACTS.get(company, []), "meeting-notes")
        researched, source, research_error = [], None, None
        try:
            researched, source = research_company(company)
        except Exception as exc:
            research_error = str(exc)
        newly_written = _write_new(conn, cid, researched, source)
        after = recall(conn, cid, goal or company, k=8)
        texts = [t for t, _ in after]
        brief = None
        brief_source = "template"
        try:
            brief = _bedrock_brief(company, goal, texts)
            if brief:
                brief_source = f"bedrock:{BRIEF_MODEL}"
        except Exception:
            brief = None
        if not brief:
            brief = _template_brief(company, goal, after)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE companies SET last_researched_at = now() WHERE id = %s",
                (cid,),
            )
        conn.commit()
        total = _counts(conn, cid)
        return _pack(
            company,
            goal,
            cid,
            total,
            [{"text": t, "distance": float(d)} for t, d in before],
            seeded,
            newly_written,
            source,
            research_error,
            [{"text": t, "distance": float(d)} for t, d in after],
            brief,
            brief_source,
            _open_loops(conn, cid),
            "prep",
        )
