"""Mutation engine: plant known discrepancies into the data room spec.

Each mutation edits the DataRoomSpec (never the ledger) and returns a
MutationRecord — the ground truth the eval harness scores against. The
taxonomy maps every mutation to the check that should catch it; one
mutation (spouse on payroll) is deliberately outside POC check scope.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field

from diligence.dataroom.spec import BankLineData, DataRoomSpec


@dataclass(frozen=True)
class MutationRecord:
    id: str
    check_id: str  # check expected to catch it (see docs/03-check-catalog.md)
    severity: str  # red | amber
    description: str
    affected_documents: list[str]
    catchable_in_poc: bool
    details: dict = field(default_factory=dict)


def _pounds(pence: int) -> int:
    return round(pence / 100) * 100


def _rebalance_bank(spec: DataRoomSpec) -> None:
    """Recompute running balances after bank-line edits."""
    balance = spec.bank_statements[0].opening_balance
    for stmt in spec.bank_statements:
        stmt.opening_balance = balance
        stmt.lines.sort(key=lambda ln: ln.date)
        for line in stmt.lines:
            balance += line.paid_in - line.paid_out
            line.balance = balance
        stmt.closing_balance = balance


# --- Mutations ---------------------------------------------------------------


@dataclass(frozen=True)
class InflateMgmtRevenueFy2:
    """P&L revenue ~11% above what the bank deposits support (FY2 months)."""
    pct: float = 0.11

    def apply(self, spec: DataRoomSpec) -> MutationRecord:
        months = spec.management_pnl.months[12:]
        total_delta = 0
        for m in months:
            delta = _pounds(round(m.revenue * self.pct))
            m.revenue += delta
            total_delta += delta
        return MutationRecord(
            id="M01_pnl_revenue_inflated",
            check_id="T1.VAT_TRIANGLE", severity="red",
            description=f"Management P&L revenue inflated {self.pct:.0%} in "
                        f"FY2 — unsupported by bank deposits or VAT Box 6.",
            affected_documents=["management_pnl.pdf"],
            catchable_in_poc=True,
            details={"period": "FY2026", "delta_pence": total_delta,
                     "pct": self.pct},
        )


@dataclass(frozen=True)
class UnderstateVatQ3:
    """VAT return for Oct–Dec 2024 underdeclares outputs (Boxes 1/3/5/6)."""
    quarter_index: int = 2
    pct: float = 0.09

    def apply(self, spec: DataRoomSpec) -> MutationRecord:
        ret = spec.vat_returns[self.quarter_index]
        old_box6 = ret.box6
        ret.box1 = round(ret.box1 * (1 - self.pct))
        ret.box3 = ret.box1 + ret.box2
        ret.box5 = ret.box3 - ret.box4
        ret.box6 = _pounds(round(ret.box6 * (1 - self.pct)))
        doc = f"vat_return_{ret.period_end:%Y-%m}.pdf"
        return MutationRecord(
            id="M02_vat_box6_understated",
            check_id="T1.VAT_TRIANGLE", severity="red",
            description=f"VAT return {ret.period_start:%b}–{ret.period_end:%b %Y} "
                        f"underdeclares outputs by {self.pct:.0%} vs P&L revenue "
                        f"and card/cash deposits.",
            affected_documents=[doc],
            catchable_in_poc=True,
            details={"quarter_end": str(ret.period_end),
                     "box6_before": old_box6, "box6_after": ret.box6},
        )


@dataclass(frozen=True)
class UndiscloseLoan:
    """Funding Circle loan hidden from accounts and the seller's claims.

    The Companies House charge remains registered and the monthly
    repayments remain visible in the bank statements.
    """

    def apply(self, spec: DataRoomSpec) -> MutationRecord:
        balances = [acc.balance for acc in spec.statutory_accounts]
        if spec.statutory_accounts[0].prior is not None:
            balances.append(spec.statutory_accounts[0].prior)
        for b in balances:
            hidden = b.note_loan_within_year + b.note_loan_after_year
            b.creditors_within_year -= b.note_loan_within_year
            b.creditors_after_year -= b.note_loan_after_year
            b.retained_earnings += hidden  # keeps the balance sheet tying
            b.note_loan_within_year = 0
            b.note_loan_after_year = 0
        for acc in spec.statutory_accounts:
            acc.loan_disclosure = None
        for claim in spec.seller_claims:
            if claim.metric == "total_borrowings":
                claim.value_gbp = 0
                claim.text = ("The business has no borrowings — everything "
                              "was paid off years ago.")
        return MutationRecord(
            id="M03_undisclosed_loan",
            check_id="T3.CHARGES", severity="red",
            description="£40k Funding Circle loan removed from statutory "
                        "accounts and denied in seller claims; CH charge "
                        "139775810001 remains outstanding and repayments of "
                        "£801.52/month remain visible in bank statements.",
            affected_documents=["statutory_accounts_fye2025.pdf",
                                "statutory_accounts_fye2026.pdf",
                                "claims.json"],
            catchable_in_poc=True,
            details={"lender": "Funding Circle Ltd",
                     "charge_id": "139775810001",
                     "monthly_repayment_pence": 801_52},
        )


@dataclass(frozen=True)
class MoveLeaseBreak:
    """Break clause moved to ~9 months after a mid-2026 acquisition."""
    new_break: dt.date = dt.date(2027, 1, 15)
    new_notice_months: int = 3

    def apply(self, spec: DataRoomSpec) -> MutationRecord:
        old = spec.lease.break_date
        spec.lease.break_date = self.new_break
        spec.lease.break_notice_months = self.new_notice_months
        return MutationRecord(
            id="M04_lease_break_moved",
            check_id="T3.LEASE", severity="red",
            description=f"Lease break clause at {self.new_break} with only "
                        f"{self.new_notice_months} months' notice — landlord "
                        f"can end the lease ~9 months after completion.",
            affected_documents=["lease.pdf"],
            catchable_in_poc=True,
            details={"break_before": str(old), "break_after": str(self.new_break),
                     "notice_months": self.new_notice_months},
        )


@dataclass(frozen=True)
class UnderstateStatTurnoverFy1:
    """Statutory accounts FY1 turnover below the management accounts."""
    pct: float = 0.08

    def apply(self, spec: DataRoomSpec) -> MutationRecord:
        acc = spec.statutory_accounts[0]
        delta = _pounds(round(acc.turnover * self.pct))
        old_tax = acc.tax
        acc.turnover -= delta
        acc.profit_before_tax -= delta
        acc.tax = max(0, _pounds(round(acc.profit_before_tax * 0.19)))
        tax_delta = old_tax - acc.tax
        b = acc.balance
        b.cash -= delta
        b.note_ct -= tax_delta
        b.creditors_within_year -= tax_delta
        b.retained_earnings -= delta - tax_delta
        return MutationRecord(
            id="M05_stat_vs_mgmt_gap",
            check_id="T1.STAT_VS_MGMT", severity="red",
            description=f"FYE2025 statutory accounts turnover {self.pct:.0%} "
                        f"below the management P&L for the same 12 months.",
            affected_documents=["statutory_accounts_fye2025.pdf",
                                "statutory_accounts_fye2026.pdf"],
            catchable_in_poc=True,
            details={"delta_pence": delta},
        )


@dataclass(frozen=True)
class InflateAugustClaim:
    """Seller's 'best month' claim well above actuals."""
    claimed: int = 52_000_00

    def apply(self, spec: DataRoomSpec) -> MutationRecord:
        claim = next(c for c in spec.seller_claims
                     if c.metric == "monthly_revenue_net")
        actual = claim.value_gbp
        claim.value_gbp = self.claimed
        claim.text = (f"August is our best month — we did about "
                      f"£{self.claimed // 100:,} last August.")
        return MutationRecord(
            id="M06_seller_claim_inflated",
            check_id="T1.CLAIM_LEDGER", severity="red",
            description=f"Seller claims £{self.claimed // 100:,} August revenue; "
                        f"monthly actuals are far lower.",
            affected_documents=["claims.json"],
            catchable_in_poc=True,
            details={"claimed_pence": self.claimed,
                     "truthful_pence": actual},
        )


