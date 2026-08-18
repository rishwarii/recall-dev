## Inspiration

Everyone with back-to-back calls has the same problem: no time to prep, and worse, no memory between calls. You research a company once, then re-research the same account from scratch next month — and forget what you promised last time. We kept seeing “AI meeting-prep” tools that treat you like a stranger every single time. The interesting problem isn’t the one-shot research. It’s **memory that compounds**.

## What it does

Recall is a meeting-prep agent with a persistent file on every company. Before a call it opens that file: what you already know, what you still owe them, who you’ve tagged, and three questions worth asking. Ask “what did they change about pricing?” and it returns “they shipped a self-serve tier” even though those words don’t match — retrieval is by **meaning**, not keywords.

After a call you can write a new fact (“you promised a security review — still open”). The next prep still has it. Repeat preps skip a full web scrape and reuse memory (**delta** vs **cold**). That’s the difference from a one-shot research tool: the tenth meeting is sharper than the first because the ninth was saved.

Try it: [recall-dev-x92e.onrender.com](https://recall-dev-x92e.onrender.com) · code: [github.com/rishwarii/recall-dev](https://github.com/rishwarii/recall-dev)

## How we built it

The memory layer is **CockroachDB**. Structured rows live there (`companies`, `people`, `meetings`, `followups`, `questions`, `briefs`) plus `memory_facts` with an embedding column and nearest-neighbour search (`<=>`). On prep we embed the agenda with **Amazon Bedrock** (Titan Text Embeddings V2, 1024-dim) and rank facts by cosine distance. New facts are written back into the same table — that’s compounding. Briefs are also stored in **Amazon S3**.

The app is Python (Flask + psycopg). Cockroach tools we used: **distributed vector indexing** on `memory_facts.embedding`, and the cluster’s **Managed MCP Server** (cluster `c1f054db-ac26-4bd4-b175-2bd03cda7b17`). Local fastembed remains as a fallback backend; production uses Bedrock.

## Challenges we ran into

The vector round-trip had to be exact: embedding dimension had to match the column (we moved from local 384-dim to Bedrock 1024-dim and rebuilt the table), cosine ranking had to put the right fact first, and facts had to **survive a new process with no write in that run**. We tested that on purpose — persistence is the thesis.

Deploying on Render meant Cockroach `verify-full` TLS wanted a `root.crt` the host didn’t have; we kept TLS with `sslmode=require`. Bedrock needed a real regional endpoint (`us-east-1`), not a malformed `bedrock` region. IAM for S3 had to be granted from the account root (the app user could invoke Bedrock but couldn’t create buckets until then).

## Accomplishments we're proud of

Semantic recall works on a live CockroachDB cluster: “what about pricing?” ranks the self-serve tier first. Memory survives refresh, redeploy, and a second Prep that writes nothing new. Open promises (API docs still owed) show up without keyword search. The hosted demo writes the brief to S3. That is a compounding agent, not a one-shot scraper.

## What we learned

Memory, not research, is what makes an agent useful over time. Keeping operational rows and vectors in **one** CockroachDB cluster meant we didn’t bolt on a second vector database or fight consistency. Second-meeting recall is the feature judges should remember; everything else is scaffolding.

## What's next for Recall

Calendar-triggered prep ~30 minutes before a call (EventBridge / OAuth), tighter delta research from real news not Wikipedia, thumbs-up on briefs, and per-user isolation so the demo DB isn’t shared. Voice deep-dive and CRM write-back stay future.
