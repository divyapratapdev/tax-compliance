
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class IngestionResponse(BaseModel):
    document_id: str
    status: str
    message: str
    file_type: str
    original_filename: str

class TransactionSchema(BaseModel):
    id: str
    client_id: int
    bank_account_id: Optional[int]
    document_id: Optional[str]
    date: Optional[datetime]
    narration: Optional[str]
    amount: float
    type: Optional[str]
    category: str
    category_confidence: float
    is_reviewed: bool
    created_at: datetime

    class Config:
        from_attributes = True

class GSTInvoiceSchema(BaseModel):
    id: str
    client_id: int
    document_id: Optional[str]
    vendor_gstin: Optional[str]
    vendor_name: Optional[str]
    invoice_number: Optional[str]
    invoice_date: Optional[datetime]
    taxable_amount: float
    cgst: float
    sgst: float
    igst: float
    total: float
    source: str
    reconciliation_status: str

    class Config:
        from_attributes = True

class DocumentSchema(BaseModel):
    id: str
    client_id: int
    type: str
    original_filename: str
    storage_path: str
    ocr_status: str
    ocr_completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    document: DocumentSchema
    transactions: List[TransactionSchema] = []
    gst_invoices: List[GSTInvoiceSchema] = []
