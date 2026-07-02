"""Build a complete synthetic data room on disk.

ledger -> spec -> (mutations, issue #4) -> rendered PDFs in three quality
tiers + manifest. The output directory is a data room where every answer
is known.
"""

from __future__ import annotations

import json
from pathlib import Path

from diligence.dataroom.spec import DataRoomSpec, build_spec
from diligence.ledger import generate_ledger
from diligence.ledger.models import CafeConfig
from diligence.render.bank_statement import render_bank_statement
from diligence.render.lease import render_lease
from diligence.render.management_pnl import render_management_pnl
from diligence.render.quality import TIERS, degrade
from diligence.render.statutory_accounts import render_statutory_accounts
from diligence.render.vat_return import render_vat_return


def render_spec(spec: DataRoomSpec, out_dir: Path) -> list[Path]:
    """Render every document in the spec to `out_dir` (clean tier). Returns paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for acc in spec.statutory_accounts:
        p = out_dir / f"statutory_accounts_fye{acc.fy_end.year}.pdf"
        render_statutory_accounts(spec.company, acc, str(p))
        paths.append(p)

    p = out_dir / "management_pnl.pdf"
    render_management_pnl(spec.company, spec.management_pnl, str(p))
    paths.append(p)

    for stmt in spec.bank_statements:
        p = out_dir / f"bank_statement_{stmt.period_start:%Y-%m}.pdf"
        render_bank_statement(spec.company, stmt, str(p))
        paths.append(p)

    for ret in spec.vat_returns:
        p = out_dir / f"vat_return_{ret.period_end:%Y-%m}.pdf"
        render_vat_return(spec.company, ret, str(p))
        paths.append(p)

    p = out_dir / "lease.pdf"
    render_lease(spec.company, spec.lease, str(p))
    paths.append(p)

    return paths


def build_dataroom(root: Path, config: CafeConfig | None = None,
                   mutations: list | None = None,
                   tiers: tuple[str, ...] = TIERS) -> DataRoomSpec:
    """Generate ledger, apply mutations to the spec, render all tiers."""
    ledger = generate_ledger(config)
    spec = build_spec(ledger)

    if mutations:
        from diligence.mutations.engine import apply_mutations

        apply_mutations(spec, mutations)

    clean_dir = root / "clean"
    paths = render_spec(spec, clean_dir)

    for tier in tiers:
        if tier == "clean":
            continue
        for p in paths:
            degrade(p, root / tier / p.name, tier)

    manifest = {
        "company": spec.company.__dict__,
        "documents": [p.name for p in paths],
        "tiers": list(tiers),
        "mutations": spec.mutations,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    (root / "mutation_log.json").write_text(
        json.dumps(spec.mutations, indent=2, default=str))
    return spec


def main() -> None:
    root = Path("data_rooms/copper_kettle_clean")
    spec = build_dataroom(root)
    n_docs = len(list((root / "clean").glob("*.pdf")))
    print(f"Data room written to {root}/ ({n_docs} documents x {len(TIERS)} tiers)")
    print(f"Mutations applied: {len(spec.mutations)}")


if __name__ == "__main__":
    main()
