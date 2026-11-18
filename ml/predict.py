"""
FraudGuard – Model Inference & Prediction Engine
================================================
Loads the serialized Scikit-learn Random Forest champion pipeline
and produces calibrated fraud probabilities, risk level tiers, and explanations.
"""

import os
import json
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "model", "fraud_model.pkl")
METADATA_PATH = os.path.join(BASE_DIR, "model", "model_metadata.json")

_LOADED_MODEL = None
_LOADED_METRICS = None

def get_model():
    """Singleton getter for fitted model pipeline."""
    global _LOADED_MODEL
    if _LOADED_MODEL is None:
        if os.path.exists(MODEL_PATH):
            try:
                _LOADED_MODEL = joblib.load(MODEL_PATH)
            except Exception as e:
                print(f"[!] Warning: Failed loading model pipeline: {e}")
                _LOADED_MODEL = None
    return _LOADED_MODEL

def get_metrics():
    """Singleton getter for offline training metadata."""
    global _LOADED_METRICS
    if _LOADED_METRICS is None:
        if os.path.exists(METADATA_PATH):
            try:
                with open(METADATA_PATH, "r") as f:
                    _LOADED_METRICS = json.load(f)
            except Exception as e:
                print(f"[!] Warning: Failed reading model metadata: {e}")
                _LOADED_METRICS = {}
        else:
            # Check model_metrics.json fallback
            alt_path = os.path.join(BASE_DIR, "model", "model_metrics.json")
            if os.path.exists(alt_path):
                try:
                    with open(alt_path, "r") as f:
                        _LOADED_METRICS = json.load(f)
                except Exception:
                    _LOADED_METRICS = {}
    return _LOADED_METRICS or {}

def predict_single(features_df):
    """
    Runs features DataFrame through fitted Scikit-learn Pipeline.
    Returns: (is_fraud, probability, label, risk_tier)
    """
    model = get_model()
    if model is None:
        raise RuntimeError("Fraud detection model pipeline is not ready or not loaded.")

    raw_pred = model.predict(features_df)[0]
    is_fraud = int(raw_pred)

    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(features_df)[0]
        # Class 1 is Fraud
        fraud_prob = float(probs[1])
    else:
        fraud_prob = 1.0 if is_fraud == 1 else 0.0

    label = "FRAUDULENT" if is_fraud == 1 else "LEGITIMATE"

    # Risk level categorization
    if fraud_prob >= 0.80:
        risk_level = "CRITICAL"
    elif fraud_prob >= 0.50:
        risk_level = "HIGH"
    elif fraud_prob >= 0.20:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    return is_fraud, fraud_prob, label, risk_level

def generate_risk_reasons(amount_usd, trans_type, old_org, new_orig, engineered, prob):
    """Generates transparent cybersecurity audit factors explaining prediction."""
    reasons = []

    if trans_type in ["TRANSFER", "CASH_OUT"]:
        reasons.append(f"High-risk corridor ({trans_type}): 98%+ of online payment fraud exploits transfer or cash-out rails.")

    if engineered.get("drainRatio", 0.0) >= 0.85 and old_org > 0:
        pct_drained = round(min(amount_usd / old_org * 100, 100), 1)
        reasons.append(f"Aggressive balance exhaustion: transaction drains {pct_drained}% of the sender's account.")

    if abs(engineered.get("errorBalanceOrig", 0.0)) > 5.0:
        reasons.append(f"Origin balance discrepancy: calculated outflow mismatch of ${abs(engineered['errorBalanceOrig']):,.2f}.")

    if engineered.get("zeroDestFlag") == 1 and trans_type in ["TRANSFER", "CASH_OUT"]:
        reasons.append("Unverified zero-balance recipient: characteristic of disposable mule accounts with immediate laundering.")

    if engineered.get("hour_of_day") in [0, 1, 2, 3, 4, 5]:
        reasons.append(f"Abnormal temporal pattern: transaction initiated at {engineered['hour_of_day']:02d}:00 off-peak hours.")

    if prob > 0.50 and not reasons:
        reasons.append("Multi-factor statistical anomaly detected across combined banking features.")

    if prob <= 0.15:
        reasons.append("Transaction exhibits standard balance reconciliation continuity and low volatility.")

    return reasons

