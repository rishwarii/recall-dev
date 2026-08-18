"""
Recall — Phase 0 smoke test (LOCAL version, no AWS).

Same round trip as the Bedrock version, but the embeddings are made
locally with fastembed instead of Amazon Bedrock. Proves that:
  1. we can connect to CockroachDB
  2. turn text into an embedding (locally)
  3. store the vector in CockroachDB
  4. query it back by semantic similarity

This script is SELF-CONTAINED: it creates its own temporary table and
drops it at the end, so it does NOT need schema.sql loaded and does NOT
touch your real tables. When AWS is ready, we switch embed() back to
Bedrock and use the real 1024-dim schema.

Setup:
  pip install "psycopg[binary]" fastembed
  $env:DATABASE_URL = "postgresql://...:26257/defaultdb?sslmode=verify-full"
  python phase0_local.py
"""

import os
import uuid

import psycopg
from fastembed import TextEmbedding

DATABASE_URL = os.environ["DATABASE_URL"]

# Small local model. 384-dim output. Downloads ~100MB the first run, then cached.
print("Loading local embedding model (first run downloads ~100MB)...")
_model = TextEmbedding("BAAI/bge-small-en-v1.5")
EMBED_DIM = 384


def embed(text: str) -> list[float]:
    """Turn text into a 384-dim vector, locally. No cloud, no account."""
    return list(_model.embed([text]))[0].tolist()


def to_vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def main() -> None:
    facts = [
        "Acme Corp shipped a self-serve pricing tier last month.",
        "Acme Corp raised a Series B led by a fintech VC.",
        "Acme's CTO previously founded a developer-tools startup.",
        "You promised to send Acme your API documentation — still open.",
    ]
    query = "What did Acme change about how they charge customers?"

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Self-contained: make our own throwaway table with the matching dim.
            table = f"smoke_{uuid.uuid4().hex[:8]}"
            cur.execute(
                f"""
                CREATE TABLE {table} (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    fact_text STRING,
                    embedding VECTOR({EMBED_DIM})
                )
                """
            )

            print("Embedding and storing facts...")
            for fact in facts:
                cur.execute(
                    f"INSERT INTO {table} (fact_text, embedding) VALUES (%s, %s::VECTOR)",
                    (fact, to_vector_literal(embed(fact))),
                )
            conn.commit()

            print(f"\nQuery: {query}\n")
            qvec = to_vector_literal(embed(query))
            cur.execute(
                f"""
                SELECT fact_text, embedding <=> %s::VECTOR AS distance
                FROM {table}
                ORDER BY distance
                LIMIT 3
                """,
                (qvec,),
            )
            print("Most relevant facts (closest first):")
            for text, dist in cur.fetchall():
                print(f"  [{dist:.4f}]  {text}")

            # Clean up — leave no trace in your cluster.
            cur.execute(f"DROP TABLE {table}")
            conn.commit()

    print("\n✅  Round trip works. Phase 0 (local) is done.")


if __name__ == "__main__":
    main()
