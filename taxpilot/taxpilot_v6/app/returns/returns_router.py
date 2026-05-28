"""
returns_router.py
-----------------
Module 6 endpoints:

  GET /api/v1/returns/gstr3b/{client_id}?month=&year=
  GET /api/v1/returns/26q/{client_id}?quarter=&fy=&tan=&pan=&deductor_name=
  GET /api/v1/returns/pl-summary/{client_id}?from=&to=

Mount in main.py:
    from app.returns.returns_router import router as returns_router
    app.include_router(returns_router)
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.returns.return_generator import generate_gstr3b, generate_26q, generate_pl_pdf

router = APIRouter(prefix="/api/v1/returns", tags=["returns"])


@router.get("/gstr3b/{client_id}", response_model=Dict[str, Any])
def get_gstr3b(
    client_id: int,
    month: int = Query(..., ge=1, le=12, description="Period month 1-12"),
    year:  int = Query(..., ge=2020,     description="Period year e.g. 2025"),
    db: Session = Depends(get_db),
):
    """
    Return a prefilled GSTR-3B JSON in GSTN portal format.
    Pulls outward supplies from uploaded invoices and ITC from
    the latest completed GST reconciliation run for the period.
    """
    try:
        payload = generate_gstr3b(client_id, month, year, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"GSTR-3B generation failed: {exc}")
    return payload


@router.get("/26q/{client_id}")
def get_26q(
    client_id: int,
    quarter:       str = Query(..., pattern="^Q[1-4]$", description="Q1/Q2/Q3/Q4"),
    fy:            str = Query(..., description="Financial year e.g. 2025-26"),
    tan:           str = Query(..., description="Deductor TAN"),
    pan:           str = Query(..., description="Deductor PAN"),
    deductor_name: str = Query(..., description="Deductor name"),
    db: Session = Depends(get_db),
):
    """
    Return Form 26Q XML for the given quarter and FY as a downloadable file.
    """
    try:
        xml_bytes = generate_26q(client_id, quarter, fy, tan, pan, deductor_name, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"26Q generation failed: {exc}")

    filename = f"26Q_{client_id}_{fy}_{quarter}.xml"
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pl-summary/{client_id}")
def get_pl_summary(
    client_id: int,
    from_date: date = Query(..., alias="from", description="Start date YYYY-MM-DD"),
    to_date:   date = Query(..., alias="to",   description="End date YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """
    Return a P&L summary PDF for the given date range as a downloadable file.
    """
    if to_date < from_date:
        raise HTTPException(status_code=400, detail="'to' must be >= 'from'")

    try:
        pdf_bytes = generate_pl_pdf(client_id, from_date, to_date, db)
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"P&L PDF generation failed: {exc}")

    filename = f"PL_{client_id}_{from_date}_{to_date}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
