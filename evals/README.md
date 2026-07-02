# Evals

Pytest-based eval harness (golden rule 3: eval-driven development).

- Evals compare pipeline output against the **mutation log** of the synthetic
  data room — the ground truth of planted discrepancies.
- Headline metric: red-flag recall by severity tier.
- Second metric: false-positive rate on the clean (unmutated) data room.
- Extraction evals are stratified by document quality tier
  (clean / scanned / photographed).

Run with `pytest evals`. Evals that need external services (Claude API,
Postgres) skip cleanly when the required env vars are absent, so CI always
runs the deterministic subset.
