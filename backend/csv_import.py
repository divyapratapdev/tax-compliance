import csv
import io
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from datetime import datetime
from typing import Dict, Any

from server import get_current_user, db, _now
from validators import validate_gstin

router = APIRouter()

@router.post("/import/purchase-register")
async def import_purchase_register(
    client_id: str, 
    period_month: int,
    period_year: int,
    file: UploadFile = File(...), 
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
    except Exception:
        raise HTTPException(400, "Invalid CSV format")

    entries = []
    errors = []
    
    for i, row in enumerate(reader, start=2):
        gstin = row.get("supplier_gstin", "").strip().upper()
        inv_no = row.get("invoice_number", "").strip()
        inv_date = row.get("invoice_date", "").strip()
        
        is_valid, msg = validate_gstin(gstin)
        if not is_valid:
            errors.append(f"Row {i}: Invalid GSTIN {gstin} - {msg}")
            continue
            
        try:
            parsed_date = datetime.strptime(inv_date, "%Y-%m-%d")
        except ValueError:
            errors.append(f"Row {i}: Invalid date format. Use YYYY-MM-DD")
            continue
            
        try:
            taxable = float(row.get("taxable_value", 0))
            cgst = float(row.get("cgst", 0))
            sgst = float(row.get("sgst", 0))
            igst = float(row.get("igst", 0))
            cess = float(row.get("cess", 0))
            total_tax = cgst + sgst + igst + cess
        except ValueError:
            errors.append(f"Row {i}: Invalid numeric values for taxes/amounts")
            continue
            
        entries.append({
            "client_id": client_id,
            "ca_firm_id": current_user["firm_id"],
            "supplier_gstin": gstin,
            "supplier_name": row.get("supplier_name", ""),
            "invoice_number": inv_no,
            "invoice_date": parsed_date,
            "period_month": period_month,
            "period_year": period_year,
            "taxable_value": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "cess": cess,
            "total_tax": total_tax,
            "hsn_code": row.get("hsn_code", ""),
            "source": "csv_import",
            "imported_at": _now()
        })
        
    if errors:
        raise HTTPException(status_code=400, detail={"status": "error", "errors": errors[:20]})
        
    if entries:
        # Clear existing for this period/client
        await db.purchase_register.delete_many({
            "client_id": client_id,
            "ca_firm_id": current_user["firm_id"],
            "period_month": period_month,
            "period_year": period_year
        })
        await db.purchase_register.insert_many(entries)
        
    return {"status": "success", "imported_count": len(entries)}

@router.post("/import/gstr2b")
async def import_gstr2b(
    client_id: str, 
    period_month: int,
    period_year: int,
    file: UploadFile = File(...), 
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # Same logic but saves to gstr2b_data collection
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
    except Exception:
        raise HTTPException(400, "Invalid CSV format")

    entries = []
    errors = []
    
    for i, row in enumerate(reader, start=2):
        gstin = row.get("supplier_gstin", "").strip().upper()
        inv_no = row.get("invoice_number", "").strip()
        inv_date = row.get("invoice_date", "").strip()
        
        is_valid, msg = validate_gstin(gstin)
        if not is_valid:
            errors.append(f"Row {i}: Invalid GSTIN {gstin} - {msg}")
            continue
            
        try:
            parsed_date = datetime.strptime(inv_date, "%Y-%m-%d")
        except ValueError:
            errors.append(f"Row {i}: Invalid date format. Use YYYY-MM-DD")
            continue
            
        try:
            taxable = float(row.get("taxable_value", 0))
            cgst = float(row.get("cgst", 0))
            sgst = float(row.get("sgst", 0))
            igst = float(row.get("igst", 0))
            cess = float(row.get("cess", 0))
            total_tax = cgst + sgst + igst + cess
        except ValueError:
            errors.append(f"Row {i}: Invalid numeric values for taxes/amounts")
            continue
            
        entries.append({
            "client_id": client_id,
            "ca_firm_id": current_user["firm_id"],
            "supplier_gstin": gstin,
            "supplier_name": row.get("supplier_name", ""),
            "invoice_number": inv_no,
            "invoice_date": parsed_date,
            "period_month": period_month,
            "period_year": period_year,
            "taxable_value": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "cess": cess,
            "total_tax": total_tax,
            "source": "csv_import",
            "imported_at": _now()
        })
        
    if errors:
        raise HTTPException(status_code=400, detail={"status": "error", "errors": errors[:20]})
        
    if entries:
        await db.gstr2b_data.delete_many({
            "client_id": client_id,
            "ca_firm_id": current_user["firm_id"],
            "period_month": period_month,
            "period_year": period_year
        })
        await db.gstr2b_data.insert_many(entries)
        
    return {"status": "success", "imported_count": len(entries)}

@router.post("/import/bank-statement")
async def import_bank_statement(
    client_id: str,
    fy: str = "2025-26",
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
    except Exception:
        raise HTTPException(400, "Invalid CSV format")

    entries = []
    errors = []
    
    for i, row in enumerate(reader, start=2):
        pan = row.get("vendor_pan", "").strip().upper()
        if not validate_pan(pan)[0]:
            errors.append(f"Row {i}: Invalid PAN {pan}")
            continue
            
        try:
            parsed_date = datetime.strptime(row.get("date", ""), "%Y-%m-%d")
            amount = float(row.get("amount", 0))
            tds_ded = float(row.get("tds_deducted", 0)) if row.get("tds_deducted") else 0.0
        except ValueError:
            errors.append(f"Row {i}: Invalid date or amount format")
            continue
            
        entries.append({
            "client_id": client_id,
            "ca_firm_id": current_user["firm_id"],
            "vendor_name": row.get("vendor_name", ""),
            "vendor_pan": pan,
            "payment_date": parsed_date,
            "amount": amount,
            "payment_type": row.get("payment_type", "other").lower(),
            "description": row.get("description", ""),
            "tds_deducted": tds_ded,
            "source": "csv_import",
            "imported_at": _now()
        })
        
    if errors:
        raise HTTPException(status_code=400, detail={"status": "error", "errors": errors[:20]}) # Limit to top 20 errors to avoid massive payloads
        
    if entries:
        await db.vendor_payments.insert_many(entries)
        
    return {"status": "success", "imported_count": len(entries)}
