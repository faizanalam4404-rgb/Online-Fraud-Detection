"""
FraudGuard – Transaction Query & Reporting Service
==================================================
Enforces strict customer data isolation at the ORM query level.
Provides pagination, multi-criteria filtering, search, CSV export,
and professional PDF audit report generation using ReportLab.
"""

import io
import csv
from datetime import datetime, timezone
from database.models import db, Transaction, User, AuditLog
from services.currency_service import CurrencyService

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class TransactionService:
    @staticmethod
    def get_customer_transactions(
        user_id,
        search=None,
        status="all",
        currency=None,
        txn_type=None,
        sort_by="date_desc",
        page=1,
        per_page=20
    ):
        """
        Retrieves paginated transactions strictly owned by the authenticated customer.
        CUSTOMER DATA ISOLATION GUARANTEE: Filtered explicitly by user_id.
        """
        query = Transaction.query.filter_by(user_id=user_id)

        # Search filter
        if search:
            search_term = f"%{search.strip()}%"
            query = query.filter(
                (Transaction.trans_uuid.ilike(search_term)) |
                (Transaction.transaction_type.ilike(search_term)) |
                (Transaction.currency_code.ilike(search_term)) |
                (Transaction.sender_account.ilike(search_term)) |
                (Transaction.recipient_account.ilike(search_term))
            )

        # Status filter
        if status == "fraud":
            query = query.filter(Transaction.is_fraud == 1)
        elif status == "legitimate":
            query = query.filter(Transaction.is_fraud == 0)

        # Currency filter
        if currency and currency.upper() != "ALL":
            query = query.filter(Transaction.currency_code == currency.upper().strip())

        # Transaction type filter
        if txn_type and txn_type.upper() != "ALL":
            query = query.filter(Transaction.transaction_type == txn_type.upper().strip())

        # Sorting
        if sort_by == "date_asc":
            query = query.order_by(Transaction.created_at.asc(), Transaction.id.asc())
        elif sort_by == "amount_desc":
            query = query.order_by(Transaction.transaction_amount.desc())
        elif sort_by == "amount_asc":
            query = query.order_by(Transaction.transaction_amount.asc())
        else:  # date_desc default
            query = query.order_by(Transaction.created_at.desc(), Transaction.id.desc())

        total = query.count()
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "transactions": [t.to_dict() for t in pagination.items],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev
        }

    @staticmethod
    def get_customer_transaction(user_id, txn_id):
        """
        Returns a single transaction owned by the customer.
        Returns None if record does not exist or belongs to another customer.
        """
        return Transaction.query.filter_by(id=txn_id, user_id=user_id).first()

    @staticmethod
    def delete_customer_transaction(user_id, txn_id):
        """Safely deletes an isolated customer transaction."""
        txn = Transaction.query.filter_by(id=txn_id, user_id=user_id).first()
        if not txn:
            return False, "Transaction not found or unauthorized access."

        db.session.delete(txn)
        db.session.commit()
        return True, f"Transaction {txn.trans_uuid} deleted successfully."

    @staticmethod
    def export_customer_csv(user_id):
        """Generates an in-memory CSV file of customer's isolated transactions."""
        txns = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)

        # CSV Header
        writer.writerow([
            "Transaction ID",
            "Date & Time (UTC)",
            "Channel",
            "Original Amount",
            "Currency",
            "USD Equivalent",
            "Exchange Rate Used",
            "Sender Account",
            "Recipient Account",
            "ML Prediction",
            "Fraud Probability (%)",
            "Risk Level"
        ])

        for t in txns:
            writer.writerow([
                t.trans_uuid,
                t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
                t.transaction_type,
                f"{t.transaction_amount:.2f}",
                t.currency_code,
                f"{t.amount_usd:.2f}",
                f"{t.exchange_rate_used:.4f}",
                t.sender_account or "",
                t.recipient_account or "",
                t.prediction,
                f"{t.fraud_probability * 100:.2f}",
                t.risk_level
            ])

        output.seek(0)
        return output.getvalue().encode("utf-8")

    @staticmethod
    def export_customer_pdf(user_id):
        """
        Generates a professional, branded PDF statement of customer transactions
        using ReportLab.
        """
        user = db.session.get(User, user_id)
        txns = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.created_at.desc()).limit(150).all()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0f172a")
        )
        sub_style = ParagraphStyle(
            "DocSub",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b")
        )
        cell_style = ParagraphStyle(
            "CellText",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#1e293b")
        )

        # Header Info
        elements.append(Paragraph("FraudGuard – Personal Transaction Security Statement", title_style))
        gen_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        elements.append(Paragraph(f"Customer: <b>{user.full_name}</b> ({user.email}) &nbsp;|&nbsp; Generated: {gen_time} &nbsp;|&nbsp; Total Records: {len(txns)}", sub_style))
        elements.append(Spacer(1, 15))

        # Table Data
        table_data = [[
            Paragraph("<b>Reference ID</b>", cell_style),
            Paragraph("<b>Timestamp</b>", cell_style),
            Paragraph("<b>Channel</b>", cell_style),
            Paragraph("<b>Amount</b>", cell_style),
            Paragraph("<b>Currency</b>", cell_style),
            Paragraph("<b>USD Eq.</b>", cell_style),
            Paragraph("<b>Prediction</b>", cell_style),
            Paragraph("<b>Fraud Risk %</b>", cell_style),
            Paragraph("<b>Risk Tier</b>", cell_style)
        ]]

        for t in txns:
            is_fraud = (t.is_fraud == 1)
            pred_color = "#dc2626" if is_fraud else "#16a34a"
            table_data.append([
                Paragraph(t.trans_uuid, cell_style),
                Paragraph(t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "", cell_style),
                Paragraph(t.transaction_type, cell_style),
                Paragraph(CurrencyService.format_amount(t.transaction_amount, t.currency_code), cell_style),
                Paragraph(t.currency_code, cell_style),
                Paragraph(f"${t.amount_usd:,.2f}", cell_style),
                Paragraph(f"<font color='{pred_color}'><b>{t.prediction}</b></font>", cell_style),
                Paragraph(f"{t.fraud_probability*100:.1f}%", cell_style),
                Paragraph(t.risk_level, cell_style)
            ])

        col_widths = [85, 80, 65, 85, 55, 65, 85, 65, 65]
        t_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        t_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        elements.append(t_table)
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    # =========================================================================
    # ADMINISTRATOR TRANSACTION ACCESS
    # =========================================================================
    @staticmethod
    def get_admin_transactions(
        search=None,
        status="all",
        customer_id=None,
        currency=None,
        sort_by="date_desc",
        page=1,
        per_page=25
    ):
        """Platform-wide transaction management for authorized administrators."""
        query = Transaction.query

        if search:
            search_term = f"%{search.strip()}%"
            query = query.filter(
                (Transaction.trans_uuid.ilike(search_term)) |
                (Transaction.transaction_type.ilike(search_term)) |
                (Transaction.currency_code.ilike(search_term)) |
                (Transaction.sender_account.ilike(search_term)) |
                (Transaction.recipient_account.ilike(search_term))
            )

        if status == "fraud":
            query = query.filter(Transaction.is_fraud == 1)
        elif status == "legitimate":
            query = query.filter(Transaction.is_fraud == 0)

        if customer_id:
            query = query.filter(Transaction.user_id == int(customer_id))

        if currency and currency.upper() != "ALL":
            query = query.filter(Transaction.currency_code == currency.upper().strip())

        if sort_by == "date_asc":
            query = query.order_by(Transaction.created_at.asc())
        elif sort_by == "amount_desc":
            query = query.order_by(Transaction.amount_usd.desc())
        elif sort_by == "amount_asc":
            query = query.order_by(Transaction.amount_usd.asc())
        else:
            query = query.order_by(Transaction.created_at.desc())

        total = query.count()
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        return {
            "transactions": [t.to_dict() for t in pagination.items],
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
            "has_prev": pagination.has_prev
        }

    @staticmethod
    def get_admin_transaction_by_id(txn_id):
        """Retrieves individual transaction for admin audit inspection."""
        return db.session.get(Transaction, txn_id)

