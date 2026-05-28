import os
import smtplib
from email.message import EmailMessage
from datetime import date
from typing import Dict, Any

from compliance_engine import generate_compliance_calendar

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
# Resend provides SMTP interface, which is easiest
SMTP_HOST = "smtp.resend.com"
SMTP_PORT = 465
SMTP_USER = "resend"
SMTP_PASS = RESEND_API_KEY

async def send_email(to_email: str, subject: str, html_content: str):
    if not RESEND_API_KEY:
        print(f"Would send email to {to_email}: {subject}")
        return
        
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = "notifications@taxpilot.com" # Requires verified domain in Resend
    msg['To'] = to_email
    msg.set_content("Please enable HTML to view this email.")
    msg.add_alternative(html_content, subtype='html')

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        def _send():
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        await loop.run_in_executor(None, _send)
    except Exception as e:
        print(f"Failed to send email: {e}")

async def send_reminder(firm: Dict[str, Any], item: Dict[str, Any], days_remaining: int):
    subject = f"⚠️ {item['description']} due in {days_remaining} day(s) — {item['client_name']}"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
        <h2>Tax Compliance Reminder</h2>
        <p>Dear {firm.get('name', 'CA')},</p>
        <p>This is an automated reminder that a compliance item is due soon for your client:</p>
        
        <div style="background-color: #f8f9fa; border-left: 4px solid #ef4444; padding: 15px; margin: 20px 0;">
            <p><strong>Client:</strong> {item['client_name']}</p>
            <p><strong>Item:</strong> {item['description']}</p>
            <p><strong>Due Date:</strong> {item['due_date']}</p>
            <p><strong>Penalty if missed:</strong> <span style="color: #ef4444;">{item.get('penalty_description', 'Statutory penalty applies')}</span></p>
        </div>
        
        <p>Please ensure this is filed on time to avoid penalties for your client.</p>
        <a href="https://tax-compliance-9qb4.vercel.app/compliance" 
           style="display: inline-block; background-color: #0f172a; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
           View Dashboard
        </a>
    </body>
    </html>
    """
    
    # Ideally firm["email"], but fallback to a test email if not set
    to_email = firm.get("email", "admin@taxpilot.com")
    await send_email(to_email, subject, html)

async def run_daily_checks(db):
    """Run via APScheduler daily at 9am"""
    today = date.today()
    
    firms = await db.firms.find({}).to_list(None)
    for firm in firms:
        # Check if firm has email alerts enabled
        alerts = firm.get("alert_preferences", {})
        if not alerts.get("email_enabled", True):
            continue
            
        clients = await db.clients.find({"ca_firm_id": firm["id"]}).to_list(None)
        
        for client in clients:
            items = generate_compliance_calendar(client)
            for item in items:
                days_until = (item["due_date"] - today).days
                
                # We want to alert at 7 days and 1 day
                if days_until == 7 or days_until == 1:
                    
                    # Check if already filed
                    existing = await db.compliance_items.find_one({
                        "client_id": client["id"],
                        "type": item["type"],
                        "due_date": item["due_date"].isoformat()
                    })
                    
                    if not existing or existing.get("status") != "filed":
                        item["client_name"] = client["name"]
                        await send_reminder(firm, item, days_until)
