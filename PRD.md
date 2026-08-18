# Recall PRD (hackathon slice)

## Problem
Every meeting-prep tool researches a company as if you have never spoken. Promises, pricing changes, and follow-ups die when the process ends.

## Product
Recall is an agentic meeting-prep dossier with **compounding memory**. Facts live in CockroachDB. Embeddings come from Amazon Bedrock. Two primitives sit under everything: `write_facts` and `recall`.

## Features (must ship)

| Feature | Where |
|---|---|
| Persistent vector memory | `memory.py` → `memory_facts` |
| Semantic recall (not keyword search) | `recall()` + **Ask memory** |
| Write what you learned | `write_facts()` + **Write fact** |
| Company resolve / create | `resolve_company()` |
| Public research into memory | Wikipedia → `write_facts` on **Prep** |
| Meeting brief | Bedrock text if enabled, else structured template |
| Open promises / still owe them | **Open promises** list + stamp |
| Compounding across runs | second Prep writes nothing new if known |
| Roster of companies in memory | homepage meta line |
| Hosted UI | https://recall-dev-x92e.onrender.com |

## Out of scope this slice
Calendar sync, email ingest, multi-user auth, Bedrock 1024 schema.sql load while on a mixed local dim.
