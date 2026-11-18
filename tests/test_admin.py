"""
FraudGuard – Administrative Portal & Governance Unit Tests
==========================================================
Verifies:
- Admin login with role='admin'
- Administrative platform-wide metrics
- Customer status toggling (active <-> deactivated)
- Global transactions surveillance
- Offline model metadata and confusion matrix API
- Security audit log inspection
"""

import pytest
import json
from app import create_app, db

@pytest.fixture
def admin_client():
    app = create_app("testing")
    client = app.test_client()
    with app.app_context():
        db.create_all()
    # Login as admin
    login_resp = client.post("/auth/api/login", json={
        "username": "admin",
        "password": "AdminPassword2026!"
    })
    assert login_resp.status_code == 200
    return client

def test_admin_dashboard_api(admin_client):
    """Verify administrator dashboard retrieves platform-wide stats."""
    resp = admin_client.get("/admin/api/dashboard")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["status"] == "success"
    assert "platform_stats" in data
    assert data["platform_stats"]["total_customers"] >= 2
    assert "recent_transactions" in data

def test_admin_customer_management(admin_client):
    """Verify admin can list customers and toggle their account status."""
    # List customers
    list_resp = admin_client.get("/admin/api/customers")
    assert list_resp.status_code == 200
    cust_data = json.loads(list_resp.data)["data"]
    assert cust_data["total"] >= 2
    first_cust = cust_data["customers"][0]
    cust_id = first_cust["id"]

    # Toggle status to deactivated
    toggle_resp = admin_client.patch(f"/admin/api/customers/{cust_id}/status", json={"status": "deactivated"})
    assert toggle_resp.status_code == 200
    assert json.loads(toggle_resp.data)["account_status"] == "deactivated"

    # Re-activate status
    react_resp = admin_client.patch(f"/admin/api/customers/{cust_id}/status", json={"status": "active"})
    assert react_resp.status_code == 200
    assert json.loads(react_resp.data)["account_status"] == "active"

def test_admin_model_info_api(admin_client):
    """Verify MLOps endpoint returns offline benchmark metrics."""
    resp = admin_client.get("/admin/api/model-info")
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert data["best_model"] == "Random Forest"
    assert "champion_metrics" in data
    assert "confusion_matrix" in data["champion_metrics"]

def test_admin_audit_logs_api(admin_client):
    """Verify administrative security audit trail can be queried."""
    resp = admin_client.get("/admin/api/audit-logs")
    assert resp.status_code == 200
    data = json.loads(resp.data)["data"]
    assert "logs" in data

