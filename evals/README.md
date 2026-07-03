# Evals

Pytest-based eval harness (golden rule 3: eval-driven development).

- Evals compare pipeline output against the **mutation log** of the synthetic
  data room — the ground truth of planted discrepancies.
- Headline metric: red-flag recall by severity tier.
- Second metric: false-positive rate on the clean (unmutated) data room.
- Extraction evals are stratified by document quality tier
  (clean / scanned / photographed).

## Current results (check layer, ground-truth facts)

| Metric | Result | Exit criterion |
|---|---|---|
| Planted discrepancies caught | **9/10** | ≥ 8/10 ✅ |
| Red (deal-killer) recall | **7/7** | — |
| Amber recall | 2/3 (miss = T2 check, out of POC scope) | — |
| False positives on clean room | **0** | 0 ✅ |
| Hallucinated citations | **0** | 0 ✅ |

## Running

`pytest evals` — the deterministic subset (scorers, recall on ground-truth
facts) always runs and gates CI.

The **live extraction eval** (`test_extraction_accuracy.py`) additionally
needs: `ANTHROPIC_API_KEY` in `.env`, Postgres up (`docker compose up -d`),
and generated data rooms (`diligence generate`). It measures field-level
extraction accuracy per doc type per quality tier against the Week 2 exit
criterion (≥95% clean) and the ≤85% scanned kill criterion.
