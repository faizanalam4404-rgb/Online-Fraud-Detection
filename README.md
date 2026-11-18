# 🛡️ FraudGuard – Global Online Payment Fraud Detection & Customer Management System

**FraudGuard** is an enterprise-grade cybersecurity web application that detects fraudulent online payment transactions in real time using a trained Machine Learning pipeline (**Scikit-learn Random Forest Classifier**).

The platform is designed with a **multi-tenant architecture** featuring two distinct portals:
1. **Personal Customer Portal:** Provides customer self-registration, session security, live transaction fraud analysis, personal isolated transaction history, search/filter/sort, CSV and ReportLab PDF statement exports, personal telemetry, and profile/currency preference management.
2. **Administrative Security Portal (SOC):** Allows authorized security administrators to monitor platform-wide telemetry, inspect global transactions, activate/deactivate customer accounts (passwords never exposed), view model benchmark MLOps metadata (confusion matrix & feature importances), and examine the immutable security audit trail.

---

## 🏗️ Architecture & Tech Stack

```text
FraudGuard/
│
├── app.py                      # Application factory, CSRF protection, auto-database seeding
├── config.py                   # Configuration classes (Development, Testing, Production)
├── requirements.txt            # Production dependencies
├── run.bat                     # Windows 1-click startup launcher
├── run.ps1                     # PowerShell startup launcher
│
├── database/
│   ├── models.py               # SQLAlchemy ORM Models (User, Transaction, ModelMetadata, ExchangeRate, AuditLog)
│   └── database.db             # SQLite relational database
│
├── services/
│   ├── currency_service.py     # 60+ ISO 4217 currencies, live exchange rate fetching & cache
│   ├── fraud_service.py        # Currency normalization, feature engineering, scoring & persistence
│   ├── transaction_service.py  # Customer-isolated querying, pagination, CSV & ReportLab PDF exporter
│   └── analytics_service.py    # Isolated personal customer metrics & platform-wide SOC analytics
│
├── ml/
│   ├── preprocessing.py        # Domain discrepancy math, drain ratio, mule flag (Polars/Pandas compatible)
│   └── predict.py              # Model inference singleton, probability gauge, audit reason generator
│
├── model/
│   ├── fraud_model.pkl         # Fitted Scikit-learn Pipeline (ColumnTransformer + Random Forest)
│   └── model_metadata.json     # Genuine offline holdout test evaluation benchmarks
│
├── routes/
│   ├── auth.py                 # Login, register, logout, session management & RBAC decorators
│   ├── customer.py             # Customer portal views & isolated REST APIs (/customer/*)
│   ├── admin.py                # Admin portal views & SOC APIs (/admin/*)
│   ├── currency.py             # ISO 4217 registry & live rate synchronization APIs
│   └── api.py                  # Public marketing pages & health status endpoints
│
├── templates/
│   ├── base.html               # Master layout (sidebar, topbar, theme switcher, currency pill)
│   ├── index.html              # Modern cybersecurity landing page
│   ├── about.html              # Architecture & compliance overview
│   ├── features.html           # Platform capabilities breakdown
│   ├── how_it_works.html       # Mathematical explainability & pipeline stages
│   ├── login.html              # Sign in with 1-click demo presets
│   ├── register.html           # Customer self-registration form
│   ├── error.html              # 403, 404, 500 error display
│   ├── customer/               # Customer portal templates (Dashboard, Detection, History, Analytics, etc.)
│   └── admin/                  # Admin portal templates (Dashboard, Customers, Transactions, Model Info, etc.)
│
├── static/
│   └── css/style.css           # Cybersecurity Navy theme + Light theme variables & components
│
└── tests/                      # Automated Pytest Suite (23/23 tests passing)
    ├── test_currency.py        # ISO 4217 registry, precision & conversion math
    ├── test_ml.py              # Model loading, predictions, risk tiering & explanations
    ├── test_database.py        # ORM models, PBKDF2 password hashing & relationships
    ├── test_auth.py            # Authentication, registration & duplicate prevention
    ├── test_isolation.py       # CRITICAL: Multi-tenant customer data isolation verification
    ├── test_admin.py           # Admin SOC KPIs, customer management & audit trails
    └── test_exports.py         # CSV & ReportLab PDF statement generation
```

---

## 🔒 Strict Customer Data Isolation Guarantees

In FraudGuard, customer data isolation is enforced at the database ORM query level:
- **Tenant Isolation:** Every customer query strictly filters by `user_id == current_user.id`.
- **Zero Cross-Tenant Leakage:** A customer can never view, search, filter, or infer another customer's transactions or account statistics.
- **Direct Access Defense:** Attempting to query another customer's transaction ID (e.g. `/customer/api/transactions/<foreign_id>`) returns `404 Not Found`.
- **Export Confinement:** CSV and PDF exports exclusively contain records belonging to the authenticated customer.
- **RBAC Protection:** Customer accounts attempting to call administrative endpoints are immediately blocked with `403 Forbidden`.

