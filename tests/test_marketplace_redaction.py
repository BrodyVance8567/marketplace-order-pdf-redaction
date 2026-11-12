from src.marketplace_redaction import ArchiveResult, MarketplaceOrder, archive_order_document


class RecordingClient:
    def __init__(self):
        self.calls = []

    def redact(self, pdf, patterns):
        self.calls.append((pdf, patterns))
        return {"ok": True, "data": {"pdf": "redacted-pdf"}}


def test_gift_handoff_redacts_recipient_details_before_archive():
    client = RecordingClient()
    order = MarketplaceOrder("order-7", b"invoice", "Please make it a gift", "handoff to recipient")

    result = archive_order_document(order, client)

    assert isinstance(result, ArchiveResult)
    assert result.redacted_pdf == "redacted-pdf"
    assert result.patterns == ("email", "phone", "address", "recipient")
    assert client.calls[0][1] == ["email", "phone", "address", "recipient"]
