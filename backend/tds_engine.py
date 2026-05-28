import os
import math
from typing import List, Dict, Any
import motor.motor_asyncio
from datetime import datetime

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "taxpilot")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# FY 2025-26 TDS Rates and Thresholds
TDS_RULES = {
    "194C_INDIVIDUAL": {"threshold": 100000, "single_threshold": 30000, "rate": 0.01},
    "194C_COMPANY": {"threshold": 100000, "single_threshold": 30000, "rate": 0.02},
    "194J_PROFESSIONAL": {"threshold": 30000, "rate": 0.10},
    "194J_TECHNICAL": {"threshold": 30000, "rate": 0.02},
    "194I_RENT_PLANT": {"threshold": 240000, "rate": 0.02},
    "194I_RENT_LAND": {"threshold": 240000, "rate": 0.10},
    "194H_COMMISSION": {"threshold": 15000, "rate": 0.05},
    "194Q_GOODS": {"threshold": 5000000, "rate": 0.001},
    "194R_PERQUISITES": {"threshold": 20000, "rate": 0.10},
}

def get_rule_for_payment(payment_type: str, vendor_entity_type: str) -> dict:
    if payment_type == "contractor":
        if vendor_entity_type in ["Individual", "HUF"]:
            return {"section": "194C", **TDS_RULES["194C_INDIVIDUAL"]}
        return {"section": "194C", **TDS_RULES["194C_COMPANY"]}
    elif payment_type == "professional":
        return {"section": "194J", **TDS_RULES["194J_PROFESSIONAL"]}
    elif payment_type == "technical":
        return {"section": "194J", **TDS_RULES["194J_TECHNICAL"]}
    elif payment_type == "rent_plant":
        return {"section": "194I(a)", **TDS_RULES["194I_RENT_PLANT"]}
    elif payment_type == "rent":
        return {"section": "194I(b)", **TDS_RULES["194I_RENT_LAND"]}
    elif payment_type == "commission":
        return {"section": "194H", **TDS_RULES["194H_COMMISSION"]}
    elif payment_type == "goods":
        return {"section": "194Q", **TDS_RULES["194Q_GOODS"]}
    elif payment_type == "perquisite":
        return {"section": "194R", **TDS_RULES["194R_PERQUISITES"]}
    return None

async def detect_tds_misses(client_id: str, firm_id: str, fy: str) -> Dict[str, Any]:
    # Parse FY (e.g., "2025-26")
    start_year = int(fy.split("-")[0])
    start_date = datetime(start_year, 4, 1)
    end_date = datetime(start_year + 1, 3, 31, 23, 59, 59)
    
    payments_cursor = db.vendor_payments.find({
        "client_id": client_id,
        "ca_firm_id": firm_id,
        "payment_date": {"$gte": start_date, "$lte": end_date}
    }).sort("payment_date", 1)
    
    payments = await payments_cursor.to_list(length=None)
    
    vendor_totals = {}
    missed_deductions = []
    approaching_threshold = []
    total_short_deducted = 0.0
    
    for p in payments:
        pan = p.get("vendor_pan", "UNKNOWN").strip().upper()
        ptype = p.get("payment_type", "other")
        amount = float(p.get("amount", 0))
        date = p.get("payment_date")
        entity_type = p.get("vendor_entity_type", "Company") # Would derive from PAN realistically
        
        rule = get_rule_for_payment(ptype, entity_type)
        if not rule:
            continue
            
        key = (pan, ptype)
        if key not in vendor_totals:
            vendor_totals[key] = {"total": 0, "name": p.get("vendor_name", pan)}
            
        vendor_totals[key]["total"] += amount
        cumulative = vendor_totals[key]["total"]
        
        # Check single threshold for 194C
        single_breach = "single_threshold" in rule and amount > rule["single_threshold"]
        agg_breach = cumulative > rule["threshold"]
        
        if single_breach or agg_breach:
            # Should have deducted TDS
            expected_tds = amount * rule["rate"]
            
            if agg_breach and cumulative - amount <= rule["threshold"]:
                # Just crossed the threshold!
                # We need to deduct TDS on the ENTIRE cumulative amount, not just the current payment
                expected_tds = cumulative * rule["rate"]
            
            # Special case for 194Q: TDS only on excess
            if rule["section"] == "194Q":
                if cumulative - amount < rule["threshold"]:
                    # Just crossed threshold
                    excess = cumulative - rule["threshold"]
                    expected_tds = excess * rule["rate"]
                    
            actual_tds = float(p.get("tds_deducted", 0))
            if actual_tds < expected_tds - 1.0: # 1 rupee tolerance
                shortfall = expected_tds - actual_tds
                total_short_deducted += shortfall
                
                # Calculate interest (1% per month or part thereof from payment date)
                days_delayed = (datetime.now() - date).days
                months_delayed = math.ceil(days_delayed / 30) if days_delayed > 0 else 0
                if months_delayed == 0 and shortfall > 0:
                    months_delayed = 1
                interest = shortfall * 0.01 * months_delayed
                
                missed_deductions.append({
                    "vendor_name": vendor_totals[key]["name"],
                    "vendor_pan": pan,
                    "section": rule["section"],
                    "payment_date": date.isoformat() if hasattr(date, 'isoformat') else date,
                    "amount": amount,
                    "tds_expected": round(expected_tds, 2),
                    "tds_deducted": actual_tds,
                    "shortfall": round(shortfall, 2),
                    "interest": round(interest, 2),
                    "late_fee_risk": min(months_delayed * 30 * 200, shortfall)
                })
        else:
            # Check if approaching (within 80%)
            if cumulative > rule["threshold"] * 0.8:
                approaching_threshold.append({
                    "vendor_name": vendor_totals[key]["name"],
                    "section": rule["section"],
                    "current_total": cumulative,
                    "threshold": rule["threshold"],
                    "remaining": rule["threshold"] - cumulative
                })
                
    # Deduplicate approaching alerts
    unique_approaching = {f"{a['vendor_name']}_{a['section']}": a for a in approaching_threshold}.values()
                
    return {
        "summary": {
            "total_missed": len(missed_deductions),
            "total_shortfall": round(total_short_deducted, 2),
            "vendors_approaching": len(unique_approaching)
        },
        "missed": missed_deductions,
        "approaching": list(unique_approaching)[:5]
    }