Verified by automated test: [`tests/test_isolation.py`](file:///c:/Users/User/OneDrive/Desktop/OPF/tests/test_isolation.py).

---

## 💱 Global Multi-Currency Support (ISO 4217)

- **Comprehensive Registry:** Supports 60+ world currencies including `USD`, `INR`, `EUR`, `GBP`, `JPY`, `CNY`, `AED`, `SAR`, `CAD`, `AUD`, `CHF`, `SGD`, `BRL`, `ZAR`, etc.
- **Accurate Decimal Precision:**
  - Standard 2-decimal currencies (USD, EUR, INR, GBP).
  - Zero-decimal currencies (JPY, KRW, VND) correctly rendered without floating-point fractions.
  - Three-decimal currencies (KWD, BHD, OMR) correctly formatted to 3 decimal places.
- **Live Exchange Rate Engine:** Connects to live external exchange rate providers, caching rates in SQLite with automatic fallback to persistent offline baselines during network downtime.
- **Non-Destructive Conversion:** The original transaction amount and currency code are strictly preserved in the database. When evaluating risk, the system calculates an equivalent USD value solely for pipeline scoring and persists the exact exchange rate used.

---

## 🧠 Machine Learning Model & Pipeline

### Champion Model: Random Forest Classifier
- **Pipeline Architecture:**
  - `ColumnTransformer`: One-Hot Encoding for categorical payment rail (`type`), `StandardScaler` for continuous numerical features.
  - `RandomForestClassifier`: Ensemble of balanced decision trees with depth limiting to prevent overfitting.
- **Engineered Banking Heuristics:**
  - `errorBalanceOrig`: Calculated sender balance mismatch `(newbalanceOrig + amount) - oldbalanceOrg`.
  - `errorBalanceDest`: Calculated recipient balance mismatch `(oldbalanceDest + amount) - newbalanceDest`.
  - `drainRatio`: Ratio of transfer amount to sender available balance `amount / (oldbalanceOrg + 1.0)`.
  - `zeroDestFlag`: Identifies mule accounts starting and ending at $0 balance.
  - `isHighRiskType`: Flags high-risk corridors (`TRANSFER`, `CASH_OUT`).
- **Verified Offline Test Benchmarks (Holdout N = 6,000):**
  - **Accuracy:** 99.82%
  - **Precision:** 93.66%
  - **Recall:** 98.52%
  - **F1-Score:** 96.03%
  - **ROC-AUC:** 0.9999
  - **Confusion Matrix:** 5,856 True Negatives, 9 False Positives, 2 False Negatives, 133 True Positives.

---

## 🚀 Step-by-Step Running Guide

### 1. Requirements
- Python 3.10+ (Tested and verified on Python 3.14).
- Modern web browser (Chrome, Edge, Firefox, Safari).

### 2. Quick Launch (Recommended)
Double-click `run.bat` or run in PowerShell:
```powershell
.\run.ps1
```
The application will boot the Flask backend and open `http://127.0.0.1:5000` directly in your browser.

### 3. Manual Command Line Launch
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the web application
python app.py
```
Visit `http://127.0.0.1:5000` in your browser.

---

## 🔑 Pre-Seeded Demo Credentials

FraudGuard automatically seeds the database with three pre-configured accounts:

| Role | Username | Password | Default Currency | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Customer 1** | `customer_alex` | `CustomerPass2026!` | USD ($) | Isolated US Customer Workspace |
| **Customer 2** | `customer_priya` | `CustomerPass2026!` | INR (₹) | Isolated Indian Customer Workspace |
| **Administrator** | `admin` | `AdminPassword2026!` | USD ($) | Security Operations Center (SOC) Console |

*Note: On the login page, you can click the **1-Click Demo Credentials** buttons to instantly autofill these credentials.*

---

## 🧪 Running Automated Test Suite

FraudGuard comes with 23 comprehensive unit and integration tests:

```powershell
python -m pytest tests/ -v
```

### Verified Test Results:
```text
tests/test_admin.py::test_admin_dashboard_api PASSED
tests/test_admin.py::test_admin_customer_management PASSED
tests/test_admin.py::test_admin_model_info_api PASSED
tests/test_admin.py::test_admin_audit_logs_api PASSED
tests/test_auth.py::test_api_login_success_customer PASSED
tests/test_auth.py::test_api_login_failure_bad_password PASSED
tests/test_auth.py::test_api_registration_and_duplicate_check PASSED
tests/test_currency.py::test_currency_registry_breadth PASSED
tests/test_currency.py::test_currency_decimal_precision PASSED
tests/test_currency.py::test_amount_formatting PASSED
tests/test_currency.py::test_currency_conversion_math PASSED
tests/test_currency.py::test_invalid_currency_rejection PASSED
tests/test_database.py::test_user_password_hashing PASSED
tests/test_database.py::test_user_transaction_relationship PASSED
tests/test_database.py::test_audit_log_creation PASSED
tests/test_exports.py::test_export_csv_statement PASSED
tests/test_exports.py::test_export_pdf_statement PASSED
tests/test_isolation.py::test_strict_customer_data_isolation PASSED
tests/test_ml.py::test_model_pipeline_loaded PASSED
tests/test_ml.py::test_model_metadata_loaded PASSED
tests/test_ml.py::test_legitimate_payment_inference PASSED
tests/test_ml.py::test_fraudulent_mule_drain_inference PASSED
tests/test_ml.py::test_cybersecurity_reasons_generation PASSED

============================= 23 passed in 11.23s =============================
```
