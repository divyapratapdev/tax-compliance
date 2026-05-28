import asyncio
import os
import fitz  # PyMuPDF
from typing import Dict, Any
from datetime import datetime, timezone

# Ensure uploads directory exists
os.makedirs("uploads", exist_ok=True)

async def process_document_background(db, doc_id: str, file_path: str, doc_type: str):
    # Simulate processing time
    await asyncio.sleep(2)
    
    extracted_text = ""
    try:
        # Check if it's a PDF
        if file_path.lower().endswith(".pdf"):
            loop = asyncio.get_event_loop()
            def extract():
                t = ""
                doc = fitz.open(file_path)
                for page in doc:
                    t += page.get_text()
                doc.close()
                return t
            extracted_text = await loop.run_in_executor(None, extract)
        else:
            extracted_text = "Simulated extraction for non-PDF file."
            
        # Mock logic based on doc_type
        if doc_type == "invoice":
            result = "processed"
            notes = f"Extracted {len(extracted_text)} characters. Identified as Invoice."
        elif doc_type == "bank_statement":
            result = "processed"
            notes = f"Extracted {len(extracted_text)} characters. Identified as Bank Statement."
        else:
            result = "processed"
            notes = "Processed standard document."
            
    except Exception as e:
        result = "failed"
        notes = f"OCR Error: {str(e)}"
        
    await db.documents.update_one(
        {"id": doc_id},
        {"$set": {
            "ocr_status": "completed" if result == "processed" else "failed",
            "ocr_error": notes if result == "failed" else None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "extracted_count": max(1, len(extracted_text) // 100) if result == "processed" else None
        }}
    )
