"""
FraudGuard – Multi-Tenant Customer Data Isolation Verification Tests
====================================================================
CRITICAL VERIFICATION:
Guarantees that customer account data is strictly isolated at the ORM layer.
No customer may ever access, search, filter, or infer another customer's transactions.
"""

import pytest
import json
from app import create_app, db
from database.models import User, Transaction

@pytest.fixture
def app_and_clients():
    app = create_app("testing")
    client_alex = app.test_client()
    client_priya = app.test_client()
    with app.app_context():
        db.create_all()
    return app, client_alex, client_priya

def test_strict_customer_data_isolation(app_and_clients):
    app, client_alex, client_priya = app_and_clients

    # 1. Login as Alex (USD)
    alex_login = client_alex.post("/auth/api/login", json={
        "username": "customer_alex",
        "password": "CustomerPass2026!"
    })
    assert alex_login.status_code == 200

    # 2. Login as Priya (INR)
    priya_login = client_priya.post("/auth/api/login", json={
        "username": "customer_priya",
        "password": "CustomerPass2026!"
    })
    assert priya_login.status_code == 200

    # 3. Submit a unique transaction under Priya's account
    priya_tx_resp = client_priya.post("/customer/api/transactions/predict", json={
        "amount": 750000.0,
        "currency": "INR",
        "type": "TRANSFER",
        "oldbalanceOrg": 750000.0,
        "newbalanceOrig": 0.0,
        "oldbalanceDest": 0.0,
        "newbalanceDest": 0.0,
        "hour_of_day": 2,
        "sender_account": "PRIYA_PRIVATE_SENDER",
        "recipient_account": "PRIYA_PRIVATE_RECIPIENT"
    })
    assert priya_tx_resp.status_code == 201
    priya_tx_data = json.loads(priya_tx_resp.data)["data"]
    priya_tx_id = priya_tx_data["id"]
    priya_uuid = priya_tx_data["trans_uuid"]

    # 4. Alex queries their transaction history
    alex_history_resp = client_alex.get("/customer/api/transactions")
    assert alex_history_resp.status_code == 200
    alex_txns = json.loads(alex_history_resp.data)["transactions"]

    # VERIFY: Priya's transaction must NEVER appear in Alex's list
    alex_uuids = [t["trans_uuid"] for t in alex_txns]
    assert priya_uuid not in alex_uuids, "DATA LEAK: Customer Alex can see Customer Priya's transaction UUID!"

    for t in alex_txns:
        assert t["sender_account"] != "PRIYA_PRIVATE_SENDER", "DATA LEAK: Customer Alex received Priya's private sender account!"
        assert t["recipient_account"] != "PRIYA_PRIVATE_RECIPIENT", "DATA LEAK: Customer Alex received Priya's private recipient account!"

    # 5. Alex attempts to query Priya's transaction detail directly by ID
    alex_direct_access = client_alex.get(f"/customer/api/transactions/{priya_tx_id}")
    assert alex_direct_access.status_code == 404, "SECURITY BREACH: Customer Alex accessed another customer's transaction detail by ID!"

    # 6. Alex attempts to access Administrative endpoints
    alex_admin_access = client_alex.get("/admin/api/dashboard")
    assert alex_admin_access.status_code == 403, "SECURITY BREACH: Customer Alex was not forbidden from accessing admin API!"

    alex_admin_customers = client_alex.get("/admin/api/customers")
    assert alex_admin_customers.status_code == 403, "SECURITY BREACH: Customer Alex was not forbidden from accessing customer directory!"

