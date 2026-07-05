"""Extractors: PDF in, schema-conforming JSON out.

ClaudeExtractor sends the PDF as a base64 document block and constrains the
response with output_config.format (structured outputs), so the reply is
guaranteed-valid JSON matching the doc-type schema. FakeExtractor serves
canned JSON for tests and offline pipeline runs.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from diligence.extraction.schemas import PROMPTS, SCHEMAS

DEFAULT_MODEL = "claude-opus-4-8"

# USD per million tokens (input, output) — for the POC cost log.
PRICES = {
    "claude-opus-4-8": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


@dataclass
class UsageLog:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    model: str = DEFAULT_MODEL

    def add(self, usage) -> None:
        self.calls += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens

    @property
    def cost_usd(self) -> float:
        inp, out = PRICES.get(self.model, PRICES[DEFAULT_MODEL])
        return (self.input_tokens * inp + self.output_tokens * out) / 1_000_000


class ClaudeExtractor:
    """Live extraction via the Claude API. Requires credentials
    (ANTHROPIC_API_KEY or an `ant auth login` profile)."""

    name = "claude"

    # Hard wall-clock cap per attempt. A wedged connection can trickle just
    # enough to keep resetting httpx's per-chunk read timeout and hang a run
    # for hours; per-chunk timeouts are NOT a deadline.
    ATTEMPT_DEADLINE_S = 600

    def __init__(self, model: str | None = None):
        import anthropic
        import httpx

        self.model = model or os.environ.get("EXTRACTION_MODEL", DEFAULT_MODEL)
        self.client = anthropic.Anthropic(
            timeout=httpx.Timeout(120.0, connect=10.0), max_retries=2)
        self.usage = UsageLog(model=self.model)

    def extract(self, pdf_path: Path, doc_type: str) -> dict:
        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import TimeoutError as FuturesTimeout

        import anthropic

        last_exc: Exception | None = None
        for attempt in range(3):
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(self._extract_once, pdf_path, doc_type)
            try:
                return future.result(timeout=self.ATTEMPT_DEADLINE_S)
            except FuturesTimeout:
                last_exc = TimeoutError(
                    f"extraction exceeded {self.ATTEMPT_DEADLINE_S}s deadline")
            except (anthropic.APIConnectionError, anthropic.RateLimitError,
                    anthropic.InternalServerError) as exc:
                last_exc = exc
            finally:
                # Don't block on a wedged worker thread; let it die with the
                # abandoned socket.
                executor.shutdown(wait=False, cancel_futures=True)
            time.sleep(5 * (attempt + 1))
        raise last_exc

    def _extract_once(self, pdf_path: Path, doc_type: str) -> dict:
        pdf_b64 = base64.standard_b64encode(pdf_path.read_bytes()).decode()
        with self.client.messages.stream(
            model=self.model,
            max_tokens=32000,
            output_config={"format": {"type": "json_schema",
                                      "schema": SCHEMAS[doc_type]}},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "document",
                     "source": {"type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64}},
                    {"type": "text", "text": PROMPTS[doc_type]},
                ],
            }],
        ) as stream:
            message = stream.get_final_message()
        self.usage.add(message.usage)
        if message.stop_reason == "refusal":
            raise RuntimeError(f"extraction refused for {pdf_path.name}")
        text = next(b.text for b in message.content if b.type == "text")
        return json.loads(text)


@dataclass
class FakeExtractor:
    """Deterministic extractor for tests: canned JSON keyed by file name."""

    responses: dict[str, dict] = field(default_factory=dict)
    name: str = "fake"
    usage: UsageLog = field(default_factory=UsageLog)

    def extract(self, pdf_path: Path, doc_type: str) -> dict:
        return self.responses[pdf_path.name]
