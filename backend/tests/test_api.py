import csv
import io
import json

import pytest

OPTIONS = dict(
    date_column="Date",
    description_column="Description",
    amount_column="Amount",
    mode="signed",
    date_format="iso",
    sign_convention="negative_outgoing",
    currency="USD",
)


def upload(client, body="2026-10-01,FIGMA,-10\n", options=None):
    return client.post(
        "/api/statements",
        files={"file": ("test.csv", ("Date,Description,Amount\n" + body).encode(), "text/csv")},
        data={"options": json.dumps(options or OPTIONS)},
    )


def rows(client, sid):
    return client.get(f"/api/statements/{sid}/transactions").json()["items"]


def patch(client, row, **data):
    return client.patch(
        f"/api/transactions/{row['id']}/review", json={"version": row["version"], **data}
    )


def test_full_import_review_export_and_reset(client):
    result = upload(client, "2026-10-01,UNKNOWN MERCHANT,-20\n")
    assert result.status_code == 200
    sid = result.json()["statement"]["id"]
    row = rows(client, sid)[0]
    assert row["needs_review"]
    assert client.get(f"/api/statements/{sid}/export?reviewed_only=true").status_code == 409
    saved = patch(client, row, action="save", kind="expense", category="office")
    assert saved.status_code == 200
    persisted = rows(client, sid)[0]
    assert persisted["reviewed"] and persisted["category"] == "office"
    summary = client.get(f"/api/statements/{sid}/summary").json()
    assert summary["totals"]["net_expense_minor"] == 2000
    assert not summary["provisional"]
    exported = client.get(f"/api/statements/{sid}/export?reviewed_only=true")
    exported_rows = list(csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff"))))
    assert exported_rows[0]["amount"] == "-20.00"
    assert exported_rows[0]["status"] == "reviewed"
    assert len(client.get(f"/api/transactions/{row['id']}/history").json()) == 1
    assert patch(client, row, action="reset").status_code == 409  # stale edit
    assert patch(client, persisted, action="reset").status_code == 200
    assert rows(client, sid)[0]["needs_review"]


def test_atomic_failure_and_idempotency(client):
    assert upload(client, "2026-10-01,FIGMA,-10\n2026-99-99,broken,-20").status_code == 422
    assert client.get("/api/statements").json() == []
    first = upload(client).json()
    second = upload(client).json()
    assert first["statement"]["id"] == second["statement"]["id"]
    assert second["already_imported"]
    assert len(client.get("/api/statements").json()) == 1


def test_duplicates_are_not_silently_deleted(client):
    sid = upload(client, "2026-10-01,FIGMA,-10\n2026-10-01,FIGMA,-10\n").json()["statement"]["id"]
    items = rows(client, sid)
    assert len(items) == 2 and all(r["needs_review"] for r in items)
    assert patch(client, items[0], action="duplicate", duplicate_action="keep").status_code == 200
    assert (
        patch(client, items[1], action="duplicate", duplicate_action="exclude").status_code == 200
    )
    report = client.get(f"/api/statements/{sid}/summary").json()
    assert report["counts"]["excluded"] == 1
    assert report["totals"]["net_expense_minor"] == 1000
    assert report["totals"]["imported_signed_minor"] == -2000
    assert report["totals"]["included_signed_minor"] == -1000
    assert report["totals"]["excluded_signed_minor"] == -1000
    assert not report["provisional"]
    kept = rows(client, sid)[0]
    assert patch(client, kept, action="duplicate", duplicate_action="exclude").status_code == 422
    excluded = rows(client, sid)[1]
    assert patch(client, excluded, action="duplicate", duplicate_action="reset").status_code == 200
    assert rows(client, sid)[1]["needs_review"]


def test_legitimate_duplicate_can_be_kept(client):
    sid = upload(client, "2026-10-01,FIGMA,-10\n2026-10-01,FIGMA,-10\n").json()["statement"]["id"]
    for row in rows(client, sid):
        assert patch(client, row, action="duplicate", duplicate_action="keep").status_code == 200
    assert client.get(f"/api/statements/{sid}/summary").json()["totals"]["expense_minor"] == 2000


def test_refunds_transfers_unresolved_and_reconciliation(client):
    sid = upload(
        client,
        "2026-10-01,FIGMA,-10\n2026-10-02,FIGMA REFUND,15\n"
        "2026-10-03,TRANSFER TO SAVINGS,-100\n2026-10-04,UNKNOWN,30\n"
        "2026-10-05,CLIENT INVOICE PAYMENT,200\n",
    ).json()["statement"]["id"]
    report = client.get(f"/api/statements/{sid}/summary").json()
    totals = report["totals"]
    assert totals["net_expense_minor"] == -500  # refunds can exceed this statement's purchases
    assert totals["income_minor"] == 20000
    assert totals["transfer_out_minor"] == 10000
    assert totals["unresolved_in_minor"] == 3000
    assert report["reconciled"] and report["provisional"]
    exported = client.get(f"/api/statements/{sid}/export?kind=summary")
    values = {
        r["metric"]: r["amount"]
        for r in csv.DictReader(io.StringIO(exported.text.lstrip("\ufeff")))
        if r["section"] == "totals"
    }
    assert values["net_expense"] == "-5.00"
    assert values["income"] == "200.00"


@pytest.mark.parametrize(
    "kind,category",
    [
        ("expense", "income"),
        ("income", "income"),
        ("refund", "software"),
        ("unknown", "uncategorized"),
    ],
)
def test_invalid_review_combinations(client, kind, category):
    sid = upload(client).json()["statement"]["id"]
    row = rows(client, sid)[0]
    assert patch(client, row, action="save", kind=kind, category=category).status_code == 422


def test_formula_injection_text_is_escaped(client):
    sid = upload(client, "2026-10-01,=1+1,-10\n").json()["statement"]["id"]
    content = client.get(f"/api/statements/{sid}/export").text.lstrip("\ufeff")
    row = next(csv.DictReader(io.StringIO(content)))
    assert row["description"] == "'=1+1"
    assert row["amount"] == "-10.00"


def test_delete_cascades_and_unknown_ids(client):
    sid = upload(client).json()["statement"]["id"]
    row = rows(client, sid)[0]
    patch(client, row, action="save", kind="expense", category="software")
    assert client.delete(f"/api/statements/{sid}").status_code == 204
    assert client.get("/api/statements").json() == []
    assert client.get(f"/api/transactions/{row['id']}/history").status_code == 404
    assert client.get(f"/api/statements/{sid}/transactions").status_code == 404


def test_filters_and_cross_site_write(client):
    sid = upload(client, "2026-10-01,FIGMA,-10\n2026-10-02,UNKNOWN,-5").json()["statement"]["id"]
    assert (
        client.get(f"/api/statements/{sid}/transactions?status=needs_review").json()["total"] == 1
    )
    assert client.get(f"/api/statements/{sid}/transactions?search=figma").json()["total"] == 1
    response = client.delete(
        f"/api/statements/{sid}", headers={"origin": "https://attacker.example"}
    )
    assert response.status_code == 403


def test_upload_limits_and_preview(client):
    content = b"Date,Description,Amount\n2026-01-01,FIGMA,-1"
    assert (
        client.post("/api/imports/preview", files={"file": ("a.csv", content)}).json()["row_count"]
        == 1
    )
    assert (
        client.post("/api/imports/preview", files={"file": ("big.csv", b"x" * 2097153)}).status_code
        == 413
    )


def test_duplicate_correction_does_not_resolve_duplicate_warning(client):
    sid = upload(client, "2026-10-01,UNKNOWN,-10\n2026-10-01,UNKNOWN,-10").json()["statement"]["id"]
    row = rows(client, sid)[0]
    result = patch(client, row, action="save", kind="expense", category="other").json()
    assert result["reviewed"] and result["needs_review"]
    result = patch(client, result, action="duplicate", duplicate_action="keep").json()
    assert result["reviewed"] and not result["needs_review"]