@dataclass(frozen=True)
class UnderstateCardShareClaim:
    """Seller claims a much lower card share than settlements support,
    implying substantial unbanked cash takings ('add-backs')."""
    claimed_ratio: float = 0.60

    def apply(self, spec: DataRoomSpec) -> MutationRecord:
        claim = next(c for c in spec.seller_claims if c.metric == "card_share")
        actual = claim.value_ratio
        claim.value_ratio = self.claimed_ratio
        claim.text = ("Only about 60% goes through the card machine — "
                      "there's a lot of cash on top that never shows in "
                      "the accounts, worth another £20k a year to you.")
        return MutationRecord(
            id="M07_cash_addback_claim",
            check_id="T1.CARD_RECON", severity="red",
            description="Seller claims 60% card share (implying large "
                        "undeclared cash takings); SumUp settlements vs "
                        "banked cash show ~78% card.",
            affected_documents=["claims.json"],
            catchable_in_poc=True,
            details={"claimed_ratio": self.claimed_ratio,
                     "truthful_ratio": actual},
        )


@dataclass(frozen=True)
class ShortPayVatQ2:
    """Bank payment to HMRC for the Jul–Sep 2024 VAT quarter is less than
    the Box 5 liability on the corresponding return."""
    short_by: int = 2_400_00

    def apply(self, spec: DataRoomSpec) -> MutationRecord:
        target = None
        for stmt in spec.bank_statements:
            if stmt.period_start == dt.date(2024, 11, 1):
                for line in stmt.lines:
                    if line.description == "HMRC VAT":
                        target = line
        assert target is not None, "expected HMRC VAT payment in Nov 2024"
        target.paid_out -= self.short_by
        return MutationRecord(
            id="M08_vat_payment_short",
            check_id="T1.VAT_TRIANGLE", severity="amber",
            description=f"Bank payment for the Jul–Sep 2024 VAT return is "
                        f"£{self.short_by // 100:,} less than Box 5 on the "
                        f"return — arrears or an undisclosed time-to-pay "
                        f"arrangement.",
            affected_documents=["bank_statement_2024-11.pdf"],
            catchable_in_poc=True,
            details={"short_by_pence": self.short_by},
        )


