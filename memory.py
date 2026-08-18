"""
Recall — Phase 1: the memory core.

Two functions the whole agent will stand on:
  write_facts(...)  -> embed facts and persist them (compounding memory)
  recall(...)       -> semantic lookup of what we already know

Unlike the Phase 0 smoke test, this writes to a PERSISTENT table
(memory_facts), so facts survive across runs — that is what makes memory
"compound." Embeddings: EMBED_BACKEND=local (fastembed, 384-dim, default)
or EMBED_BACKEND=bedrock (Titan Text Embeddings V2, 1024-dim). Recreate
memory_facts when switching backends — do not mix dimensions in one table.

Setup:
  pip install "psycopg[binary]" fastembed boto3
  $env:DATABASE_URL = "postgresql://...:26257/defaultdb?sslmode=verify-full"
  $env:EMBED_BACKEND = "local"   # or "bedrock"
"""

import json
import os
import uuid

import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]
EMBED_BACKEND = os.environ.get("EMBED_BACKEND", "local").strip().lower()

# Local model is lazy-loaded so Bedrock deploys do not need fastembed.
_model = None
_bedrock_client = None

if EMBED_BACKEND == "local":
    EMBED_DIM = 384
elif EMBED_BACKEND == "bedrock":
    EMBED_DIM = 1024
else:
    raise ValueError(
        f"EMBED_BACKEND must be 'local' or 'bedrock', got {EMBED_BACKEND!r}"
    )


def _embed_local(text: str) -> list[float]:
    """Text -> 384-dim vector, locally."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding("BAAI/bge-small-en-v1.5")
    return list(_model.embed([text]))[0].tolist()


def _embed_bedrock(text: str) -> list[float]:
    """Text -> 1024-dim vector via Bedrock Titan Text Embeddings V2."""
    import boto3

    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )
    resp = _bedrock_client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text}),
    )
    payload = json.loads(resp["body"].read())
    return payload["embedding"]


def embed(text: str) -> list[float]:
    """Text -> vector; backend from EMBED_BACKEND (local | bedrock)."""
    if EMBED_BACKEND == "bedrock":
        return _embed_bedrock(text)
    return _embed_local(text)


def _vec(v: list[float]) -> str:
    """Format a Python list as a CockroachDB VECTOR literal."""
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def _connect_url() -> str:
    """Render has no ~/.postgresql/root.crt; use OS trust store for verify-full."""
    url = DATABASE_URL
    if "sslrootcert=" not in url.lower():
        join = "&" if "?" in url else "?"
        url = f"{url}{join}sslrootcert=system"
    return url


def get_connection():
    """One place to open a connection."""
    return psycopg.connect(_connect_url())


def init_schema(conn) -> None:
    """Create tables at EMBED_DIM (384 local / 1024 bedrock). Idempotent."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name   STRING NOT NULL,
                domain STRING,
                last_researched_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT now()
            )
            """
        )
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS memory_facts (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                entity_type STRING NOT NULL,
                entity_id   UUID   NOT NULL,
                fact_text   STRING NOT NULL,
                source_url  STRING,
                confidence  FLOAT DEFAULT 0.7,
                embedding   VECTOR({EMBED_DIM}),
                created_at  TIMESTAMPTZ DEFAULT now()
            )
            """
        )
    conn.commit()


def resolve_company(conn, name: str, domain: str | None = None) -> uuid.UUID:
    """Get the company's id, creating the row if we've never seen it."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM companies WHERE name = %s LIMIT 1", (name,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            "INSERT INTO companies (name, domain) VALUES (%s, %s) RETURNING id",
            (name, domain),
        )
        cid = cur.fetchone()[0]
    conn.commit()
    return cid


def write_facts(
    conn,
    entity_type: str,
    entity_id: uuid.UUID,
    facts: list[str],
    source_url: str | None = None,
) -> int:
    """Embed each fact and persist it. Returns how many were written."""
    with conn.cursor() as cur:
        for fact in facts:
            cur.execute(
                """
                INSERT INTO memory_facts
                    (entity_type, entity_id, fact_text, source_url, embedding)
                VALUES (%s, %s, %s, %s, %s::VECTOR)
                """,
                (entity_type, entity_id, fact, source_url, _vec(embed(fact))),
            )
    conn.commit()
    return len(facts)


def recall(conn, entity_id: uuid.UUID, query: str, k: int = 5):
    """Return the k facts most semantically similar to `query`.

    Distance is cosine distance via <=> (smaller = more relevant).
    """
    qv = _vec(embed(query))
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT fact_text, embedding <=> %s::VECTOR AS distance
            FROM memory_facts
            WHERE entity_id = %s
            ORDER BY distance
            LIMIT %s
            """,
            (qv, entity_id, k),
        )
        return cur.fetchall()
