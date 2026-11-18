"""
FraudGuard Routes Package
"""
from .auth import auth_bp, admin_required
from .customer import customer_bp
from .admin import admin_bp
from .currency import currency_bp
from .api import api_bp

__all__ = ["auth_bp", "customer_bp", "admin_bp", "currency_bp", "api_bp", "admin_required"]

