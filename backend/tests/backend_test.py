"""TaxPilot Dashboard API regression tests.

Covers all FastAPI endpoints declared in /app/backend/server.py.
Run via: pytest /app/backend/tests/backend_test.py -v --tb=short \
                --junitxml=/app/test_reports/pytest/pytest_results.xml
"""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    # fallback only if not set; real value is read by tests
).rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None


# Read from frontend .env if backend doesn't have it
if not BASE_URL:
    fe_env = "/app/frontend/.env"
    if os.path.exists(fe_env):
        with open(fe_env) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break

assert BASE_URL, "REACT_APP_BACKEND_URL not configured"
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session", autouse=True)
def reseed(client):
    """Ensure clean demo data before tests."""
    r = client.post(f"{API}/seed/reset", timeout=30)
    assert r.status_code == 200, f"Seed failed: {r.text}"
    yield
    # Reseed at end to restore state for next runs
    client.post(f"{API}/seed/reset", timeout=30)


# --- Health ---
def test_health(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


# --- Profile ---
def test_get_profile(client):
    r = client.get(f"{API}/profile")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "firm-demo-001"
    assert data["name"] == "Kumar & Associates"
    assert "alert_preferences" in data
    assert data["alert_preferences"]["whatsapp_enabled"] is True


# --- Dashboard ---
def test_dashboard_summary(client):
    r = client.get(f"{API}/dashboard/summary")
    assert r.status_code == 200
    d = r.json()
    for k in ("kpis", "client_health", "upcoming_deadlines", "top_missed_tds"):
        assert k in d
    assert d["kpis"]["total_clients"] == 3
    assert d["kpis"]["missed_tds"] > 0
    assert isinstance(d["upcoming_deadlines"], list)
    assert isinstance(d["top_missed_tds"], list)


# --- Clients ---
def test_list_clients(client):
    r = client.get(f"{API}/clients")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 3
    for c in d["clients"]:
        assert c["health"] in ("safe", "at_risk", "critical")
        assert "open_mismatches" in c
        assert "missed_tds" in c


def test_clients_search(client):
    r = client.get(f"{API}/clients", params={"search": "Acme"})
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 1
    assert "Acme" in d["clients"][0]["name"]


def test_clients_health_filter(client):
    r = client.get(f"{API}/clients", params={"health": "critical"})
    assert r.status_code == 200
    d = r.json()
    for c in d["clients"]:
        assert c["health"] == "critical"


def test_get_client_detail(client):
    r = client.get(f"{API}/clients/client-001")
    assert r.status_code == 200
    d = r.json()
    assert d["id"] == "client-001"
    assert d["gstin"] == "27AABCA1234E1Z5"


def test_get_client_not_found(client):
    r = client.get(f"{API}/clients/nope-xyz")
    assert r.status_code == 404


# --- Documents ---
def test_list_documents(client):
    r = client.get(f"{API}/documents")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 6
    assert all("client_name" in doc for doc in d["documents"])


def test_documents_filter_by_client(client):
    r = client.get(f"{API}/documents", params={"client_id": "client-001"})
    assert r.status_code == 200
    d = r.json()
    assert all(doc["client_id"] == "client-001" for doc in d["documents"])
    assert d["count"] >= 3


def test_upload_document(client):
    fake = io.BytesIO(b"%PDF-1.4 fake pdf content for testing")
    files = {"file": ("TEST_upload.pdf", fake, "application/pdf")}
    data = {"client_id": "client-001", "doc_type": "invoice"}
    s = requests.Session()  # no JSON header
    r = s.post(f"{API}/documents/upload", files=files, data=data)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ocr_status"] == "processing"
    assert body["original_filename"] == "TEST_upload.pdf"
    assert "id" in body


def test_upload_invalid_doctype(client):
    s = requests.Session()
    files = {"file": ("x.pdf", io.BytesIO(b"x"), "application/pdf")}
    r = s.post(f"{API}/documents/upload",
               files=files,
               data={"client_id": "client-001", "doc_type": "bogus"})
    assert r.status_code == 400


# --- GST ---
def test_gst_recon_summary(client):
    r = client.get(f"{API}/gst/reconciliation/summary",
                   params={"client_id": "client-001", "month": 4, "year": 2025})
    assert r.status_code == 200
    d = r.json()
    assert "itc_summary" in d
    for k in ("safe_to_claim", "at_risk", "missing_in_books"):
        assert k in d["itc_summary"]
        assert "amount" in d["itc_summary"][k]


def test_gst_mismatches(client):
    r = client.get(f"{API}/gst/mismatches")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 6


def test_gst_mismatches_filter(client):
    r = client.get(f"{API}/gst/mismatches", params={"mismatch_type": "missing_in_2a"})
    assert r.status_code == 200
    d = r.json()
    for m in d["mismatches"]:
        assert m["type"] == "missing_in_2a"


def test_resolve_mismatch(client):
    r = client.get(f"{API}/gst/mismatches")
    mid = r.json()["mismatches"][0]["id"]
    r2 = client.post(f"{API}/gst/mismatches/{mid}/resolve",
                     json={"notes": "TEST_resolved", "resolved_by": "tester"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "resolved"
    # verify persisted
    r3 = client.get(f"{API}/gst/mismatches",
                    params={"is_resolved": "true"})
    assert any(m["id"] == mid for m in r3.json()["mismatches"])


def test_resolve_mismatch_404(client):
    r = client.post(f"{API}/gst/mismatches/nope/resolve", json={})
    assert r.status_code == 404


# --- TDS ---
def test_tds_summary(client):
    r = client.get(f"{API}/tds/summary")
    assert r.status_code == 200
    d = r.json()
    assert "overall" in d and "quarterly" in d and "by_section" in d
    assert d["overall"]["entries"] == 5
    assert d["overall"]["tds_missed"] > 0
    # quarters present
    for q in ("Q1", "Q2", "Q3", "Q4"):
        assert q in d["quarterly"]


def test_tds_missed(client):
    r = client.get(f"{API}/tds/missed")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 3
    # Sorted by penalty desc
    pens = [e.get("penalty_estimate", 0) for e in d["entries"]]
    assert pens == sorted(pens, reverse=True)


def test_tds_vendors(client):
    r = client.get(f"{API}/tds/vendors")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] >= 1
    for v in d["vendors"]:
        assert "compliance_pct" in v
        assert "vendor_pan" in v


# --- Compliance ---
def test_compliance_calendar(client):
    r = client.get(f"{API}/compliance/calendar")
    assert r.status_code == 200
    d = r.json()
    assert d["count"] == 9
    for item in d["items"]:
        assert "days_to_due" in item
        assert "client_name" in item


def test_mark_filed(client):
    r = client.get(f"{API}/compliance/calendar")
    item_id = r.json()["items"][0]["id"]
    r2 = client.post(f"{API}/compliance/{item_id}/mark-filed",
                     json={"filed_by": "TEST_user"})
    assert r2.status_code == 200
    assert r2.json()["status"] == "filed"


def test_mark_filed_404(client):
    r = client.post(f"{API}/compliance/no-such-id/mark-filed", json={})
    assert r.status_code == 404


# --- Settings ---
def test_update_profile(client):
    payload = {"name": "Kumar & Associates", "email": "office@kumarca.in", "plan": "growth"}
    r = client.put(f"{API}/settings/profile", json=payload)
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "Kumar & Associates"
    assert d["plan"] == "growth"


def test_update_profile_no_fields(client):
    r = client.put(f"{API}/settings/profile", json={"foo": "bar"})
    assert r.status_code == 400


def test_update_alerts(client):
    payload = {
        "whatsapp_enabled": False,
        "email_enabled": True,
        "reminder_7day": True,
        "reminder_1day": False,
        "escalation_on_missed": True,
    }
    r = client.put(f"{API}/settings/alerts", json=payload)
    assert r.status_code == 200
    d = r.json()
    assert d["alert_preferences"]["whatsapp_enabled"] is False
    # Verify persistence
    r2 = client.get(f"{API}/profile")
    assert r2.json()["alert_preferences"]["whatsapp_enabled"] is False


# --- Seed reset (last) ---
def test_seed_reset(client):
    r = client.post(f"{API}/seed/reset")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "reseeded"
    assert d["counts"]["clients"] == 3
    assert d["counts"]["documents"] == 6
    assert d["counts"]["mismatches"] == 6
    assert d["counts"]["tds_entries"] == 5
    assert d["counts"]["compliance_items"] == 9
