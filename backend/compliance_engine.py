import os
import uuid
from typing import List, Dict, Any
from datetime import datetime, date, timedelta, timezone
import motor.motor_asyncio
import calendar

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "taxpilot")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

GSTR3B_QUARTERLY_22ND_STATES = [
    "33", "32", "23", "08", "20", "29", "21", "03", "34", "06", 
    "09", "10", "19", "24", "26", "27", "30", "31", "35", "37"
]

def get_next_due_date(day: int, months_to_add: int = 1, from_date: date = None) -> date:
    d = from_date or date.today()
    month = d.month - 1 + months_to_add
    year = d.year + month // 12
    month = month % 12 + 1
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, max_day))
    
def get_quarter_end_date(d: date) -> date:
    quarter = (d.month - 1) // 3
    month = (quarter + 1) * 3
    max_day = calendar.monthrange(d.year, month)[1]
    return date(d.year, month, max_day)

def generate_compliance_calendar(client: Dict[str, Any]) -> List[Dict[str, Any]]:
    today = date.today()
    items = []
    
    is_composition = client.get("entity_type") == "Composition Dealer"
    turnover = float(client.get("turnover", 0))
    is_monthly = turnover > 50000000 # 5 Cr
    state_code = client.get("gstin", "00")[:2]
    
    # 1. GST Returns
    if is_composition:
        # CMP-08: 18th of month following quarter
        q_end = get_quarter_end_date(today)
        items.append({
            "type": "CMP-08",
            "description": "GST Composition Return",
            "due_date": get_next_due_date(18, 1, q_end),
            "penalty_description": "₹50/day late fee"
        })
        # GSTR-4: April 30th
        fy_end_year = today.year if today.month > 3 else today.year - 1
        items.append({
            "type": "GSTR-4",
            "description": "GST Annual Return (Composition)",
            "due_date": date(fy_end_year + 1, 4, 30),
            "penalty_description": "₹50/day late fee"
        })
    else:
        if is_monthly:
            # GSTR-1 (11th)
            items.append({
                "type": "GSTR-1",
                "description": "Outward Supplies Return (Monthly)",
                "due_date": get_next_due_date(11, 1),
                "penalty_description": "₹50/day (max ₹10,000)"
            })
            # GSTR-3B (20th)
            items.append({
                "type": "GSTR-3B",
                "description": "Summary Return (Monthly)",
                "due_date": get_next_due_date(20, 1),
                "penalty_description": "₹50/day + 18% p.a. interest"
            })
        else:
            # QRMP Scheme
            q_end = get_quarter_end_date(today)
            items.append({
                "type": "GSTR-1 (QRMP)",
                "description": "Outward Supplies Return (Quarterly)",
                "due_date": get_next_due_date(13, 1, q_end),
                "penalty_description": "₹50/day (max ₹10,000)"
            })
            gstr3b_day = 22 if state_code in GSTR3B_QUARTERLY_22ND_STATES else 24
            items.append({
                "type": "GSTR-3B (QRMP)",
                "description": "Summary Return (Quarterly)",
                "due_date": get_next_due_date(gstr3b_day, 1, q_end),
                "penalty_description": "₹50/day + 18% p.a. interest"
            })
            
        # Annual Returns
        fy_end_year = today.year if today.month > 3 else today.year - 1
        items.append({
            "type": "GSTR-9",
            "description": "GST Annual Return",
            "due_date": date(fy_end_year, 12, 31),
            "penalty_description": "₹200/day (Max 0.5% turnover)"
        })
        if turnover > 50000000:
            items.append({
                "type": "GSTR-9C",
                "description": "GST Reconciliation Statement",
                "due_date": date(fy_end_year, 12, 31),
                "penalty_description": "General penalty up to ₹25,000"
            })

    # 2. TDS Returns (If they deduct TDS)
    items.append({
        "type": "TDS Payment",
        "description": "Monthly TDS Deposit",
        "due_date": get_next_due_date(7, 1),
        "penalty_description": "1.5%/month interest (201(1A))"
    })
    
    # 3. Income Tax Return
    itr_due = date(fy_end_year + 1, 10, 31) if turnover > 10000000 else date(fy_end_year + 1, 7, 31)
    items.append({
        "type": "ITR",
        "description": "Income Tax Return",
        "due_date": itr_due,
        "penalty_description": "₹5,000 (Section 234F)"
    })
    
    # 4. Advance Tax
    current_q_end = get_quarter_end_date(today)
    if current_q_end.month == 6: advance_day, advance_month = 15, 6
    elif current_q_end.month == 9: advance_day, advance_month = 15, 9
    elif current_q_end.month == 12: advance_day, advance_month = 15, 12
    else: advance_day, advance_month = 15, 3
    
    items.append({
        "type": "Advance Tax",
        "description": f"Advance Tax Installment (Due {advance_day}/{advance_month})",
        "due_date": date(today.year if advance_month != 3 or today.month <= 3 else today.year + 1, advance_month, advance_day),
        "penalty_description": "1%/month interest (234C)"
    })

    return items

async def build_client_calendar(client_id: str, firm_id: str) -> List[Dict[str, Any]]:
    client_doc = await db.clients.find_one({"id": client_id, "ca_firm_id": firm_id})
    if not client_doc:
        return []
        
    items = generate_compliance_calendar(client_doc)
    
    today = date.today()
    for item in items:
        # Check if already filed in DB
        existing = await db.compliance_items.find_one({
            "client_id": client_id,
            "type": item["type"],
            "due_date": item["due_date"].isoformat()
        })
        
        if existing:
            item["status"] = existing["status"]
            item["id"] = existing["id"]
            item["due_date"] = item["due_date"].isoformat()
        else:
            days_until = (item["due_date"] - today).days
            if days_until < 0:
                item["status"] = "missed"
            else:
                item["status"] = "pending"
                
            item["id"] = str(uuid.uuid4())
            item["client_id"] = client_id
            item["due_date"] = item["due_date"].isoformat()
            item["filed_at"] = None
            item["reminder_7day_sent"] = days_until <= 7 and days_until >= 0
            item["reminder_1day_sent"] = days_until <= 1 and days_until >= 0
            item["created_at"] = datetime.now(timezone.utc).isoformat()
            
            await db.compliance_items.insert_one(item.copy())
            
    return items
