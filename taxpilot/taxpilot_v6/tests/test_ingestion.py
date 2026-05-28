
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, get_db
from app.database import Base
from app.models import models

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override dependency
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="function")
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Create test CA firm and client
    ca_firm = models.CAFirm(
        name="Test CA Firm",
        registration_number="TEST123",
        email="test@example.com",
        plan="starter"
    )
    db.add(ca_firm)
    db.commit()
    db.refresh(ca_firm)

    client_company = models.Client(
        ca_firm_id=ca_firm.id,
        company_name="Test Pvt Ltd",
        gstin="27AABCU9603R1ZX",
        pan="AABCU9603R",
        turnover_category="medium",
        registration_type="regular"
    )
    db.add(client_company)
    db.commit()
    db.refresh(client_company)

    bank_account = models.BankAccount(
        client_id=client_company.id,
        bank_name="HDFC",
        account_number_last4="1234",
        account_type="current"
    )
    db.add(bank_account)
    db.commit()
    db.refresh(bank_account)

    yield {
        "ca_firm_id": ca_firm.id,
        "client_id": client_company.id,
        "bank_account_id": bank_account.id
    }

    Base.metadata.drop_all(bind=engine)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ingestion"

def test_upload_invalid_format(setup_db):
    # Try uploading a text file (should fail)
    with open("test.txt", "w") as f:
        f.write("not a bank statement")

    try:
        with open("test.txt", "rb") as f:
            response = client.post(
                f"/ingest/bank-statement?client_id={setup_db['client_id']}&bank_account_id={setup_db['bank_account_id']}",
                files={"file": ("test.txt", f, "text/plain")}
            )

        assert response.status_code == 400
        assert "Unsupported format" in response.json()["detail"]
    finally:
        if os.path.exists("test.txt"):
            os.remove("test.txt")

