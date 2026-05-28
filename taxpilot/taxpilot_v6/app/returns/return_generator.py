"""
return_generator.py
-------------------
Module 6 — Draft Return Preparation

Three outputs:
  1. GSTR-3B prefill JSON  (GSTN portal format)
  2. 26Q XML               (wired to existing form_26q_generator.py)
  3. P&L summary PDF       (reportlab)
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.models import Transaction, Client
from app.gst.models.gst_models import ReconciliationRun, GSTInvoice
from app.tds.models.tds_models import TDSEntry
from app.tds.form_26q_generator import Form26QGenerator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GSTR-3B Prefill
# ---------------------------------------------------------------------------

def generate_gstr3b(
    client_id: int,
    month: int,
    year: int,
    db: Session,
) -> Dict[str, Any]:
    """
    Build a GSTR-3B prefill JSON in GSTN portal format.
    Pulls from latest completed reconciliation_run for the period.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise ValueError(f"Client {client_id} not found")

    # Latest completed reconciliation run for the period
    run = (
        db.query(ReconciliationRun)
        .filter(
            ReconciliationRun.client_id    == client_id,
            ReconciliationRun.period_month == month,
            ReconciliationRun.period_year  == year,
            ReconciliationRun.status       == "completed",
        )
        .order_by(ReconciliationRun.completed_at.desc())
        .first()
    )

    # Outward supplies — uploaded invoices from books
    invoices_books = (
        db.query(GSTInvoice)
        .filter(
            GSTInvoice.client_id    == client_id,
            GSTInvoice.period_month == month,
            GSTInvoice.period_year  == year,
            GSTInvoice.source       == "uploaded",
        )
        .all()
    )

    total_taxable = round(sum(i.taxable_amount for i in invoices_books), 2)
    total_cgst    = round(sum(i.cgst  for i in invoices_books), 2)
    total_sgst    = round(sum(i.sgst  for i in invoices_books), 2)
    total_igst    = round(sum(i.igst  for i in invoices_books), 2)

    # ITC — matched GSTR-2A invoices only (safe ITC)
    matched_invoices = []
    if run:
        matched_invoices = (
            db.query(GSTInvoice)
            .filter(
                GSTInvoice.client_id             == client_id,
                GSTInvoice.period_month          == month,
                GSTInvoice.period_year           == year,
                GSTInvoice.source                == "gstr2a",
                GSTInvoice.reconciliation_status == "matched",
            )
            .all()
        )

    itc_igst = round(sum(i.igst for i in matched_invoices), 2)
    itc_cgst = round(sum(i.cgst for i in matched_invoices), 2)
    itc_sgst = round(sum(i.sgst for i in matched_invoices), 2)

    net_igst = round(max(total_igst - itc_igst, 0), 2)
    net_cgst = round(max(total_cgst - itc_cgst, 0), 2)
    net_sgst = round(max(total_sgst - itc_sgst, 0), 2)

    # GSTN ret_period format: MMYYYY  e.g. "042025"
    period_str = f"{month:02d}{year}"

    return {
        "gstin":      getattr(client, "gstin", "") or "",
        "ret_period": period_str,
        "status":     "P",   # P = draft/prepared
        "sup_details": {
            "osup_det": {                      # 3.1(a) taxable outward
                "txval": total_taxable,
                "iamt":  total_igst,
                "camt":  total_cgst,
                "samt":  total_sgst,
                "csamt": 0.0,
            },
            "osup_zero":    {"txval": 0.0, "iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0},
            "osup_nil_exmp":{"txval": 0.0},
            "isup_rev":     {"txval": 0.0, "iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0},
            "osup_nonzero": {"txval": 0.0},
        },
        "itc_elg": {
            "itc_avl": [
                {"ty": "IMPG", "iamt": 0.0,      "camt": 0.0,      "samt": 0.0,      "csamt": 0.0},
                {"ty": "IMPS", "iamt": 0.0,      "camt": 0.0,      "samt": 0.0,      "csamt": 0.0},
                {"ty": "ISRC", "iamt": itc_igst,  "camt": itc_cgst, "samt": itc_sgst, "csamt": 0.0},
                {"ty": "ISD",  "iamt": 0.0,      "camt": 0.0,      "samt": 0.0,      "csamt": 0.0},
                {"ty": "OTH",  "iamt": 0.0,      "camt": 0.0,      "samt": 0.0,      "csamt": 0.0},
            ],
            "itc_rev": [
                {"ty": "RUL",  "iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0},
                {"ty": "OTH",  "iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0},
            ],
            "itc_net":   {"iamt": itc_igst, "camt": itc_cgst, "samt": itc_sgst, "csamt": 0.0},
            "itc_inelg": [
                {"ty": "RUL",  "iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0},
                {"ty": "OTH",  "iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0},
            ],
        },
        "intr_ltfee": {
            "intr_details": {"iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0},
            "ltfee_details":{"iamt": 0.0, "camt": 0.0, "samt": 0.0, "csamt": 0.0},
        },
        "tax_pay": {
            "iamt":  net_igst,
            "camt":  net_cgst,
            "samt":  net_sgst,
            "csamt": 0.0,
        },
        "_taxpilot_meta": {
            "generated_at":          datetime.utcnow().isoformat(),
            "period":                f"{month:02d}/{year}",
            "source_invoice_count":  len(invoices_books),
            "matched_invoice_count": len(matched_invoices),
            "reconciliation_run_id": run.id if run else None,
            "itc_at_risk":           run.itc_at_risk_amount if run else 0.0,
            "warning": (
                None if run else
                "No completed reconciliation run found for this period. "
                "ITC figures may be incomplete — run GST reconciliation first."
            ),
        },
    }


# ---------------------------------------------------------------------------
# 26Q XML wire-up
# ---------------------------------------------------------------------------

def generate_26q(
    client_id: int,
    quarter: str,
    financial_year: str,
    tan: str,
    pan: str,
    deductor_name: str,
    db: Session,
) -> bytes:
    """Pull TDS entries from DB and return 26Q XML as UTF-8 bytes."""
    entries = (
        db.query(TDSEntry)
        .filter(
            TDSEntry.client_id      == client_id,
            TDSEntry.financial_year == financial_year,
            TDSEntry.quarter        == quarter,
        )
        .all()
    )

    if not entries:
        raise ValueError(
            f"No TDS entries for client={client_id} FY={financial_year} {quarter}"
        )

    entry_dicts = [_tds_entry_to_dict(e) for e in entries]
    generator   = Form26QGenerator(tan, pan, deductor_name)
    xml_str     = generator.generate_26q(entry_dicts, financial_year, quarter)
    return xml_str.encode("utf-8")


def _tds_entry_to_dict(e: TDSEntry) -> Dict[str, Any]:
    return {
        "vendor_pan":       e.vendor_pan,
        "vendor_name":      e.vendor_name,
        "tds_section":      e.tds_section,
        "payment_date":     e.payment_date,
        "payment_amount":   e.payment_amount,
        "tds_rate":         e.tds_rate,
        "tds_amount":       e.tds_amount,
        "tds_deducted":     e.tds_deducted,
        "missed_deduction": e.missed_deduction,
        "quarter":          e.quarter,
    }


# ---------------------------------------------------------------------------
# P&L Summary PDF
# ---------------------------------------------------------------------------

# Which categories are income vs expense
_INCOME_CATS = {"interest_income", "upi_transfer", "neft_rtgs"}

_EXPENSE_CATS = {
    "salary", "vendor_payment", "tds_payment", "gst_payment",
    "professional_fees", "utility", "travel", "office_expense",
    "bank_charges", "loan_repayment", "insurance", "investment",
}


def generate_pl_pdf(
    client_id: int,
    from_date: date,
    to_date: date,
    db: Session,
) -> bytes:
    """
    Aggregate categorised transactions and render a P&L PDF.
    Returns raw PDF bytes.  Raises ImportError if reportlab is missing.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer,
            Table, TableStyle, HRFlowable,
        )
    except ImportError:
        raise ImportError(
            "reportlab is not installed. "
            "Add 'reportlab>=4.0' to requirements.txt and rebuild."
        )

    client       = db.query(Client).filter(Client.id == client_id).first()
    company_name = getattr(client, "company_name", None) or f"Client #{client_id}"

    from_dt = datetime.combine(from_date, datetime.min.time())
    to_dt   = datetime.combine(to_date,   datetime.max.time())

    txns = (
        db.query(Transaction)
        .filter(
            Transaction.client_id >= client_id,
            Transaction.client_id <= client_id,   # explicit equality via range avoids ORM quirk
            Transaction.date      >= from_dt,
            Transaction.date      <= to_dt,
        )
        .filter(Transaction.client_id == client_id)
        .all()
    )

    income_totals:  Dict[str, float] = {}
    expense_totals: Dict[str, float] = {}

    for txn in txns:
        cat = txn.category or "uncategorized"
        amt = abs(float(txn.amount))
        if txn.type == "credit" or cat in _INCOME_CATS:
            income_totals[cat]  = income_totals.get(cat, 0.0)  + amt
        else:
            expense_totals[cat] = expense_totals.get(cat, 0.0) + amt

    total_income  = sum(income_totals.values())
    total_expense = sum(expense_totals.values())
    net_profit    = total_income - total_expense

    # ---- Build PDF -------------------------------------------------------
    buf  = io.BytesIO()
    doc  = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm,   bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()

    H1 = ParagraphStyle("tp_h1", parent=styles["Heading1"],
                        fontSize=16, spaceAfter=4,
                        textColor=colors.HexColor("#1a1a2e"))
    SUB = ParagraphStyle("tp_sub", parent=styles["Normal"],
                         fontSize=10, spaceAfter=2,
                         textColor=colors.HexColor("#555555"))
    FOOT = ParagraphStyle("tp_foot", parent=styles["Normal"],
                          fontSize=8, spaceBefore=4,
                          textColor=colors.grey)

    COL_W = [10*cm, 5*cm]
    DARK  = colors.HexColor("#1a1a2e")
    LIGHT = colors.HexColor("#f5f7fa")
    MID   = colors.HexColor("#e8ecf0")
    GRID  = colors.HexColor("#cccccc")

    def _table(rows_data: list) -> Table:
        t = Table(rows_data, colWidths=COL_W)
        n = len(rows_data)
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1,  0),  DARK),
            ("TEXTCOLOR",     (0, 0), (-1,  0),  colors.white),
            ("FONTNAME",      (0, 0), (-1,  0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1,  0),  10),
            ("BOTTOMPADDING", (0, 0), (-1,  0),  8),
            ("FONTNAME",      (0, 1), (-1, -2),  "Helvetica"),
            ("FONTSIZE",      (0, 1), (-1, -2),  9),
            ("ROWBACKGROUNDS",(0, 1), (-1, -2),  [colors.white, LIGHT]),
            ("BACKGROUND",    (0,-1), (-1, -1),  MID),
            ("FONTNAME",      (0,-1), (-1, -1),  "Helvetica-Bold"),
            ("FONTSIZE",      (0,-1), (-1, -1),  10),
            ("ALIGN",         (1, 0), ( 1, -1),  "RIGHT"),
            ("GRID",          (0, 0), (-1, -1),  0.5, GRID),
            ("TOPPADDING",    (0, 1), (-1, -1),  5),
            ("BOTTOMPADDING", (0, 1), (-1, -1),  5),
        ]))
        return t

    story: list = []

    # Title block
    story.append(Paragraph("Profit & Loss Summary", H1))
    story.append(Paragraph(company_name, SUB))
    story.append(Paragraph(
        f"Period: {from_date.strftime('%d %b %Y')} – {to_date.strftime('%d %b %Y')}", SUB))
    story.append(Paragraph(
        f"Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC  |  TaxPilot", SUB))
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=DARK))
    story.append(Spacer(1, 0.4*cm))

    # Income table
    story.append(Paragraph("Income", styles["Heading2"]))
    if income_totals:
        rows = [["Category", "Amount (₹)"]]
        for cat, amt in sorted(income_totals.items(), key=lambda x: -x[1]):
            rows.append([_fmt_cat(cat), f"₹ {amt:,.2f}"])
        rows.append(["Total Income", f"₹ {total_income:,.2f}"])
        story.append(_table(rows))
    else:
        story.append(Paragraph("No income transactions in this period.", styles["Normal"]))
    story.append(Spacer(1, 0.5*cm))

    # Expense table
    story.append(Paragraph("Expenses", styles["Heading2"]))
    if expense_totals:
        rows = [["Category", "Amount (₹)"]]
        for cat, amt in sorted(expense_totals.items(), key=lambda x: -x[1]):
            rows.append([_fmt_cat(cat), f"₹ {amt:,.2f}"])
        rows.append(["Total Expenses", f"₹ {total_expense:,.2f}"])
        story.append(_table(rows))
    else:
        story.append(Paragraph("No expense transactions in this period.", styles["Normal"]))
    story.append(Spacer(1, 0.5*cm))

    # Summary box
    label = "Net Profit" if net_profit >= 0 else "Net Loss"
    profit_color = colors.HexColor("#27ae60") if net_profit >= 0 else colors.HexColor("#e74c3c")
    summary_rows = [
        ["Total Income",   f"₹ {total_income:,.2f}"],
        ["Total Expenses", f"₹ {total_expense:,.2f}"],
        [label,            f"₹ {abs(net_profit):,.2f}"],
    ]
    story.append(Paragraph("Summary", styles["Heading2"]))
    s_tbl = Table(summary_rows, colWidths=COL_W)
    s_tbl.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -2), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -2), 10),
        ("BACKGROUND",    (0,-1), (-1, -1), profit_color),
        ("TEXTCOLOR",     (0,-1), (-1, -1), colors.white),
        ("FONTNAME",      (0,-1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0,-1), (-1, -1), 12),
        ("ALIGN",         (1, 0), ( 1, -1), "RIGHT"),
        ("GRID",          (0, 0), (-1, -1), 0.5, GRID),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(s_tbl)

    # Footer
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "This is a system-generated draft P&L based on categorised bank transactions. "
        "Review with a Chartered Accountant before filing.",
        FOOT,
    ))

    doc.build(story)
    return buf.getvalue()


def _fmt_cat(cat: str) -> str:
    return cat.replace("_", " ").title()
