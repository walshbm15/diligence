"""JSON schemas for structured extraction, one per document type.

Every monetary leaf is a {value, confidence} object and every section carries
the 1-based page it was read from — provenance and confidence are extracted,
not inferred (golden rules 2 and 4). Values are pounds as numbers; the facts
builder converts to integer pence.
"""

from __future__ import annotations


def _amount(description: str) -> dict:
    return {
        "type": "object",
        "description": description,
        "properties": {
            "value": {"type": ["number", "null"],
                      "description": "Amount in pounds (negative if shown in "
                                     "brackets); null if absent/illegible"},
            "confidence": {"type": "number",
                           "description": "0-1 confidence in the reading"},
        },
        "required": ["value", "confidence"],
        "additionalProperties": False,
    }


def _amount_solid(description: str) -> dict:
    """Non-nullable amount: structured outputs allow at most 16 union-typed
    parameters per schema, and the statutory-accounts schema exceeds that
    with nullable leaves. Absent/illegible is encoded as value 0 with
    confidence 0 instead."""
    return {
        "type": "object",
        "description": description,
        "properties": {
            "value": {"type": "number",
                      "description": "Amount in pounds (negative if shown in "
                                     "brackets); 0 with confidence 0 if the "
                                     "line is absent or illegible"},
            "confidence": {"type": "number",
                           "description": "0-1 confidence in the reading; 0 "
                                          "when the line is absent"},
        },
        "required": ["value", "confidence"],
        "additionalProperties": False,
    }


def _page(description: str = "1-based page number the section appears on") -> dict:
    return {"type": "integer", "description": description}


STATUTORY_ACCOUNTS_SCHEMA = {
    "type": "object",
    "properties": {
        "fy_end": {"type": "string", "description": "Financial year end, YYYY-MM-DD"},
        "income_statement": {
            "type": "object",
            "properties": {
                "page": _page(),
                "turnover": _amount_solid("Turnover"),
                "raw_materials": _amount_solid("Cost of raw materials and consumables "
                                         "(positive number)"),
                "staff_costs": _amount_solid("Staff costs (positive number)"),
                "depreciation": _amount_solid("Depreciation (positive number)"),
                "other_charges": _amount_solid("Other charges (positive number)"),
                "profit_before_tax": _amount_solid("Profit before tax"),
                "tax": _amount_solid("Tax (positive number)"),
            },
            "required": ["page", "turnover", "raw_materials", "staff_costs",
                         "depreciation", "other_charges", "profit_before_tax",
                         "tax"],
            "additionalProperties": False,
        },
        "balance_sheet": {
            "type": "object",
            "properties": {
                "page": _page(),
                "fixed_assets": _amount_solid("Fixed assets"),
                "current_assets": _amount_solid("Current assets"),
                "creditors_within_year": _amount_solid(
                    "Creditors: amounts falling due within one year "
                    "(positive number even if shown in brackets)"),
                "creditors_after_year": _amount_solid(
                    "Creditors: amounts falling due after more than one year "
                    "(positive number)"),
                "net_assets": _amount_solid("Net assets"),
                "share_capital": _amount_solid("Called up share capital"),
                "retained_earnings": _amount_solid("Profit and loss account"),
            },
            "required": ["page", "fixed_assets", "current_assets",
                         "creditors_within_year", "creditors_after_year",
                         "net_assets", "share_capital", "retained_earnings"],
            "additionalProperties": False,
        },
        "notes": {
            "type": "object",
            "properties": {
                "page": _page(),
                "average_employees": {"type": "integer", "description": "0 if not stated"},
                "loan_within_year": _amount_solid(
                    "Bank loans current portion from creditors note; 0 "
                    "if no such line exists"),
                "loan_after_year": _amount_solid(
                    "Bank loans due after one year from creditors note; 0 "
                    "if no such line exists"),
                "loan_disclosure": {
                    "type": "string",
                    "description": "Verbatim loan/charge disclosure paragraph "
                                   "if present, else empty string"},
            },
            "required": ["page", "average_employees", "loan_within_year",
                         "loan_after_year", "loan_disclosure"],
            "additionalProperties": False,
        },
    },
    "required": ["fy_end", "income_statement", "balance_sheet", "notes"],
    "additionalProperties": False,
}


_MGMT_MONTH = {
    "type": "object",
    "properties": {
        "month": {"type": "string", "description": "YYYY-MM"},
        "page": _page(),
        "revenue": _amount("Revenue"),
        "cost_of_sales": _amount("Cost of sales (positive)"),
        "staff_costs": _amount("Staff costs (positive)"),
        "rent": _amount("Rent (positive)"),
        "overheads": _amount("Overheads (positive)"),
        "card_fees": _amount("Card fees (positive)"),
        "depreciation": _amount("Depreciation (positive)"),
        "loan_interest": _amount("Loan interest (positive)"),
        "net_profit": _amount("Net profit"),
    },
    "required": ["month", "page", "revenue", "cost_of_sales", "staff_costs",
                 "rent", "overheads", "card_fees", "depreciation",
                 "loan_interest", "net_profit"],
    "additionalProperties": False,
}

MANAGEMENT_PNL_SCHEMA = {
    "type": "object",
    "properties": {
        "months": {"type": "array", "items": _MGMT_MONTH,
                   "description": "Every month column on every page; exclude "
                                  "the Total column"},
    },
    "required": ["months"],
    "additionalProperties": False,
}


