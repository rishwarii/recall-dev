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

**Amazon Bedrock** — Titan Text Embeddings V2 for vectors (`EMBED_BACKEND=bedrock`). Titan Text Express (or Lite) drafts the meeting brief when that model is enabled; otherwise Recall still prints a structured brief from memory.

## Phase 2 — the agent on top of memory

`write_facts` / `recall` are still the spine. Phase 2 adds:

1. **Research** — Wikipedia summary split into facts and written into `memory_facts` (duplicates skipped).
2. **Brief** — recalled facts turned into a one-page meeting dossier.
3. **Local UI** — `python app.py` then open http://127.0.0.1:5000. For a public URL, deploy as a Python web service (Render), not GitHub Pages.

Second click on the same company writes nothing new if memory already has it. That is compounding, visible in the UI.

## How memory compounds

Phase 1 writes facts into the persistent `memory_facts` table (not a throwaway). After `test_phase1.py` ran, a **new Python process** called `recall` with **no** `write_facts` first and still returned the pricing fact. That is the difference from a one-shot tool: memory survives across runs because CockroachDB holds it.

Demo beat for the video: ask “what did they change about pricing?”, quit the process, restart, ask again — the same fact comes back by meaning.

## Setup

Never hardcode secrets. Use environment variables in the shell session.

```powershell
pip install "psycopg[binary]" fastembed boto3 flask

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
python app.py
```

Then open http://127.0.0.1:5000

CLI: ask `What did Acme change about pricing?` — the self-serve pricing tier should rank first.

UI: company `Acme Corp`, goal `pricing changes and open follow-ups`, click **Prep this meeting**. Restart the server and click again — facts are still there.

## Hosted demo (not GitHub Pages)

GitHub Pages is static files only. Recall needs Python + CockroachDB + Bedrock, so the public UI belongs on a Python host such as [Render](https://render.com).

1. Push this repo.
2. Cockroach Cloud → allow networks → add `0.0.0.0/0` for the hackathon (or the host will be blocked).
3. Render → New Web Service → connect `rishwarii/recall-dev` → use `requirements.txt` / `Procfile`.
4. Set env vars in the Render dashboard (never in git): `DATABASE_URL`, `EMBED_BACKEND=bedrock`, `AWS_REGION=us-east-1`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.

The public URL from Render is the Devpost “try it out” link.

## License

MIT
