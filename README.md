# Recall

An agentic meeting-prep tool with **compounding memory**. Before you walk into a call, Recall already knows what you learned last time — pricing changes, open follow-ups, funding — because those facts live in a real database, not in a one-shot chat.

Repo: [github.com/rishwarii/recall-dev](https://github.com/rishwarii/recall-dev)

## Architecture

- **CockroachDB** is the persistent memory layer. Facts are stored with embeddings and retrieved by cosine distance (`<=>`) over a **distributed vector index**.
- **Amazon Bedrock** (Titan Text Embeddings V2, `amazon.titan-embed-text-v2:0`) turns text into 1024-dim vectors when `EMBED_BACKEND=bedrock`. A local fastembed path (384-dim) remains for offline work.
- Two functions sit under everything else: `write_facts` (store what you learn) and `recall` (get back what is relevant).

## CockroachDB tools used

- **Distributed vector indexing** on `memory_facts.embedding` for semantic recall
- **Managed MCP Server** for agent access to the cluster  
  Cluster ID: `c1f054db-ac26-4bd4-b175-2bd03cda7b17`

## AWS service used

**Amazon Bedrock** — Titan Text Embeddings V2 for production embeddings (`EMBED_BACKEND=bedrock`).

## How memory compounds

Phase 1 writes facts into the persistent `memory_facts` table (not a throwaway). After `test_phase1.py` ran, a **new Python process** called `recall` with **no** `write_facts` first and still returned the pricing fact. That is the difference from a one-shot tool: memory survives across runs because CockroachDB holds it.

Demo beat for the video: ask “what did they change about pricing?”, quit the process, restart `demo.py`, ask again — the same fact comes back by meaning.

## Setup

Never hardcode secrets. Use environment variables in the shell session.

```powershell
pip install "psycopg[binary]" fastembed boto3

$env:PYTHONIOENCODING = "utf-8"
$env:DATABASE_URL = "postgresql://USER:PASSWORD@HOST:26257/defaultdb?sslmode=verify-full"
$env:EMBED_BACKEND = "bedrock"   # or "local"
$env:AWS_REGION = "us-east-1"
$env:AWS_ACCESS_KEY_ID = "AKIA..."
$env:AWS_SECRET_ACCESS_KEY = "..."
```

Do **not** load `schema.sql` while using the local 384-dim embedder; `memory.py` creates `memory_facts` at the dimension for the current backend. Switching `local` ↔ `bedrock` requires dropping and recreating `memory_facts` so vector sizes do not mix.

## Run

```powershell
python test_phase1.py
python demo.py
```

Ask `What did Acme change about pricing?` — the self-serve pricing tier should rank first.

## License

MIT
