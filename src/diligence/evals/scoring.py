"""Field-level extraction accuracy scoring.

Compares extracted facts against spec-derived expected facts. Scalar facts
match on (fact_type, source_doc, period) with exact value equality; bank
transactions match as a multiset of (date, amount, direction) per document.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from diligence.facts.model import Fact, FactType


@dataclass
class DocTypeScore:
    matched: int = 0
    expected: int = 0
    mismatches: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.matched / self.expected if self.expected else 1.0


@dataclass
class AccuracyReport:
    tier: str
    by_doc_type: dict[str, DocTypeScore] = field(default_factory=dict)

    @property
    def overall(self) -> float:
        matched = sum(s.matched for s in self.by_doc_type.values())
        expected = sum(s.expected for s in self.by_doc_type.values())
        return matched / expected if expected else 1.0

    def table(self) -> str:
        lines = [f"extraction accuracy — tier: {self.tier}"]
        for doc_type in sorted(self.by_doc_type):
            s = self.by_doc_type[doc_type]
            lines.append(f"  {doc_type:22} {s.matched:5}/{s.expected:<5} "
                         f"{s.accuracy:7.1%}")
        lines.append(f"  {'OVERALL':22} {self.overall:7.1%}")
        return "\n".join(lines)


def _value_key(f: Fact):
    return (f.value_pence, f.value_num, f.value_text, f.value_date)


def _scalar_key(f: Fact):
    return (f.fact_type, f.source_doc, f.period_start, f.period_end)


def score_extraction(expected: list[Fact], extracted: list[Fact],
                     tier: str) -> AccuracyReport:
    report = AccuracyReport(tier=tier)

    def bucket(doc_type: str) -> DocTypeScore:
        return report.by_doc_type.setdefault(doc_type, DocTypeScore())

    # --- Bank transactions: multiset match per document -------------------
    def txn_multiset(facts: list[Fact]) -> dict[str, Counter]:
        out: dict[str, Counter] = defaultdict(Counter)
        for f in facts:
            if f.fact_type == FactType.BANK_TXN:
                out[f.source_doc][(f.value_date, f.value_pence,
                                   f.attrs.get("direction"))] += 1
        return out

    exp_txns = txn_multiset(expected)
    got_txns = txn_multiset(extracted)
    for doc, exp_counter in exp_txns.items():
        got_counter = got_txns.get(doc, Counter())
        matched = sum((exp_counter & got_counter).values())
        total = sum(exp_counter.values())
        score = bucket("bank_statement")
        score.matched += matched
        score.expected += total
        if matched < total:
            missing = exp_counter - got_counter
            sample = next(iter(missing))
            score.mismatches.append(
                f"{doc}: {total - matched} txn(s) missed/wrong, "
                f"e.g. {sample[0]} {sample[1]}p {sample[2]}")

    # --- Scalars ------------------------------------------------------------
    extracted_scalars = {_scalar_key(f): f for f in extracted
                         if f.fact_type != FactType.BANK_TXN}
    for exp in expected:
        if exp.fact_type == FactType.BANK_TXN:
            continue
        score = bucket(exp.doc_type)
        score.expected += 1
        got = extracted_scalars.get(_scalar_key(exp))
        if got is None:
            score.mismatches.append(
                f"{exp.source_doc} {exp.fact_type}: not extracted")
        elif _value_key(got) != _value_key(exp):
            score.mismatches.append(
                f"{exp.source_doc} {exp.fact_type}: "
                f"expected {_value_key(exp)}, got {_value_key(got)}")
        else:
            score.matched += 1
    return report
