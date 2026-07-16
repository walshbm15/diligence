---
name: ship-it
description: Ship completed work as a reviewable PR - feature branch, local test gate, detailed commit, push, and a PR with a clear description. Use when a change is done and verified and the repo has moved to PR-based flow (post-POC / production). During the POC, direct commits to main remain the norm; only use ship-it when explicitly asked, or once the project has formally switched to PR flow.
---

# ship-it — branch, test, commit, push, PR

Turn the current working-tree changes into a reviewable pull request.
Never merge — merging is the code-reviewer's (or a human's) decision.

## 0. Preconditions — stop if any fail

- There ARE uncommitted changes to ship (`git status`). Nothing to ship →
  say so and stop.
- You can articulate in one sentence what the change does and why. If
  not, re-read the diff before proceeding.
- The work is actually complete and verified (tests you wrote pass,
  behavior was exercised). ship-it is a shipping gate, not a fix-it loop
  — if tests fail in step 2, stop and report; don't patch inside this
  skill.

## 1. Scope the change and pick a branch

```bash
git status --short && git diff --stat
git branch --show-current
```

- Already on a feature branch → stay on it (this is an update to an open
  PR; skip to step 2).
- On `main` → create a branch named for the change:
  `feat/<slug>`, `fix/<slug>`, or `chore/<slug>` (kebab-case, ≤4 words,
  e.g. `feat/multi-doc-pdf-splitting`).
- Ship only the files that belong to this change. Unrelated modified
  files stay unstaged — list them in your final report so they aren't
  forgotten.

## 2. Run the tests the diff actually touches — locally, before pushing

Pick by changed paths (run both groups when both changed):

| Changed under | Run |
|---|---|
| `src/diligence/`, `tests/`, `evals/`, `scripts/` | `.venv/bin/python -m pytest -q` and `.venv/bin/ruff check .` (Postgres up first: `docker compose up -d`) |
| `src/web/` | `cd src/web && npm run lint && npm run test && npm run build` |
| `.github/`, docs only | no test gate; note that in the PR body |

Any failure → **stop**. Report the failure output; do not commit, do not
push. Exception: a pre-existing failure unrelated to this diff may be
noted explicitly and shipped past — never silently.

## 3. Commit with a message a reviewer can trust

- Subject: imperative, specific, ≤72 chars.
- Body: what changed, WHY (the non-obvious part), what was verified and
  how. Reference issues (`#N`); use `Closes #N` only when the PR truly
  completes the issue.
- End with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## 4. Push and open the PR

```bash
git push -u origin <branch>
gh pr create --title "<subject>" --body "$(cat <<'EOF'
## Summary
<one paragraph: what this does and why now>

## Changes
- <bullet per meaningful change, not per file>

## Testing
- <suites run and their results, incl. anything skipped and why>

## Linked issues
<#N — relationship (closes/part-of/prepares)>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- A PR already exists for this branch → `git push` alone updates it; add
  a comment summarising what the new commits change.
- After opening: wait for CI (`gh pr checks <n> --watch` or a Monitor)
  and report the result. A red CI on your own PR is your problem — fix or
  report, don't abandon.

## 5. Report back

Final message must include: branch name, PR URL, test results, CI
status, and any unrelated-but-uncommitted files left behind. Suggest a
`code-reviewer` pass for non-trivial diffs.