@dataclass(frozen=True)
class SpouseOnPayroll:
    """Monthly wages to the director's spouse, invisible in headcount.

    Maps to T2.PAYE_RTI, which is NOT in POC scope — planted to measure
    honest recall against the full taxonomy.
    """
    monthly: int = 950_00

    def apply(self, spec: DataRoomSpec) -> MutationRecord:
        docs = []
        for stmt in spec.bank_statements:
            stmt.lines.append(BankLineData(
                date=stmt.period_end, description="WAGES DEREK HOLT",
                paid_in=0, paid_out=self.monthly, balance=0))
            docs.append(f"bank_statement_{stmt.period_start:%Y-%m}.pdf")
        return MutationRecord(
            id="M09_spouse_on_payroll",
            check_id="T2.PAYE_RTI", severity="amber",
            description="£950/month wages to the director's spouse in every "
                        "bank statement; not reflected in claimed headcount — "
                        "leaves with the seller post-sale.",
            affected_documents=docs,
            catchable_in_poc=False,
            details={"monthly_pence": self.monthly, "counterparty": "Derek Holt"},
        )


@dataclass(frozen=True)
class NonTradingDeposit:
    """Personal money paid into the business account, padding deposits."""
    amount: int = 15_000_00
    on: dt.date = dt.date(2025, 8, 18)

    def apply(self, spec: DataRoomSpec) -> MutationRecord:
        stmt = next(s for s in spec.bank_statements
                    if s.period_start == self.on.replace(day=1))
        stmt.lines.append(BankLineData(
            date=self.on, description="FASTER PAYMENT M HOLT PERSONAL",
            paid_in=self.amount, paid_out=0, balance=0))
        return MutationRecord(
            id="M10_nontrading_deposit",
            check_id="T1.VAT_TRIANGLE", severity="amber",
            description=f"£{self.amount // 100:,} personal transfer into the "
                        f"business account in Aug 2025 — deposits exceed "
                        f"recorded revenue for the quarter.",
            affected_documents=[f"bank_statement_{stmt.period_start:%Y-%m}.pdf"],
            catchable_in_poc=True,
            details={"amount_pence": self.amount, "date": str(self.on)},
        )


DEFAULT_MUTATIONS = [
    InflateMgmtRevenueFy2(),
    UnderstateVatQ3(),
    UndiscloseLoan(),
    MoveLeaseBreak(),
    UnderstateStatTurnoverFy1(),
    InflateAugustClaim(),
    UnderstateCardShareClaim(),
    ShortPayVatQ2(),
    SpouseOnPayroll(),
    NonTradingDeposit(),
]


def apply_mutations(spec: DataRoomSpec, mutations: list) -> list[MutationRecord]:
    records = []
    for m in mutations:
        rec = m.apply(spec)
        records.append(rec)
        spec.mutations.append(asdict(rec))
    _rebalance_bank(spec)
    return records
