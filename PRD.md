# Recall PRD (hackathon slice — what ships)

Full original PRD intent: compounding meeting-prep memory on CockroachDB + Bedrock.

## Implemented in prod

- Data model: `companies`, `people`, `meetings`, `meeting_participants`, `memory_facts`, `questions`, `followups`, `briefs`
- Distributed vector search on `memory_facts.embedding` (`<=>`); vector index best-effort
- Cold vs **delta** research (skip public scrape on repeat; still recall)
- Brief with “last time / still open / three questions”
- Ask memory (chat-tab RAG) and post-meeting **Write fact**
- Optional S3 brief store if `S3_BUCKET` is set
- Structured prep logs (`research_kind`, latency, cache hit)
- Hosted UI: https://recall-dev-x92e.onrender.com
- AWS: **Amazon Bedrock** (required). S3 optional.
- Cockroach: vector recall + Managed MCP (cluster `c1f054db-ac26-4bd4-b175-2bd03cda7b17`)

## Not in this slice (PRD cut-list)

- Google OAuth / Gmail / calendar poll
- AWS Lambda + Step Functions + EventBridge Scheduler (prep is in-process)
- Voice deep-dive
- Multi-user RBAC / MCP write path in this repo

Protect **second-meeting recall** first — that is live.