def test_create_csv_bank_statement(setup_db):
    """Test CSV upload and parsing"""
    # Create a test CSV bank statement
    csv_content = """Date,Narration,Ref No,Debit,Credit,Balance
01/01/2024,SALARY CREDIT FROM EMPLOYER,REF001,0,50000.00,50000.00
02/01/2024,UPI PAYMENT TO VENDOR,REF002,1500.00,0,48500.00
03/01/2024,NEFT TDS PAYMENT NSDL,REF003,25000.00,0,23500.00
04/01/2024,GST PAYMENT CGST SGST,REF004,18000.00,0,5500.00
05/01/2024,INTEREST RECEIVED SAVINGS,REF005,0,125.50,5625.50"""

    with open("test_statement.csv", "w") as f:
        f.write(csv_content)

    try:
        with open("test_statement.csv", "rb") as f:
            response = client.post(
                f"/ingest/bank-statement?client_id={setup_db['client_id']}&bank_account_id={setup_db['bank_account_id']}",
                files={"file": ("hdfc_statement.csv", f, "text/csv")}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["file_type"] == "bank_statement"
    finally:
        if os.path.exists("test_statement.csv"):
            os.remove("test_statement.csv")

    # Note: Background tasks don't run in TestClient, so we test the endpoint response only
    # In production, the background task would process and store transactions

def test_document_model():
    """Test database model creation"""
    db = TestingSessionLocal()

    doc = models.Document(
        id="test-doc-123",
        client_id=1,
        type="bank_statement",
        original_filename="test.pdf",
        storage_path="/uploads/test.pdf",
        ocr_status="pending"
    )
    db.add(doc)
    db.commit()

    fetched = db.query(models.Document).filter(models.Document.id == "test-doc-123").first()
    assert fetched is not None
    assert fetched.type == "bank_statement"

    db.close()



def test_end_to_end_categorization(setup_db):
    """Test full pipeline: upload CSV → transactions created → auto-categorized with fields populated"""
    import time

    # Create a test CSV with mixed transaction types
    csv_content = """Date,Narration,Ref No,Debit,Credit,Balance
01/01/2024,SALARY CREDIT FROM TCS FOR JAN 2024,REF001,0,50000.00,50000.00
02/01/2024,UPI/1234567890/SWIGGY/YBL,REF002,1500.00,0,48500.00
03/01/2024,NEFT TDS PAYMENT NSDL CHALLAN 234,REF003,25000.00,0,23500.00
04/01/2024,GST PAYMENT CGST SGST FOR DEC 2023,REF004,18000.00,0,5500.00
05/01/2024,INTEREST RECEIVED SAVINGS ACCOUNT,REF005,0,125.50,5625.50
06/01/2024,NEFT/SBIN12345/SHARMA ELEC/INV2026,REF006,5000.00,0,625.50
07/01/2024,UNKNOWN GARBAGE TRANSACTION XYZ123,REF007,100.00,0,525.50"""

    with open("test_e2e.csv", "w") as f:
        f.write(csv_content)

    try:
        with open("test_e2e.csv", "rb") as f:
            response = client.post(
                f"/ingest/bank-statement?client_id={setup_db['client_id']}&bank_account_id={setup_db['bank_account_id']}",
                files={"file": ("hdfc_statement.csv", f, "text/csv")}
            )

        assert response.status_code == 200
        doc_data = response.json()
        doc_id = doc_data["document_id"]

        # In TestClient, background tasks don't run automatically
        # We need to trigger them manually or check the DB state
        # For this test, we'll verify the document was created and check transactions

        db = TestingSessionLocal()

        # Verify document exists
        doc = db.query(models.Document).filter(models.Document.id == doc_id).first()
        assert doc is not None
        assert doc.type == "bank_statement"

        # Note: In real FastAPI with TestClient, background tasks don't execute
        # So we manually run the processing to test categorization
        from main import process_bank_statement
        process_bank_statement(
            doc_id=doc_id,
            storage_path=doc.storage_path,
            file_ext=".csv",
            client_id=setup_db["client_id"],
            bank_account_id=setup_db["bank_account_id"]
        )

        # Verify transactions were created and categorized
        transactions = db.query(models.Transaction).filter(
            models.Transaction.document_id == doc_id
        ).all()

        assert len(transactions) == 7  # 7 rows in CSV

        # Check categorization results
        categories = {txn.narration: (txn.category, txn.category_confidence, txn.needs_review) 
                      for txn in transactions}

        # Salary should be rule-matched with high confidence
        salary_txn = [t for t in transactions if "SALARY" in t.narration.upper()][0]
        assert salary_txn.category == "salary"
        assert salary_txn.category_confidence == 1.0
        assert salary_txn.needs_review == False

        # UPI should be categorized
        upi_txn = [t for t in transactions if "UPI" in t.narration.upper()][0]
        assert upi_txn.category == "upi_transfer"
        assert upi_txn.category_confidence > 0.0

        # TDS should be rule-matched
        tds_txn = [t for t in transactions if "TDS" in t.narration.upper()][0]
        assert tds_txn.category == "tds_payment"
        assert tds_txn.category_confidence == 1.0
        assert tds_txn.needs_review == False

        # GST should be rule-matched
        gst_txn = [t for t in transactions if "GST" in t.narration.upper()][0]
        assert gst_txn.category == "gst_payment"
        assert gst_txn.category_confidence == 1.0

        # Interest should be rule-matched
        interest_txn = [t for t in transactions if "INTEREST" in t.narration.upper()][0]
        assert interest_txn.category == "interest_income"
        assert interest_txn.category_confidence == 1.0

        # Vendor payment with realistic format
        vendor_txn = [t for t in transactions if "SHARMA" in t.narration.upper()][0]
        assert vendor_txn.category == "vendor_payment"
        assert vendor_txn.category_confidence > 0.0

        # Unknown garbage should be low confidence / needs review
        unknown_txn = [t for t in transactions if "UNKNOWN" in t.narration.upper()][0]
        assert unknown_txn.category_confidence < 0.9  # Below threshold
        assert unknown_txn.needs_review == True

        db.close()
    finally:
        if os.path.exists("test_e2e.csv"):
            os.remove("test_e2e.csv")

    print(f"E2E test passed: {len(transactions)} transactions categorized")
    print("Categories:", {k: v[0] for k, v in categories.items()})

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
