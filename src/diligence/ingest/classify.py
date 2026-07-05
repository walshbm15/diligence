"""Content-based document classification.

Real data rooms don't follow naming conventions. Chain: filename heuristic
(free) -> text-layer keyword rules (free, deterministic) -> single-page
vision call (paid, only for image-only PDFs). Unclassifiable files are
surfaced to the caller — never silently skipped.
"""

from __future__ import annotations

import re
from pathlib import Path

from diligence.extraction.facts_builder import doc_type_for

DOC_TYPES = ("statutory_accounts", "management_pnl", "bank_statement",
             "vat_return", "lease")

_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun",
           "jul", "aug", "sep", "oct", "nov", "dec")


def _first_pages_text(pdf_path: Path, pages: int = 2) -> str:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    out = []
    for i in range(min(pages, len(doc))):
        out.append(doc[i].get_textpage().get_text_range())
    doc.close()
    return "\n".join(out)


def classify_by_text(text: str) -> str | None:
    """Keyword rules over the first pages' text layer. Order matters: the
    most distinctive markers first (statutory accounts mention 'profit and
    loss'; leases mention rent; don't let the generic terms win)."""
    t = re.sub(r"\s+", " ", text).lower()
    if not t.strip():
        return None

    if ("vat return" in t or "value added tax return" in t
            or ("box" in t and ("hm revenue" in t or "making tax digital" in t))):
        return "vat_return"
    if (" lease" in t or t.startswith("lease")) and "landlord" in t and "tenant" in t:
        return "lease"
    if ("sort code" in t or "sortcode" in t
            or ("statement" in t and ("paid out" in t or "paid in" in t))):
        return "bank_statement"
    month_hits = sum(1 for m in _MONTHS if f" {m} " in t or f" {m}-" in t)
    if (("management" in t and ("profit" in t or "p&l" in t))
            or (month_hits >= 8 and ("profit" in t or "revenue" in t))):
        return "management_pnl"
    if ("balance sheet" in t or "statement of financial position" in t
            or "micro-entity" in t or "companies act 2006" in t
            or ("registered number" in t and "accounts" in t)):
        return "statutory_accounts"
    return None


def _classify_by_vision(pdf_path: Path, model: str) -> str | None:
    """One-page vision call for image-only PDFs (scans/photos)."""
    import base64
    import io
    import json

    import anthropic
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    image = doc[0].render(scale=150 / 72).to_pil()
    doc.close()
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=70)
    b64 = base64.standard_b64encode(buf.getvalue()).decode()

    client = anthropic.Anthropic(timeout=120.0, max_retries=2)
    response = client.messages.create(
        model=model, max_tokens=64,
        output_config={"format": {"type": "json_schema", "schema": {
            "type": "object",
            "properties": {"doc_type": {
                "type": "string",
                "enum": [*DOC_TYPES, "other"],
            }},
            "required": ["doc_type"],
            "additionalProperties": False,
        }}},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
                                         "media_type": "image/jpeg",
                                         "data": b64}},
            {"type": "text", "text":
                "Classify this UK business document page. statutory_accounts "
                "= filed annual accounts (balance sheet/income statement); "
                "management_pnl = internal monthly profit & loss table; "
                "bank_statement = bank transactions with running balance; "
                "vat_return = HMRC VAT return with boxes 1-9; lease = "
                "commercial property lease. Anything else: other."},
        ]}])
    if response.stop_reason == "refusal":
        return None
    text = next(b.text for b in response.content if b.type == "text")
    label = json.loads(text)["doc_type"]
    return label if label in DOC_TYPES else None


class Classifier:
    """Filename -> text rules -> (optional) vision fallback."""

    def __init__(self, use_llm: bool = True, model: str | None = None):
        import os

        self.use_llm = use_llm
        self.model = model or os.environ.get("EXTRACTION_MODEL",
                                             "claude-opus-4-8")
        self.llm_calls = 0

    def classify(self, pdf_path: Path) -> str | None:
        by_name = doc_type_for(pdf_path.name)
        if by_name:
            return by_name
        try:
            text = _first_pages_text(pdf_path)
        except Exception:  # noqa: BLE001 — corrupt PDF: leave unclassified
            return None
        by_text = classify_by_text(text)
        if by_text:
            return by_text
        if self.use_llm:
            self.llm_calls += 1
            return _classify_by_vision(pdf_path, self.model)
        return None
