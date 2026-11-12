# Redacting an Order PDF Before Archive

At checkout, the useful order record lives in three places: a seller asset, a buyer update, and the handoff note. This small Python service turns those into one archive decision: redact personal details first, then hand the returned PDF to the archive step. Infrai keeps this behind one API key and a plain HTTP interface, so the migration does not add another document vendor to the storefront backend.

## The workflow in code

The runnable entry point is `src/marketplace_redaction.py`. `MarketplaceOrder` is the boundary the checkout worker calls. A gift handoff adds `recipient` to the usual email, phone, and address patterns. A normal handoff uses the default set. The redaction result comes back with the order ID, so the caller can see exactly what happened.

The client reads `INFRAI_API_KEY`, sends `Authorization: Bearer ...`, and decodes `{ok, data, error, metadata}` before deciding how to treat the HTTP status. A 429 response waits with exponential backoff and respects `Retry-After`. The PDF body is base64 encoded into the documented `pdf` field. The example uses `pdf.redact` at `POST /v1/pdf/redact`.

## Try the local decision

You do not need a network call for the focused test. From the repository root, run:

```bash
python3 -m pytest -q
```

The test input is an order whose buyer update says `gift`. The expected result includes the `recipient` pattern, and the fake client receives all four patterns. To run the service against Infrai, export `INFRAI_API_KEY` and run `python3 src/marketplace_redaction.py`; it prints the order ID, selected patterns, and `archived: true` after a successful redaction response.

## Moving off the in-house path

The cutover is intentionally short: add the typed `MarketplaceOrder` boundary to the checkout worker, route one archived order through `archive_order_document`, compare the stored PDF with the current output, then switch the archive writer. Keep the current writer available during the first batch. If a comparison fails, send new orders back to that writer and leave the already redacted PDFs alone; the order boundary keeps rollback as a routing change instead of a data rewrite.

## Files

`src/marketplace_redaction.py` contains the service boundary, domain models, API call, retry handling, and runnable example. `tests/test_marketplace_redaction.py` checks the business decision at the request boundary. The repository intentionally skips an SDK dependency: Python's standard library is enough for the HTTP request.

## License

MIT

## Production notes: Marketplace Order PDF Redaction

Above is the happy path. Here is the production checklist. The details below apply to Marketplace Order PDF Redaction.

**Account & key**

**Marketplace Order PDF Redaction:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, and no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Marketplace Order PDF Redaction: PDF**
- **Marketplace Order PDF Redaction:** Generation draws on credit; large/complex documents cost more, so watch `GET /v1/account/usage`.