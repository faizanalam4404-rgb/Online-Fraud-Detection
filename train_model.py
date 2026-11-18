"""
FraudGuard - Machine Learning Training Pipeline
================================================
Trains and evaluates multiple fraud detection models (Logistic Regression,
Decision Tree, Random Forest) on online payment transaction data.
Handles class imbalance, feature engineering, and saves the best model
along with evaluation metrics and confusion matrix to disk.
"""

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
import joblib

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report
)

# Base directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "model")
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

MODEL_PATH = os.path.join(MODEL_DIR, "fraud_model.pkl")
METRICS_PATH = os.path.join(MODEL_DIR, "model_metrics.json")
SYNTHETIC_DATASET_PATH = os.path.join(DATA_DIR, "transactions_dataset.csv")

def generate_realistic_dataset(n_samples=30000, random_state=42):
    """
    Generates a realistic financial payment dataset modeled on real-world
    distributions (PaySim benchmark specifications).
    Contains authentic fraud patterns:
      - Class imbalance (~2% fraud)
      - High fraud risk concentrated in TRANSFER and CASH_OUT
      - Balance drain anomalies (oldbalanceOrg ~ amount, newbalanceOrig = 0)
      - Zero recipient balance discrepancies (oldbalanceDest = 0, newbalanceDest = 0)
      - Midnight/early-morning anomalous fraud concentrations
    """
    print(f"[*] Generating {n_samples:,} realistic financial transactions...")
    rng = np.random.RandomState(random_state)

    # 1. Transaction Types distribution
    # In online payments: PAYMENT (35%), CASH_OUT (30%), CASH_IN (20%), TRANSFER (12%), DEBIT (3%)
    types = ['PAYMENT', 'CASH_OUT', 'CASH_IN', 'TRANSFER', 'DEBIT']
    type_probs = [0.35, 0.30, 0.20, 0.12, 0.03]
    trans_types = rng.choice(types, size=n_samples, p=type_probs)

    # 2. Time step: 1 to 744 hours (31 days)
    steps = rng.randint(1, 745, size=n_samples)
    hour_of_day = steps % 24

    # 3. Base Amount and Balances
    amounts = np.zeros(n_samples)
    oldbalance_org = np.zeros(n_samples)
    newbalance_orig = np.zeros(n_samples)
    oldbalance_dest = np.zeros(n_samples)
    newbalance_dest = np.zeros(n_samples)
    is_fraud = np.zeros(n_samples, dtype=int)

    for i in range(n_samples):
        t_type = trans_types[i]
        hr = hour_of_day[i]

        # Determine if this sample should be a candidate for fraud
        # Fraud in financial datasets exclusively occurs in TRANSFER and CASH_OUT
        fraud_candidate = (t_type in ['TRANSFER', 'CASH_OUT'])
        # Target ~2% overall fraud rate (out of all records, ~4.5% of TRANSFER/CASH_OUT)
        # Higher fraud probability during off-hours (0-5 AM)
        off_hours_factor = 1.8 if hr in [0, 1, 2, 3, 4, 5] else 1.0
        prob_fraud = 0.045 * off_hours_factor if fraud_candidate else 0.0

        if rng.rand() < prob_fraud:
            # === FRAUDULENT TRANSACTION ===
            is_fraud[i] = 1
            # Fraud transactions typically involve large sums or complete balance drain
            # Account takeover: draining available balance
            old_org = float(rng.exponential(scale=180000) + 5000)
            oldbalance_org[i] = round(old_org, 2)

            # In ~70% of frauds, drain exact whole balance
            if rng.rand() < 0.70:
                amt = old_org
                new_orig = 0.0
            else:
                amt = float(rng.uniform(0.6, 0.99) * old_org)
                new_orig = round(max(0.0, old_org - amt), 2)

            amounts[i] = round(amt, 2)
            newbalance_orig[i] = new_orig

            # Fraud destination accounts are often newly created/mules with 0 balance
            # And after transfer, money is immediately vanished (dest balance remains 0 or doesn't reflect)
            if rng.rand() < 0.65:
                oldbalance_dest[i] = 0.0
                newbalance_dest[i] = 0.0  # Suspicious zero destination trace
            else:
                old_dst = float(rng.exponential(scale=10000))
                oldbalance_dest[i] = round(old_dst, 2)
                newbalance_dest[i] = round(old_dst + amt, 2)

        else:
            # === LEGITIMATE TRANSACTION ===
            is_fraud[i] = 0
            if t_type == 'PAYMENT':
                # Everyday retail, small to moderate purchases
                amt = float(rng.exponential(scale=150) + 5)
                old_org = float(rng.exponential(scale=3500) + amt + 50)
                amounts[i] = round(amt, 2)
                oldbalance_org[i] = round(old_org, 2)
                newbalance_orig[i] = round(max(0.0, old_org - amt), 2)
                # Merchant destinations often don't track recipient personal balance
                oldbalance_dest[i] = 0.0
                newbalance_dest[i] = 0.0

            elif t_type == 'CASH_IN':
                # Deposit cash into own account
                amt = float(rng.exponential(scale=2000) + 50)
                old_org = float(rng.exponential(scale=5000) + 100)
                amounts[i] = round(amt, 2)
                oldbalance_org[i] = round(old_org, 2)
                newbalance_orig[i] = round(old_org + amt, 2)
                oldbalance_dest[i] = round(float(rng.exponential(scale=10000)), 2)
                newbalance_dest[i] = round(max(0.0, oldbalance_dest[i] - amt), 2)

            elif t_type == 'CASH_OUT':
                # Legitimate cash withdrawal / ATM / counter
                amt = float(rng.exponential(scale=1500) + 20)
                old_org = float(rng.exponential(scale=8000) + amt + 200)
                amounts[i] = round(amt, 2)
                oldbalance_org[i] = round(old_org, 2)
                newbalance_orig[i] = round(max(0.0, old_org - amt), 2)
                old_dst = float(rng.exponential(scale=25000) + 100)
                oldbalance_dest[i] = round(old_dst, 2)
                newbalance_dest[i] = round(old_dst + amt, 2)

            elif t_type == 'TRANSFER':
                # Legitimate wire / peer-to-peer transfer
                amt = float(rng.exponential(scale=4000) + 100)
                old_org = float(rng.exponential(scale=20000) + amt + 500)
                amounts[i] = round(amt, 2)
                oldbalance_org[i] = round(old_org, 2)
                newbalance_orig[i] = round(max(0.0, old_org - amt), 2)
                old_dst = float(rng.exponential(scale=15000) + 50)
                oldbalance_dest[i] = round(old_dst, 2)
                newbalance_dest[i] = round(old_dst + amt, 2)

            else:  # DEBIT
                amt = float(rng.exponential(scale=80) + 2)
                old_org = float(rng.exponential(scale=1200) + amt + 20)
                amounts[i] = round(amt, 2)
                oldbalance_org[i] = round(old_org, 2)
                newbalance_orig[i] = round(max(0.0, old_org - amt), 2)
                oldbalance_dest[i] = 0.0
                newbalance_dest[i] = 0.0

    df = pd.DataFrame({
        'step': steps,
        'type': trans_types,
        'amount': amounts,
        'oldbalanceOrg': oldbalance_org,
        'newbalanceOrig': newbalance_orig,
        'oldbalanceDest': oldbalance_dest,
        'newbalanceDest': newbalance_dest,
        'isFraud': is_fraud
    })

    df.to_csv(SYNTHETIC_DATASET_PATH, index=False)
    print(f"[✓] Saved realistic dataset to {SYNTHETIC_DATASET_PATH}")
    return df

