"""
Recall — Phase 0 smoke test.

Proves the one round trip that de-risks the whole project:
  1. connect to CockroachDB
  2. embed a sentence with Amazon Bedrock (Titan v2, 1024-dim)
  3. store the vector in memory_facts
  4. query it back by semantic similarity
"""

import json
import os
import uuid

import boto3
import psycopg

DATABASE_URL = os.environ["DATABASE_URL"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
EMBED_MODEL = "amazon.titan-embed-text-v2:0"  # 1024-dim, matches VECTOR(1024)

bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def embed(text: str) -> list[float]:
    """Turn text into a 1024-dim vector via Bedrock Titan Text Embeddings V2."""
    body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
    resp = bedrock.invoke_model(modelId=EMBED_MODEL, body=body)
    return json.loads(resp["body"].read())["embedding"]


def to_vector_literal(vec: list[float]) -> str:
    """CockroachDB / pgvector wants '[0.1,0.2,...]' text, cast to VECTOR."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def main() -> None:
    # A tiny fake company so the FK on memory_facts.entity_id points somewhere real.
    company_id = uuid.uuid4()

    facts = [
        "Acme Corp shipped a self-serve pricing tier last month.",
        "Acme Corp raised a Series B led by a fintech VC.",
        "Acme's CTO previously founded a developer-tools startup.",
        "You promised to send Acme your API documentation — still open.",
    ]

    query = "What did Acme change about how they charge customers?"

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # Seed the company row.
            cur.execute(
                "INSERT INTO companies (id, name, domain) VALUES (%s, %s, %s)",
                (company_id, "Acme Corp", f"acme-{company_id.hex[:6]}.com"),
            )

            # 1 + 2 + 3: embed each fact and store it with its vector.
            print("Embedding and storing facts...")
            for fact in facts:
                vec = embed(fact)
                cur.execute(
                    """
                    INSERT INTO memory_facts (entity_type, entity_id, fact_text, embedding)
                    VALUES ('company', %s, %s, %s::VECTOR)
                    """,
                    (company_id, fact, to_vector_literal(vec)),
                )
            conn.commit()

            # 4: semantic recall — nearest facts to the query.
            print(f"\nQuery: {query}\n")
            qvec = to_vector_literal(embed(query))
            cur.execute(
                """
                SELECT fact_text, embedding <=> %s::VECTOR AS distance
                FROM memory_facts
                WHERE entity_id = %s
                ORDER BY distance
                LIMIT 3
                """,
                (qvec, company_id),
            )
            print("Most relevant facts (closest first):")
            for text, dist in cur.fetchall():
                print(f"  [{dist:.4f}]  {text}")

    print("\n✅  Round trip works. Phase 0 is done.")


if __name__ == "__main__":
    main()
