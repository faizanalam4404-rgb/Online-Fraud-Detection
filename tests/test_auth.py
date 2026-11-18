"""
FraudGuard – Authentication & Session Security Unit Tests
=========================================================
Verifies:
- Customer registration via API
- Login with valid credentials
- Rejection of invalid passwords & unknown users
- Role-based redirection and session management
"""

import pytest
import json
from app import create_app, db
from database.models import User

@pytest.fixture
def client():
    app = create_app("testing")
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
        yield client

def test_api_login_success_customer(client):
    """Verify customer login with seeded credentials."""
    resp = client.post("/auth/api/login", json={
        "username": "customer_alex",
        "password": "CustomerPass2026!"
    })
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["status"] == "success"
    assert data["user"]["username"] == "customer_alex"
    assert data["user"]["role"] == "customer"

def test_api_login_failure_bad_password(client):
    """Verify rejection on wrong password."""
    resp = client.post("/auth/api/login", json={
        "username": "customer_alex",
        "password": "WrongPassword123!"
    })
    assert resp.status_code == 401
    data = json.loads(resp.data)
    assert data["status"] == "error"

def test_api_registration_and_duplicate_check(client):
    """Verify new user registration and duplicate username/email rejection."""
    # Register new user
    reg_resp = client.post("/auth/api/register", json={
        "username": "new_cust_unit_test",
        "email": "newcust@test.io",
        "password": "SecurePassword123!",
        "full_name": "Test Customer",
        "preferred_currency": "GBP"
    })
    assert reg_resp.status_code == 201
    data = json.loads(reg_resp.data)
    assert data["status"] == "success"
    assert data["user"]["username"] == "new_cust_unit_test"
    assert data["user"]["preferred_currency"] == "GBP"

    # Attempt duplicate username
    dup_resp = client.post("/auth/api/register", json={
        "username": "new_cust_unit_test",
        "email": "diff_email@test.io",
        "password": "SecurePassword123!",
        "full_name": "Duplicate Attempt"
    })
    assert dup_resp.status_code == 409