def feature_engineering(df):
    """
    Applies domain-specific financial fraud feature engineering.
    These features capture balance discrepancies, balance drain ratios,
    and high-risk transfer indicators.
    """
    df = df.copy()

    # 1. Hour of day extracted from step
    if 'hour_of_day' not in df.columns:
        if 'step' in df.columns:
            df['hour_of_day'] = df['step'] % 24
        else:
            df['hour_of_day'] = 12

    # 2. Balance Discrepancy Error Features
    # In math: oldbalanceOrg - amount should equal newbalanceOrig
    # Large deviation is a primary indicator of anomalous/fraudulent transaction logging
    df['errorBalanceOrig'] = (df['newbalanceOrig'] + df['amount']) - df['oldbalanceOrg']
    df['errorBalanceDest'] = (df['oldbalanceDest'] + df['amount']) - df['newbalanceDest']

    # 3. Balance Drain Ratio (amount / (oldbalanceOrg + 1))
    df['drainRatio'] = df['amount'] / (df['oldbalanceOrg'] + 1.0)
    df['drainRatio'] = df['drainRatio'].clip(0, 10.0)

    # 4. Zero Destination Flag
    df['zeroDestFlag'] = ((df['oldbalanceDest'] == 0) & (df['newbalanceDest'] == 0)).astype(int)

    # 5. High-Risk Type Flag (TRANSFER or CASH_OUT)
    df['isHighRiskType'] = df['type'].isin(['TRANSFER', 'CASH_OUT']).astype(int)

    return df

