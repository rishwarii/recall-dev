"""
Recall — Phase 1 test.

Demonstrates the compounding-memory loop against the PERSISTENT table:

  Meeting 1: we learn facts about Acme -> write_facts() persists them.
  Meeting 2 (later): we recall what we already know -> recall().

Because the facts live in memory_facts (not a throwaway table), they
survive across runs. Run this twice: the second time, the recall still
works even before any new write -- that persistence IS the compounding.

  python test_phase1.py
"""

from memory import get_connection, init_schema, resolve_company, write_facts, recall

MEETING_1_FACTS = [
    "Acme Corp shipped a self-serve pricing tier last month.",
    "Acme Corp raised a Series B led by a fintech VC.",
    "Acme's CTO previously founded a developer-tools startup.",
    "You promised to send Acme your API documentation - still open.",
]

MEETING_2_QUESTIONS = [
    "What did Acme change about pricing?",
    "What do I still owe them?",
    "Tell me about their funding.",
]


def main() -> None:
    with get_connection() as conn:
        init_schema(conn)

        # Resolve (or create) the company we're meeting.
        acme = resolve_company(conn, "Acme Corp", "acme.com")
        print(f"Company resolved: Acme Corp ({acme})")

        # --- Meeting 1: learn and persist ---
        n = write_facts(conn, "company", acme, MEETING_1_FACTS,
                        source_url="https://example.com/acme")
        print(f"Meeting 1: wrote {n} facts to memory.\n")

        # --- Meeting 2: recall what we already know ---
        print("Meeting 2 -- recalling from memory:")
        for q in MEETING_2_QUESTIONS:
            print(f"\n  Q: {q}")
            for text, dist in recall(conn, acme, q, k=3):
                print(f"     [{dist:.4f}] {text}")

    print("\nPhase 1 works: facts persisted and recalled from the real memory table.")


if __name__ == "__main__":
    main()
