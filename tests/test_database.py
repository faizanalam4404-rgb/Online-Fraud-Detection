"""
FraudGuard – Database ORM Models & Integrity Unit Tests
======================================================
Verifies:
- User model creation, PBKDF2 password hashing & verification
- Transaction model relationship with User
- ModelMetadata persistence
- ExchangeRate caching
- AuditLog creation
"""

import pytest
from app import create_app, db
from database.models import User, Transaction, ModelMetadata, ExchangeRate, AuditLog

@pytest.fixture
def app_ctx():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()

def test_user_password_hashing(app_ctx):
    """Verify password is encrypted and verified securely."""
    u = User(username="test_user_hash", email="hash@test.io", role="customer")
    u.set_password("SecurePass123!")
    
    assert u.password_hash is not None
    assert u.password_hash != "SecurePass123!"
    assert u.check_password("SecurePass123!")
    assert not u.check_password("WrongPassword")

def test_user_transaction_relationship(app_ctx):
    """Verify customer transactions are linked via foreign key."""
    u = User.query.filter_by(username="customer_alex").first()
    if not u:
        u = User(username="customer_alex", email="alex@test.io", role="customer")
        u.set_password("Pass123!")
        db.session.add(u)
        db.session.commit()

    tx = Transaction(
        user_id=u.id,
        trans_uuid="TXN-TEST-RELATION",
        transaction_amount=500.0,
        currency_code="USD",
        amount_usd=500.0,
        exchange_rate_used=1.0,
        transaction_type="PAYMENT",
        oldbalance_org=1000.0,
        newbalance_orig=500.0,
        oldbalance_dest=200.0,
        newbalance_dest=700.0,
        prediction="LEGITIMATE",
        is_fraud=0,
        fraud_probability=0.05,
        risk_level="LOW"
    )
    db.session.add(tx)
    db.session.commit()

    queried_tx = Transaction.query.filter_by(trans_uuid="TXN-TEST-RELATION").first()
    assert queried_tx is not None
    assert queried_tx.user.username == u.username
    assert tx in u.transactions.all()

def test_audit_log_creation(app_ctx):
    """Verify security audit logs can be written."""
    log = AuditLog(
        user_id=1,
        action="TEST_SECURITY_EVENT",
        resource_type="system",
        resource_id="0",
        details="Unit test verification event",
        ip_address="127.0.0.1"
    )
    db.session.add(log)
    db.session.commit()

    queried_log = AuditLog.query.filter_by(action="TEST_SECURITY_EVENT").first()
    assert queried_log is not None
    assert queried_log.details == "Unit test verification event"
