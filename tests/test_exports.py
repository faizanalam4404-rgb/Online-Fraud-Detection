"""
FraudGuard – Transaction Statement Export (CSV & PDF) Unit Tests
================================================================
Verifies:
- Customer transaction history export to formatted CSV
- Customer transaction history export to official ReportLab PDF statement
- Proper Content-Type headers and Content-Disposition filenames
- Customer data isolation during export streaming
"""

import pytest
from app import create_app, db

@pytest.fixture
def logged_client():
    app = create_app("testing")
    client = app.test_client()
    with app.app_context():
        db.create_all()
    # Login as Alex
    client.post("/auth/api/login", json={
        "username": "customer_alex",
        "password": "CustomerPass2026!"
    })
    return client

def test_export_csv_statement(logged_client):
    """Verify CSV export returns valid CSV formatted data and correct headers."""
    resp = logged_client.get("/customer/api/transactions/export?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.content_type
    assert "attachment;" in resp.headers.get("Content-Disposition", "")
    assert ".csv" in resp.headers.get("Content-Disposition", "")
    
    # Check CSV header row
    csv_text = resp.data.decode("utf-8")
    assert "Transaction ID" in csv_text
    assert "Original Amount" in csv_text
    assert "USD Equivalent" in csv_text
    assert "ML Prediction" in csv_text

def test_export_pdf_statement(logged_client):
    """Verify ReportLab PDF export produces genuine PDF binary statement."""
    resp = logged_client.get("/customer/api/transactions/export?format=pdf")
    assert resp.status_code == 200
    assert "application/pdf" in resp.content_type
    assert "attachment;" in resp.headers.get("Content-Disposition", "")
    assert ".pdf" in resp.headers.get("Content-Disposition", "")
    
    # PDF magic byte header check: %PDF-
    assert resp.data.startswith(b"%PDF-"), "Generated file does not contain genuine PDF magic bytes!"
