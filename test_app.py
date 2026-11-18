"""
FraudGuard Automated Verification & Test Suite
=============================================
Tests all segregated backend routes, ML inference pipeline, database operations,
input validations, and template renderings.
"""

import unittest
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from backend.app import app, db, Transaction, ML_PIPELINE

class FraudGuardTestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        cls.client = app.test_client()
        with app.app_context():
            db.create_all()

    def setUp(self):
        with app.app_context():
            Transaction.query.delete()
            db.session.commit()

    def test_01_health_check(self):
        """Test system health and model loading"""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["model_loaded"])

    def test_02_frontend_serves(self):
        """Test that single frontend index.html serves with 200 OK"""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"FraudGuard", res.data)
        self.assertIn(b"ML Shield Active", res.data)

    def test_03_predict_legitimate_payment(self):
        """Test inference on typical legitimate retail transaction"""
        payload = {
            "type": "PAYMENT",
            "amount": 25.50,
            "oldbalanceOrg": 1200.00,
            "newbalanceOrig": 1174.50,
            "oldbalanceDest": 0.00,
            "newbalanceDest": 0.00,
            "hour_of_day": 14,
            "sender_account": "ACC-TEST-001",
            "recipient_account": "REC-TEST-001"
        }
        res = self.client.post("/api/predict", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["prediction"], "LEGITIMATE")
        self.assertEqual(data["data"]["is_fraud"], 0)
        self.assertLess(data["data"]["fraud_probability"], 0.30)
        self.assertEqual(data["data"]["risk_level"], "LOW")

        with app.app_context():
            self.assertEqual(Transaction.query.count(), 1)
            txn = Transaction.query.first()
            self.assertEqual(txn.prediction, "LEGITIMATE")

    def test_04_predict_fraudulent_takeover(self):
        """Test inference on suspicious account drain transfer"""
        payload = {
            "type": "TRANSFER",
            "amount": 190000.00,
            "oldbalanceOrg": 190000.00,
            "newbalanceOrig": 0.00,
            "oldbalanceDest": 0.00,
            "newbalanceDest": 0.00,
            "hour_of_day": 3,
            "sender_account": "ACC-TEST-VICTIM",
            "recipient_account": "REC-TEST-MULE"
        }
        res = self.client.post("/api/predict", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["data"]["prediction"], "FRAUDULENT")
        self.assertEqual(data["data"]["is_fraud"], 1)
        self.assertGreater(data["data"]["fraud_probability"], 0.70)
        self.assertIn(data["data"]["risk_level"], ["HIGH", "CRITICAL"])
        self.assertTrue(len(data["data"]["risk_reasons"]) > 0)

    def test_05_input_validation(self):
        """Test invalid payloads rejection"""
        res1 = self.client.post("/api/predict", json={
            "type": "PAYMENT", "amount": -50.0, "oldbalanceOrg": 100, "newbalanceOrig": 50,
            "oldbalanceDest": 0, "newbalanceDest": 0
        })
        self.assertEqual(res1.status_code, 422)

        res2 = self.client.post("/api/predict", json={
            "type": "UNSUPPORTED_TYPE", "amount": 100.0, "oldbalanceOrg": 100, "newbalanceOrig": 0,
            "oldbalanceDest": 0, "newbalanceDest": 0
        })
        self.assertEqual(res2.status_code, 422)

    def test_06_seed_samples_and_dashboard(self):
        """Test seed endpoint and verify dashboard stats update"""
        seed_res = self.client.post("/api/seed-samples")
        self.assertEqual(seed_res.status_code, 200)

        dash_res = self.client.get("/api/dashboard")
        self.assertEqual(dash_res.status_code, 200)
        dash_data = dash_res.get_json()
        self.assertGreater(dash_data["stats"]["total_transactions"], 0)
        self.assertGreater(dash_data["stats"]["legitimate_transactions"], 0)
        self.assertGreater(dash_data["stats"]["fraudulent_transactions"], 0)

    def test_07_transaction_search_and_filter(self):
        """Test search, status filter, and sorting"""
        self.client.post("/api/seed-samples")

        res_fraud = self.client.get("/api/transactions?status=fraud")
        data_fraud = res_fraud.get_json()
        self.assertEqual(data_fraud["status"], "success")
        for t in data_fraud["transactions"]:
            self.assertEqual(t["is_fraud"], 1)

        res_sort = self.client.get("/api/transactions?sort=amount_desc")
        data_sort = res_sort.get_json()
        amounts = [t["amount"] for t in data_sort["transactions"]]
        self.assertEqual(amounts, sorted(amounts, reverse=True))

    def test_08_analytics_and_model_info(self):
        """Test analytics and model-info endpoints"""
        self.client.post("/api/seed-samples")

        res_ana = self.client.get("/api/analytics")
        self.assertEqual(res_ana.status_code, 200)
        ana_data = res_ana.get_json()
        self.assertIn("database_metrics", ana_data)
        self.assertIn("offline_evaluation", ana_data)

        res_info = self.client.get("/api/model-info")
        self.assertEqual(res_info.status_code, 200)
        info_data = res_info.get_json()
        self.assertEqual(info_data["data"]["best_model"], "Random Forest")

if __name__ == "__main__":
    unittest.main()
