"""
compliance_engine.py
--------------------
Generates the full-year compliance calendar for a client and runs the
daily alert scheduler (APScheduler).  All deadline rules follow Indian
tax law as of FY 2024-25.

Penalty references
------------------
GSTR-1 late fee   : ₹50/day (₹20/day for nil return) – sec 47 CGST Act
GSTR-3B late fee  : ₹50/day (₹20/day nil) + 18% p.a. interest on tax – sec 47
26Q late filing   : ₹200/day u/s 234E, max = TDS amount
Advance Tax int   : 1% per month u/s 234B / 234C
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.compliance.models.compliance_models import ComplianceItem, ComplianceType, ComplianceStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Deadline helpers
# ---------------------------------------------------------------------------

def _gstr1_due(month: int, year: int) -> date:
    """11th of the following month."""
    if month == 12:
        return date(year + 1, 1, 11)
    return date(year, month + 1, 11)


def _gstr3b_due(month: int, year: int) -> date:
    """20th of the following month."""
    if month == 12:
        return date(year + 1, 1, 20)
    return date(year, month + 1, 20)


def _tds_26q_due(quarter: str, fy_start_year: int) -> date:
    """
    Q1 (Apr-Jun)  → 31 Jul of FY start year
    Q2 (Jul-Sep)  → 31 Oct of FY start year
    Q3 (Oct-Dec)  → 31 Jan of FY start year + 1
    Q4 (Jan-Mar)  → 31 May of FY start year + 1
    """
    mapping = {
        "Q1": date(fy_start_year,     7, 31),
        "Q2": date(fy_start_year,    10, 31),
        "Q3": date(fy_start_year + 1, 1, 31),
        "Q4": date(fy_start_year + 1, 5, 31),
    }
    return mapping[quarter]


def _advance_tax_dates(fy_start_year: int) -> List[dict]:
    """
    15 Jun  → 15% of estimated liability
    15 Sep  → 45%
    15 Dec  → 75%
    15 Mar  → 100%
    """
    return [
        {"due": date(fy_start_year,      6, 15), "pct": 15,  "label": "Advance Tax – 15% (Jun)"},
        {"due": date(fy_start_year,      9, 15), "pct": 45,  "label": "Advance Tax – 45% (Sep)"},
        {"due": date(fy_start_year,     12, 15), "pct": 75,  "label": "Advance Tax – 75% (Dec)"},
        {"due": date(fy_start_year + 1,  3, 15), "pct": 100, "label": "Advance Tax – 100% (Mar)"},
    ]


def _itr_dates(fy_start_year: int, is_audit: bool) -> date:
    """31 Jul (non-audit) or 31 Oct (audit) of assessment year."""
    ay = fy_start_year + 1
    if is_audit:
        return date(ay, 10, 31)
    return date(ay, 7, 31)


def _current_fy_start(reference: date) -> int:
    """Return the April-start year for the FY that contains `reference`."""
    return reference.year if reference.month >= 4 else reference.year - 1


# ---------------------------------------------------------------------------
# Calendar generator
# ---------------------------------------------------------------------------

class ComplianceEngine:

    def generate_calendar(
        self,
        client_id: int,
        db: Session,
        reference_date: Optional[date] = None,
        is_audit_case: bool = False,
        agm_date: Optional[date] = None,   # for ROC annual return
    ) -> List[ComplianceItem]:
        """
        Generate (or regenerate) the full compliance calendar for a client.
        Existing items for the same client are deleted first so this is
        idempotent — safe to call on re-onboarding.
        """
        ref = reference_date or date.today()
        fy_start = _current_fy_start(ref)
        items: List[ComplianceItem] = []

        # --- GSTR-1 & GSTR-3B: every month of the FY ---------------------
        for month in range(1, 13):
            year = fy_start if month >= 4 else fy_start + 1

            items.append(self._make_item(
                client_id=client_id,
                type=ComplianceType.GSTR1,
                due=_gstr1_due(month, year),
                period_month=month,
                period_year=year,
                description=f"GSTR-1 for {_month_name(month)} {year}",
                penalty_per_day=50,
                penalty_description="₹50/day late fee (₹20/day for nil return) u/s 47 CGST Act",
            ))

            items.append(self._make_item(
                client_id=client_id,
                type=ComplianceType.GSTR3B,
                due=_gstr3b_due(month, year),
                period_month=month,
                period_year=year,
                description=f"GSTR-3B for {_month_name(month)} {year}",
                penalty_per_day=50,
                penalty_description="₹50/day late fee + 18% p.a. interest on tax due u/s 47 CGST Act",
            ))

        # --- TDS 26Q: 4 quarters -------------------------------------------
        for q in ["Q1", "Q2", "Q3", "Q4"]:
            items.append(self._make_item(
                client_id=client_id,
                type=ComplianceType.TDS_RETURN,
                due=_tds_26q_due(q, fy_start),
                quarter=q,
                period_year=fy_start,
                description=f"26Q TDS Return – {q} FY {fy_start}-{str(fy_start+1)[-2:]}",
                penalty_per_day=200,
                penalty_description="₹200/day u/s 234E NSDL, max = TDS amount",
            ))

        # --- Advance Tax: 4 instalments ------------------------------------
        for at in _advance_tax_dates(fy_start):
            items.append(self._make_item(
                client_id=client_id,
                type=ComplianceType.ADVANCE_TAX,
                due=at["due"],
                period_year=fy_start,
                description=at["label"],
                penalty_per_day=0,
                penalty_description="1% per month interest u/s 234B/234C on shortfall",
            ))

        # --- ITR -----------------------------------------------------------
        items.append(self._make_item(
            client_id=client_id,
            type=ComplianceType.ITR,
            due=_itr_dates(fy_start, is_audit_case),
            period_year=fy_start,
            description=f"ITR Filing – FY {fy_start}-{str(fy_start+1)[-2:]} "
                        f"({'Audit' if is_audit_case else 'Non-Audit'})",
            penalty_per_day=0,
            penalty_description="₹5,000 late filing fee u/s 234F (₹1,000 if income ≤ ₹5L)",
        ))

        # --- ROC Annual Return (if AGM date provided) ----------------------
        if agm_date:
            roc_due = agm_date + timedelta(days=60)
            items.append(self._make_item(
                client_id=client_id,
                type=ComplianceType.ROC,
                due=roc_due,
                period_year=agm_date.year,
                description=f"ROC Annual Return (MGT-7) – AGM on {agm_date}",
                penalty_per_day=100,
                penalty_description="₹100/day additional fee after due date",
            ))

        # Persist: delete old items, insert new ones
        db.query(ComplianceItem).filter(ComplianceItem.client_id == client_id).delete()
        db.add_all(items)
        db.commit()
        logger.info("Generated %d compliance items for client %d", len(items), client_id)
        return items

    # -----------------------------------------------------------------------
    # Alert logic (called by APScheduler daily)
    # -----------------------------------------------------------------------

    def run_daily_alerts(self) -> None:
        """
        Entry point for APScheduler job.
        Checks every pending item and fires alerts at the right intervals.
        Also marks overdue items as MISSED.
        """
        db = SessionLocal()
        try:
            today = date.today()
            self._mark_missed(db, today)
            self._send_7day_reminders(db, today)
            self._send_1day_reminders(db, today)
            self._send_escalations(db, today)
            db.commit()
        except Exception as exc:
            logger.error("Daily alert job failed: %s", exc, exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _mark_missed(self, db: Session, today: date) -> None:
        yesterday = datetime.combine(today - timedelta(days=1), datetime.max.time())
        missed = (
            db.query(ComplianceItem)
            .filter(
                ComplianceItem.status == ComplianceStatus.PENDING,
                ComplianceItem.due_date <= yesterday,
            )
            .all()
        )
        for item in missed:
            item.status = ComplianceStatus.MISSED
            logger.info("Marked MISSED: client=%s type=%s due=%s", item.client_id, item.type, item.due_date)

    def _send_7day_reminders(self, db: Session, today: date) -> None:
        target = datetime.combine(today + timedelta(days=7), datetime.min.time())
        target_end = datetime.combine(today + timedelta(days=7), datetime.max.time())
        items = (
            db.query(ComplianceItem)
            .filter(
                ComplianceItem.status == ComplianceStatus.PENDING,
                ComplianceItem.reminder_7day_sent == False,
                ComplianceItem.due_date >= target,
                ComplianceItem.due_date <= target_end,
            )
            .all()
        )
        for item in items:
            self._dispatch_alert(item, alert_type="7day")
            item.reminder_7day_sent = True

    def _send_1day_reminders(self, db: Session, today: date) -> None:
        target = datetime.combine(today + timedelta(days=1), datetime.min.time())
        target_end = datetime.combine(today + timedelta(days=1), datetime.max.time())
        items = (
            db.query(ComplianceItem)
            .filter(
                ComplianceItem.status == ComplianceStatus.PENDING,
                ComplianceItem.reminder_1day_sent == False,
                ComplianceItem.due_date >= target,
                ComplianceItem.due_date <= target_end,
            )
            .all()
        )
        for item in items:
            self._dispatch_alert(item, alert_type="1day")
            item.reminder_1day_sent = True

    def _send_escalations(self, db: Session, today: date) -> None:
        """Day-after-missed: fire escalation once."""
        items = (
            db.query(ComplianceItem)
            .filter(
                ComplianceItem.status == ComplianceStatus.MISSED,
                ComplianceItem.escalation_sent == False,
            )
            .all()
        )
        for item in items:
            self._dispatch_alert(item, alert_type="escalation")
            item.escalation_sent = True

    def _dispatch_alert(self, item: ComplianceItem, alert_type: str) -> None:
        """
        Sends WhatsApp + email alerts.
        Replace the stubs below with real WhatsApp Business API and SMTP calls.
        """
        days_overdue = 0
        penalty_str = ""
        if alert_type == "escalation":
            overdue_delta = datetime.utcnow() - item.due_date
            days_overdue = max(overdue_delta.days, 1)
            if item.penalty_per_day:
                est = item.penalty_per_day * days_overdue
                penalty_str = f"  Estimated penalty so far: ₹{est:,.0f}"

        messages = {
            "7day": (
                f"⏰ REMINDER — 7 days left\n"
                f"{item.description}\nDue: {item.due_date.strftime('%d %b %Y')}"
            ),
            "1day": (
                f"🚨 URGENT — Due TOMORROW\n"
                f"{item.description}\nDue: {item.due_date.strftime('%d %b %Y')}"
            ),
            "escalation": (
                f"❌ MISSED DEADLINE\n"
                f"{item.description} was due {item.due_date.strftime('%d %b %Y')}.\n"
                f"{item.penalty_description or ''}{penalty_str}"
            ),
        }
        message = messages.get(alert_type, "")

        # --- WhatsApp stub (replace with actual Business API call) ---------
        logger.info("[WhatsApp] client=%s | %s | %s", item.client_id, alert_type, message)
        # Example real call:
        # requests.post(
        #     f"https://graph.facebook.com/v18.0/{PHONE_ID}/messages",
        #     headers={"Authorization": f"Bearer {WA_TOKEN}"},
        #     json={"messaging_product": "whatsapp",
        #           "to": client_phone, "type": "text", "text": {"body": message}}
        # )

        # --- Email stub (replace with SMTP / SendGrid) ---------------------
        logger.info("[Email]    client=%s | %s | %s", item.client_id, alert_type, message)
        # Example real call:
        # send_email(to=client_email, subject=f"TaxPilot: {alert_type}", body=message)

    # -----------------------------------------------------------------------
    # Internal factory
    # -----------------------------------------------------------------------

    @staticmethod
    def _make_item(
        *,
        client_id: int,
        type: ComplianceType,
        due: date,
        description: str,
        penalty_per_day: float = 0,
        penalty_description: str = "",
        period_month: Optional[int] = None,
        period_year: Optional[int] = None,
        quarter: Optional[str] = None,
    ) -> ComplianceItem:
        return ComplianceItem(
            id=str(uuid.uuid4()),
            client_id=client_id,
            type=type.value,
            due_date=datetime.combine(due, datetime.min.time()),
            period_month=period_month,
            period_year=period_year,
            quarter=quarter,
            description=description,
            status=ComplianceStatus.PENDING.value,
            penalty_per_day=penalty_per_day,
            penalty_description=penalty_description,
        )


# ---------------------------------------------------------------------------
# APScheduler setup
# ---------------------------------------------------------------------------

def start_scheduler() -> None:
    """
    Call this once at application startup (from main.py lifespan).
    Runs ComplianceEngine.run_daily_alerts() every day at 08:00 IST.
    APScheduler stores jobs in-memory; no external broker needed.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning(
            "apscheduler not installed — compliance alerts disabled. "
            "Add 'apscheduler>=3.10' to requirements.txt"
        )
        return

    engine_instance = ComplianceEngine()
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        engine_instance.run_daily_alerts,
        trigger=CronTrigger(hour=8, minute=0),
        id="compliance_daily_alerts",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler started — compliance alerts run daily at 08:00 IST")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _month_name(month: int) -> str:
    return [
        "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ][month]
