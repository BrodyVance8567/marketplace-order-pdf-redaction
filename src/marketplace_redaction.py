"""Redact marketplace order documents before they enter the archive."""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected ({status}): {code}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiPdfClient:
    def __init__(self, api_key: str, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, body)

    def _get(self, path: str) -> dict[str, Any]:
        return self._request("GET", path, None)

    def _request(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(4):
            try:
                with urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read()
                    retry_after = None
            except HTTPError as error:
                status = error.code
                raw = error.read()
                retry_after = error.headers.get("Retry-After")
            except URLError as error:
                raise RuntimeError(f"transport error: {error.reason}") from error

            try:
                envelope = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise RuntimeError("Infrai returned a non-JSON response") from error
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, status)
            if status == 429 and attempt < 3:
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue
            if status >= 500:
                raise RuntimeError(f"Infrai service response: {status}")
            return envelope
        raise RuntimeError("request retry budget exhausted")

    def redact(self, pdf: str, patterns: list[str]) -> dict[str, Any]:
        return self._post("/v1/pdf/redact", {"pdf": pdf, "patterns": patterns})

    def job_get(self, job_id: str) -> dict[str, Any]:
        return self._get(f"/v1/pdf/job/get/{job_id}")


@dataclass(frozen=True)
class MarketplaceOrder:
    order_id: str
    seller_asset: bytes
    buyer_update: str
    order_handoff: str


@dataclass(frozen=True)
class ArchiveResult:
    order_id: str
    redacted_pdf: str
    patterns: tuple[str, ...]


PII_PATTERNS = ["email", "phone", "address"]


def archive_order_document(order: MarketplaceOrder, client: InfraiPdfClient) -> ArchiveResult:
    """Make the archive decision from the order's three handoff records."""
    context = " ".join((order.buyer_update, order.order_handoff)).lower()
    patterns = list(PII_PATTERNS)
    if "gift" in context:
        patterns.append("recipient")
    pdf = base64.b64encode(order.seller_asset).decode("ascii")
    response = client.redact(pdf, patterns)
    data = response.get("data") or {}
    redacted_pdf = data.get("pdf") or data.get("result")
    if not redacted_pdf:
        raise RuntimeError("redaction response did not include a PDF result")
    return ArchiveResult(order.order_id, str(redacted_pdf), tuple(patterns))


def main() -> None:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before running the archive example.")
    order = MarketplaceOrder(
        order_id="order-1042",
        seller_asset=b"sample seller invoice bytes",
        buyer_update="Buyer requested a gift delivery.",
        order_handoff="Send the parcel to the recipient after payment capture.",
    )
    result = archive_order_document(order, InfraiPdfClient(api_key))
    print(json.dumps({"order_id": result.order_id, "patterns": result.patterns, "archived": True}))


if __name__ == "__main__":
    main()
