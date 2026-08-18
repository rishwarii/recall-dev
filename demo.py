"""Recall CLI demo for screen recording.

Windows: $env:PYTHONIOENCODING = "utf-8"  (avoids cp1252 crashes)
"""
from memory import get_connection, init_schema, resolve_company, write_facts, recall

FACTS = [
    "Acme Corp shipped a self-serve pricing tier last month.",
    "Acme Corp raised a Series B led by a fintech VC.",
    "Acme's CTO previously founded a developer-tools startup.",
    "You promised to send Acme your API documentation - still open.",
]


def main() -> None:
    with get_connection() as conn:
        init_schema(conn)
        acme = resolve_company(conn, "Acme Corp", "acme.com")
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM memory_facts WHERE entity_id = %s", (acme,))
            n = cur.fetchone()[0]
        if n == 0:
            write_facts(conn, "company", acme, FACTS, source_url="https://example.com/acme")
            print("Wrote 4 Acme facts into persistent memory.")
        else:
            print(f"Memory already has {n} Acme fact(s).")
        print("Ask a question (empty line or Ctrl+C to quit).\n")
        while True:
            q = input("Q: ").strip()
            if not q:
                break
            for text, dist in recall(conn, acme, q, k=3):
                print(f"  [{dist:.4f}] {text}")


if __name__ == "__main__":
    main()
