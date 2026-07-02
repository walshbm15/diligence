# 05 — Target System Architecture (post-POC)

```
┌─ Intake ───────────────────────────────────┐
│ Data room upload (or VDR connector) →      │
│ Temporal/Inngest durable workflows         │
│ (a data room takes 20–60 min to process)   │
│ Doc classifier (zero-shot → fine-tuned)    │
│ routes to type-specific extractors         │
└────────────────────────────────────────────┘
┌─ Extraction layer ─────────────────────────┐
│ Financial docs: visual retrieval (ColQwen  │
│ class) + VLM extraction into a typed       │
│ FACT TABLE (Postgres) — every fact carries │
│ provenance (doc, page, bbox, confidence)   │
│ Contracts/leases: clause NER + risk        │
│ classifiers (fine-tuned token              │
│ classification = proprietary IP over time) │
│ Seller calls: Whisper + diarization →      │
│ claim extraction into same fact table      │
└────────────────────────────────────────────┘
┌─ Reconciliation engine ────────────────────┐
│ Deterministic check catalog run as SQL     │
│ over the fact table (see 03-check-catalog) │
│ — LLMs extract facts; CODE does math       │
└────────────────────────────────────────────┘
┌─ External verification agents (LangGraph) ─┐
│ UK: Companies House, Charges Register,     │
│ The Gazette, CCJs (Registry Trust),        │
│ Land Registry, FCA, CQC, FSA hygiene,      │
│ Google Places                              │
│ (Later — US: SoS, UCC, UniCourt;           │
│  DE: Handelsregister)                      │
└────────────────────────────────────────────┘
┌─ Report + critic ──────────────────────────┐
│ Skeptic agent adversarially challenges     │
│ findings → QoE-style report, every finding │
│ cited; warranty-suggestion mapping         │
│ Human-review tier (ACA partner) optional   │
└────────────────────────────────────────────┘
```

## Cross-cutting
- **Evals:** synthetic data rooms with planted discrepancies (recall on red
  flags by severity = headline metric) + false-positive rate + extraction
  accuracy per doc type stratified by scan quality + citation faithfulness
  (LLM-as-judge + spot audits) + cost/latency per data room. Full suite in
  CI on every prompt/model/retrieval change. Over time add anonymized real
  deals (with consent) as golden set → data moat.
- **LLMOps:** Langfuse tracing per agent hop, prompt versioning, per-deal
  cost tracking (per-deal pricing makes unit economics observability core
  product infra), drift monitoring on extractors as new doc formats appear.
- **Storage:** Postgres + pgvector — one store for embeddings AND the
  extracted financial fact table so reconciliation (SQL) and retrieval
  (vector) share one engine. Per-deal namespacing, row-level security.
- **Compliance:** UK data residency, DPAs, retention policies, Cyber
  Essentials. GDPR: B2B docs still contain personal data.

## HuggingFace task mapping
- Visual Document Retrieval + Document QA (ColQwen-class) — scanned
  financials as images, skipping brittle OCR
- Table QA — P&L / payroll tables
- Automatic Speech Recognition + diarization — seller calls
- Token Classification — fine-tuned NER (amounts, entities, dates, clauses)
- Zero-Shot / Text Classification — document triage, risk clauses
- Sentence Similarity / Feature Extraction + Text Ranking — hybrid retrieval
  (BM25 + vector + reranker)
- Summarization — per-document briefs feeding report agent
- Tabular Classification/Regression (later) — deal scoring trained on
  outcomes = ML moat beyond LLMs
