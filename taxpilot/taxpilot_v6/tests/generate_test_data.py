
"""
Generate synthetic bank statements and invoices for testing.
Useful for development before getting real CA data.
"""
import random
from datetime import datetime, timedelta
import pandas as pd
from fpdf import FPDF
import os

class SyntheticDataGenerator:
    def __init__(self):
        self.vendors = [
            ("ABC Suppliers Pvt Ltd", "27AABCU9603R1ZX"),
            ("XYZ Services", "29AABCU9603R1ZY"),
            ("Office Supplies Co", "07AABCU9603R1ZZ"),
            ("Tech Solutions Inc", "33AABCU9603R1ZA"),
        ]

        self.categories = {
            "salary": ["SALARY CREDIT", "PAYROLL", "WAGES"],
            "vendor_payment": ["PAYMENT TO VENDOR", "INVOICE PAYMENT", "PURCHASE"],
            "gst_payment": ["GST PAYMENT", "CGST SGST PAYMENT", "TAX DEPOSIT"],
            "tds_payment": ["TDS NSDL", "TAX DEDUCTED", "194C PAYMENT"],
            "utility": ["ELECTRICITY BILL", "INTERNET CHARGES", "PHONE BILL"],
            "travel": ["UBER TRIP", "OLA RIDE", "IRCTC BOOKING"],
            "office_expense": ["RENT PAYMENT", "OFFICE SUPPLIES", "STATIONERY"],
            "interest": ["INTEREST RECEIVED", "BANK INTEREST", "FD INTEREST"],
        }

    def generate_bank_statement_csv(self, output_path: str, num_transactions: int = 50, 
                                    bank_name: str = "HDFC", start_date: str = "2024-01-01"):
        """Generate synthetic bank statement as CSV"""
        start = datetime.strptime(start_date, "%Y-%m-%d")

        data = []
        balance = 100000.00

        for i in range(num_transactions):
            date = start + timedelta(days=i)

            # Random category
            category = random.choice(list(self.categories.keys()))
            narration = random.choice(self.categories[category])

            # Random amount
            if category in ["salary", "interest"]:
                amount = round(random.uniform(1000, 50000), 2)
                debit = 0
                credit = amount
                txn_type = "credit"
            else:
                amount = round(random.uniform(500, 20000), 2)
                debit = amount
                credit = 0
                txn_type = "debit"

            balance = balance + credit - debit

            data.append({
                "Date": date.strftime("%d/%m/%Y"),
                "Narration": f"{narration} - TXN{i:04d}",
                "Chq./Ref.No.": f"REF{i:06d}",
                "Value Dt": date.strftime("%d/%m/%Y"),
                "Withdrawal Amt.": f"{debit:.2f}" if debit > 0 else "",
                "Deposit Amt.": f"{credit:.2f}" if credit > 0 else "",
                "Closing Balance": f"{balance:.2f}",
            })

        df = pd.DataFrame(data)
        df.to_csv(output_path, index=False)
        return output_path

    def generate_invoice_pdf(self, output_path: str, vendor_idx: int = 0):
        """Generate synthetic GST invoice as PDF"""
        vendor_name, vendor_gstin = self.vendors[vendor_idx]

        invoice_no = f"INV-{random.randint(1000, 9999)}"
        date = datetime.now().strftime("%d/%m/%Y")

        taxable = round(random.uniform(1000, 50000), 2)
        cgst = round(taxable * 0.09, 2)
        sgst = round(taxable * 0.09, 2)
        total = round(taxable + cgst + sgst, 2)

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "TAX INVOICE", ln=True, align="C")
        pdf.ln(10)

        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Seller: {vendor_name}", ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 8, f"GSTIN: {vendor_gstin}", ln=True)
        pdf.cell(0, 8, f"Invoice No: {invoice_no}", ln=True)
        pdf.cell(0, 8, f"Date: {date}", ln=True)
        pdf.ln(10)

        pdf.set_font("Arial", "B", 10)
        pdf.cell(60, 8, "Description", border=1)
        pdf.cell(40, 8, "Taxable Value", border=1, align="R")
        pdf.cell(30, 8, "CGST (9%)", border=1, align="R")
        pdf.cell(30, 8, "SGST (9%)", border=1, align="R")
        pdf.cell(30, 8, "Total", border=1, align="R")
        pdf.ln()

        pdf.set_font("Arial", "", 10)
        pdf.cell(60, 8, "Professional Services", border=1)
        pdf.cell(40, 8, f"{taxable:.2f}", border=1, align="R")
        pdf.cell(30, 8, f"{cgst:.2f}", border=1, align="R")
        pdf.cell(30, 8, f"{sgst:.2f}", border=1, align="R")
        pdf.cell(30, 8, f"{total:.2f}", border=1, align="R")
        pdf.ln()

        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Grand Total: Rs. {total:.2f}", ln=True)

        pdf.output(output_path)
        return output_path

if __name__ == "__main__":
    gen = SyntheticDataGenerator()

    # Generate test data
    os.makedirs("test_data", exist_ok=True)

    gen.generate_bank_statement_csv("test_data/hdfc_jan_2024.csv", num_transactions=30)
    print("Generated: test_data/hdfc_jan_2024.csv")

    gen.generate_invoice_pdf("test_data/invoice_abc.pdf", vendor_idx=0)
    print("Generated: test_data/invoice_abc.pdf")
