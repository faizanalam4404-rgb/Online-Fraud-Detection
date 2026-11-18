"""
FraudGuard – Machine Learning Pipeline & Inference Unit Tests
=============================================================
Verifies:
- Scikit-learn Pipeline loading from model/fraud_model.pkl
- Domain feature engineering (discrepancy math, drain ratio, mule flag)
- High-probability prediction for fraud simulations
- Low-probability prediction for legitimate payments
- Risk tier assignments (LOW, MEDIUM, HIGH, CRITICAL)
- Cybersecurity audit explanation generation
"""

import pytest
from ml.predict import get_model, get_metrics, predict_single, generate_risk_reasons
from ml.preprocessing import build_single_prediction_df

def test_model_pipeline_loaded():
    """Verify Scikit-learn champion model pipeline loads successfully."""
    model = get_model()
    assert model is not None
    assert hasattr(model, "predict")
    assert hasattr(model, "predict_proba")

def test_model_metadata_loaded():
    """Verify offline benchmark metrics are present and genuine."""
    metrics = get_metrics()
    assert metrics is not None
    assert metrics.get("best_model") == "Random Forest"
    assert "champion_metrics" in metrics
    cm = metrics["champion_metrics"]
    assert cm["accuracy"] >= 0.99
    assert cm["precision"] >= 0.90
    assert cm["recall"] >= 0.95
    assert cm["f1_score"] >= 0.95

def test_legitimate_payment_inference():
    """Verify standard everyday purchase is classified as LEGITIMATE with low probability."""
    # Small payment, balanced deduction, existing merchant account
    df, eng = build_single_prediction_df(
        amount_usd=45.0,
        trans_type="PAYMENT",
        old_org=2000.0,
        new_orig=1955.0,
        old_dest=10000.0,
        new_dest=10045.0,
        hour_of_day=14
    )
    is_fraud, prob, label, risk_tier = predict_single(df)
    
    assert is_fraud == 0
    assert label == "LEGITIMATE"
    assert prob < 0.35
    assert risk_tier in ["LOW", "MEDIUM"]

def test_fraudulent_mule_drain_inference():
    """Verify high-value transfer draining total sender funds to zero destination is classified as FRAUDULENT."""
    # Complete drain of 150,000 USD to empty recipient account
    df, eng = build_single_prediction_df(
        amount_usd=150000.0,
        trans_type="TRANSFER",
        old_org=150000.0,
        new_orig=0.0,
        old_dest=0.0,
        new_dest=0.0,
        hour_of_day=3
    )
    is_fraud, prob, label, risk_tier = predict_single(df)
    
    assert is_fraud == 1
    assert label == "FRAUDULENT"
    assert prob >= 0.70
    assert risk_tier in ["HIGH", "CRITICAL"]

def test_cybersecurity_reasons_generation():
    """Verify audit reasons explain fraud heuristic factors accurately."""
    _, eng = build_single_prediction_df(
        amount_usd=50000.0,
        trans_type="TRANSFER",
        old_org=50000.0,
        new_orig=0.0,
        old_dest=0.0,
        new_dest=0.0,
        hour_of_day=3
    )
    reasons = generate_risk_reasons(
        amount_usd=50000.0,
        trans_type="TRANSFER",
        old_org=50000.0,
        new_orig=0.0,
        engineered=eng,
        prob=0.95
    )
    assert len(reasons) > 0
    reasons_text = " ".join(reasons)
    assert "High-risk corridor" in reasons_text or "balance exhaustion" in reasons_text