BANK_STATEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "period_start": {"type": "string", "description": "YYYY-MM-DD"},
        "period_end": {"type": "string", "description": "YYYY-MM-DD"},
        "opening_balance": _amount("Opening balance"),
        "closing_balance": _amount("Closing balance"),
        "transactions": {
            "type": "array",
            "description": "Every transaction line, in statement order, "
                           "excluding the OPENING/CLOSING BALANCE rows",
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "description": {"type": "string"},
                    "paid_in": {"type": ["number", "null"],
                                "description": "Pounds, null if blank"},
                    "paid_out": {"type": ["number", "null"],
                                 "description": "Pounds, null if blank"},
                    "balance": {"type": ["number", "null"]},
                    "page": _page("Page this line appears on"),
                    "confidence": {"type": "number"},
                },
                "required": ["date", "description", "paid_in", "paid_out",
                             "balance", "page", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["period_start", "period_end", "opening_balance",
                 "closing_balance", "transactions"],
    "additionalProperties": False,
}


VAT_RETURN_SCHEMA = {
    "type": "object",
    "properties": {
        "period_start": {"type": "string", "description": "YYYY-MM-DD"},
        "period_end": {"type": "string", "description": "YYYY-MM-DD"},
        "page": _page(),
        "box1": _amount("Box 1: VAT due on sales"),
        "box2": _amount("Box 2"),
        "box3": _amount("Box 3: total VAT due"),
        "box4": _amount("Box 4: VAT reclaimed on purchases"),
        "box5": _amount("Box 5: net VAT"),
        "box6": _amount("Box 6: total sales ex VAT"),
        "box7": _amount("Box 7: total purchases ex VAT"),
    },
    "required": ["period_start", "period_end", "page", "box1", "box2", "box3",
                 "box4", "box5", "box6", "box7"],
    "additionalProperties": False,
}


LEASE_SCHEMA = {
    "type": "object",
    "properties": {
        "landlord": {"type": "string"},
        "tenant": {"type": "string"},
        "premises": {"type": "string"},
        "start_date": {"type": "string", "description": "YYYY-MM-DD"},
        "term_years": {"type": "integer"},
        "annual_rent": _amount("Yearly rent in pounds"),
        "rent_page": _page("Page of the rent clause"),
        "break_clause": {
            "type": "object",
            "properties": {
                "exists": {"type": "boolean"},
                "break_date": {"type": ["string", "null"],
                               "description": "YYYY-MM-DD or null"},
                "notice_months": {"type": ["integer", "null"]},
                "page": _page("Page of the break clause (or the page that "
                              "would contain it)"),
                "confidence": {"type": "number"},
            },
            "required": ["exists", "break_date", "notice_months", "page",
                         "confidence"],
            "additionalProperties": False,
        },
        "rent_review_date": {"type": ["string", "null"],
                             "description": "YYYY-MM-DD or null"},
        "inside_lta_1954": {
            "type": "object",
            "properties": {
                "value": {"type": ["boolean", "null"],
                          "description": "true if the lease is INSIDE the "
                                         "security of tenure provisions of "
                                         "the Landlord and Tenant Act 1954"},
                "page": _page(),
                "confidence": {"type": "number"},
            },
            "required": ["value", "page", "confidence"],
            "additionalProperties": False,
        },
    },
    "required": ["landlord", "tenant", "premises", "start_date", "term_years",
                 "annual_rent", "rent_page", "break_clause",
                 "rent_review_date", "inside_lta_1954"],
    "additionalProperties": False,
}


SCHEMAS: dict[str, dict] = {
    "statutory_accounts": STATUTORY_ACCOUNTS_SCHEMA,
    "management_pnl": MANAGEMENT_PNL_SCHEMA,
    "bank_statement": BANK_STATEMENT_SCHEMA,
    "vat_return": VAT_RETURN_SCHEMA,
    "lease": LEASE_SCHEMA,
}

PROMPTS: dict[str, str] = {
    "statutory_accounts": (
        "Extract the figures from these UK micro-entity statutory accounts. "
        "Read only what is printed — never compute or reconcile figures "
        "yourself. Use the CURRENT year column (the left figures column), "
        "not the comparative. Brackets mean negative presentation but report "
        "cost lines as positive numbers per the schema. Report a confidence "
        "of 1.0 only when a figure is perfectly legible; use lower values "
        "when scan quality makes a reading uncertain."
    ),
    "management_pnl": (
        "Extract every month column from this management P&L (there may be "
        "multiple pages, 12 months each). Read only what is printed; do not "
        "compute derived rows yourself. Bracketed figures are costs — report "
        "them as positive numbers. Exclude the Total column. Lower the "
        "confidence for any cell that is hard to read."
    ),
    "bank_statement": (
        "Extract every transaction line from this bank statement in order, "
        "with the exact printed description, amounts and running balance. "
        "Do not sum or reconcile anything. Lower the per-line confidence "
        "when the print is unclear."
    ),
    "vat_return": (
        "Extract the nine boxes from this UK VAT return exactly as printed. "
        "Do not compute box totals yourself even if they look inconsistent — "
        "report what is printed."
    ),
    "lease": (
        "Extract the key terms from this commercial lease: parties, premises, "
        "term, rent, rent review, break clause (date, notice period), and "
        "whether the lease is inside or outside the security of tenure "
        "provisions of Part II of the Landlord and Tenant Act 1954. Quote "
        "dates exactly as written, converted to ISO format."
    ),
}
