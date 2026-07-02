# Diligence OS

AI due-diligence engine for UK small-business acquisitions (sub-£2M deals).
See `CLAUDE.md` for architecture principles and `docs/` for the full plan.

## Setup

```bash
pyenv install 3.12.12  # if needed
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in API keys
docker compose up -d   # local Postgres on :5433
```

## Commands

```bash
pytest                 # tests + evals
ruff check .           # lint
diligence generate     # build the synthetic data room
```