def train_and_evaluate(dataset_path=None):
    """
    Main training workflow:
    1. Loads or generates dataset
    2. Performs feature engineering
    3. Splits data into train and test sets
    4. Trains Logistic Regression, Decision Tree, and Random Forest
    5. Evaluates metrics (Accuracy, Precision, Recall, F1, Confusion Matrix)
    6. Selects and serializes the best model with Joblib
    7. Outputs comprehensive metrics to JSON
    """
    print("\n" + "="*60)
    print("      FraudGuard Machine Learning Training System")
    print("="*60)

    # Load dataset
    if dataset_path and os.path.exists(dataset_path):
        print(f"[*] Loading dataset from: {dataset_path}")
        df = pd.read_csv(dataset_path)
    elif os.path.exists(SYNTHETIC_DATASET_PATH):
        print(f"[*] Loading existing dataset from: {SYNTHETIC_DATASET_PATH}")
        df = pd.read_csv(SYNTHETIC_DATASET_PATH)
    else:
        df = generate_realistic_dataset(n_samples=30000)

    # Clean & inspect
    print(f"[*] Total dataset size: {len(df):,} records, {len(df.columns)} columns")
    df = df.dropna()

    # Identify target column
    target_col = None
    for cand in ['isFraud', 'isfraud', 'fraud', 'Class', 'class', 'target']:
        if cand in df.columns:
            target_col = cand
            break

    if not target_col:
        raise ValueError("Could not find fraud target column in dataset! Expected 'isFraud' or similar.")

    fraud_count = int(df[target_col].sum())
    legit_count = int(len(df) - fraud_count)
    fraud_rate = (fraud_count / len(df)) * 100
    print(f"[*] Class Distribution: Legitimate = {legit_count:,} ({100-fraud_rate:.2f}%), Fraud = {fraud_count:,} ({fraud_rate:.2f}%)")

    # Feature Engineering
    df_engineered = feature_engineering(df)

    # Define Feature Sets
    categorical_features = ['type']
    numerical_features = [
        'amount',
        'oldbalanceOrg',
        'newbalanceOrig',
        'oldbalanceDest',
        'newbalanceDest',
        'hour_of_day',
        'errorBalanceOrig',
        'errorBalanceDest',
        'drainRatio',
        'zeroDestFlag',
        'isHighRiskType'
    ]

    feature_cols = categorical_features + numerical_features
    X = df_engineered[feature_cols]
    y = df_engineered[target_col].astype(int)

    # Train / Test Split (Stratified 80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print(f"[*] Train set: {len(X_train):,} samples | Test set: {len(X_test):,} samples")

    # Preprocessor definition
    preprocessor = ColumnTransformer(
        transformers=[
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_features),
            ('num', StandardScaler(), numerical_features)
        ]
    )

    # Models to evaluate
    models = {
        "Logistic Regression": LogisticRegression(
            class_weight='balanced',
            max_iter=1000,
            random_state=42
        ),
        "Decision Tree": DecisionTreeClassifier(
            class_weight='balanced',
            max_depth=7,
            min_samples_split=20,
            random_state=42
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=100,
            max_depth=12,
            min_samples_leaf=3,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
    }

    comparison_results = {}
    fitted_pipelines = {}
    best_f1 = -1.0
    best_model_name = None

    print("\n" + "-"*60)
    print("              MODEL COMPARISON & BENCHMARKING")
    print("-" * 60)

    for name, clf in models.items():
        print(f"\n[*] Training {name}...")
        pipeline = Pipeline(steps=[
            ('preprocessor', preprocessor),
            ('classifier', clf)
        ])

        pipeline.fit(X_train, y_train)
        fitted_pipelines[name] = pipeline

        # Predictions
        y_pred = pipeline.predict(X_test)
        if hasattr(pipeline, "predict_proba"):
            y_proba = pipeline.predict_proba(X_test)[:, 1]
            auc_val = float(roc_auc_score(y_test, y_proba))
        else:
            y_proba = None
            auc_val = 0.0

        acc = float(accuracy_score(y_test, y_pred))
        prec = float(precision_score(y_test, y_pred, zero_division=0))
        rec = float(recall_score(y_test, y_pred, zero_division=0))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        cm = confusion_matrix(y_test, y_pred)
        tn, fp, fn, tp = [int(v) for v in cm.ravel()]

        comparison_results[name] = {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "roc_auc": round(auc_val, 4),
            "confusion_matrix": {
                "tn": tn,
                "fp": fp,
                "fn": fn,
                "tp": tp
            }
        }

        print(f"    -> Accuracy : {acc*100:.2f}%")
        print(f"    -> Precision: {prec*100:.2f}%")
        print(f"    -> Recall   : {rec*100:.2f}%")
        print(f"    -> F1-Score : {f1*100:.2f}%")
        print(f"    -> ROC-AUC  : {auc_val:.4f}")
        print(f"    -> Conf Mat : TN={tn}, FP={fp}, FN={fn}, TP={tp}")

        # In fraud detection, high F1 (balancing Precision and Recall) decides champion
        if f1 > best_f1:
            best_f1 = f1
            best_model_name = name

    print("\n" + "="*60)
    print(f"[🏆] Best Performing Model: {best_model_name} (F1 Score: {best_f1*100:.2f}%)")
    print("="*60)

    best_pipeline = fitted_pipelines[best_model_name]

    # Save Best Model Pipeline with Joblib
    joblib.dump(best_pipeline, MODEL_PATH)
    print(f"[✓] Saved champion model pipeline to {MODEL_PATH}")

    # Extract Feature Importances if Random Forest or Decision Tree
    feature_names = []
    # Extract names from OneHotEncoder
    ohe = best_pipeline.named_steps['preprocessor'].named_transformers_['cat']
    cat_feature_names = list(ohe.get_feature_names_out(categorical_features))
    feature_names = cat_feature_names + numerical_features

    feature_importances = []
    clf_step = best_pipeline.named_steps['classifier']
    if hasattr(clf_step, 'feature_importances_'):
        importances = clf_step.feature_importances_
        sorted_indices = np.argsort(importances)[::-1]
        for idx in sorted_indices[:10]:
            feature_importances.append({
                "feature": feature_names[idx],
                "importance": round(float(importances[idx]), 4)
            })

    # Save comprehensive metadata
    metadata = {
        "best_model": best_model_name,
        "algorithm": str(clf_step.__class__.__name__),
        "total_dataset_samples": len(df),
        "training_samples": len(X_train),
        "testing_samples": len(X_test),
        "legitimate_samples_dataset": legit_count,
        "fraudulent_samples_dataset": fraud_count,
        "fraud_rate_pct": round(fraud_rate, 2),
        "categorical_features": categorical_features,
        "numerical_features": numerical_features,
        "all_input_features": feature_cols,
        "champion_metrics": comparison_results[best_model_name],
        "models_comparison": comparison_results,
        "feature_importances": feature_importances,
        "pipeline_description": (
            "OneHotEncoder(type) + StandardScaler(amount, balances, errors) "
            f"+ {best_model_name}(class_weight='balanced')"
        )
    }

    with open(METRICS_PATH, "w") as f:
        json.dump(metadata, f, indent=4)

    print(f"[✓] Saved model evaluation metrics to {METRICS_PATH}")
    print("[✓] Model Training & Export completed successfully!\n")
    return metadata

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train FraudGuard Machine Learning Model")
    parser.add_argument("--dataset", type=str, default=None, help="Path to custom CSV dataset")
    args = parser.parse_args()

    train_and_evaluate(dataset_path=args.dataset)

