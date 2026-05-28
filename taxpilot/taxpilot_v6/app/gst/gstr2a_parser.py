
import pandas as pd
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)

class GSTR2AParser:
    """
    Parse GSTR-2A/2B data from GST portal downloads.
    Supports Excel and JSON formats.
    """

    # Standard GSTR-2A Excel column mappings (varies slightly by portal version)
    EXCEL_COLUMN_MAP = {
        # Common variations found in portal exports
        "GSTIN of Supplier": "supplier_gstin",
        "Supplier GSTIN": "supplier_gstin",
        "GSTIN": "supplier_gstin",
        "Trade/Legal Name": "supplier_name",
        "Supplier Name": "supplier_name",
        "Invoice Number": "invoice_number",
        "Document Number": "invoice_number",
        "Invoice Date": "invoice_date",
        "Document Date": "invoice_date",
        "Invoice Value": "total_amount",
        "Document Value": "total_amount",
        "Taxable Value": "taxable_amount",
        "Integrated Tax (IGST)": "igst",
        "IGST": "igst",
        "Central Tax (CGST)": "cgst",
        "CGST": "cgst",
        "State/UT Tax (SGST)": "sgst",
        "SGST": "sgst",
        "Cess": "cess",
        "Place of Supply": "place_of_supply",
        "Reverse Charge": "reverse_charge",
        "Invoice Type": "invoice_type",
        "Rate": "tax_rate",
    }

    def __init__(self):
        self.parsed_count = 0
        self.error_count = 0

    def parse_excel(self, file_path: str, period_month: int, period_year: int) -> List[Dict[str, Any]]:
        """
        Parse GSTR-2A Excel file from GST portal.
        Handles nested headers, merged cells, and multiple sheets.
        """
        invoices = []

        try:
            # Read all sheets
            xls = pd.ExcelFile(file_path)

            for sheet_name in xls.sheet_names:
                # Skip summary/total sheets
                if any(skip in sheet_name.lower() for skip in ["summary", "total", "note", "help"]):
                    continue

                df = pd.read_excel(file_path, sheet_name=sheet_name, header=None)

                # Find header row (contains "GSTIN" or "Invoice Number")
                header_row = self._find_header_row(df)
                if header_row is None:
                    logger.warning(f"No header found in sheet: {sheet_name}")
                    continue

                # Re-read with correct header
                df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)

                # Normalize column names
                df.columns = [str(col).strip() for col in df.columns]

                # Map columns
                column_mapping = {}
                for col in df.columns:
                    for pattern, field in self.EXCEL_COLUMN_MAP.items():
                        if pattern.lower() in col.lower():
                            column_mapping[col] = field
                            break

                # Rename columns
                df = df.rename(columns=column_mapping)

                # Parse each row
                for _, row in df.iterrows():
                    try:
                        invoice = self._row_to_invoice(row, period_month, period_year)
                        if invoice:
                            invoices.append(invoice)
                    except Exception as e:
                        self.error_count += 1
                        logger.warning(f"Error parsing row: {str(e)}")
                        continue

        except Exception as e:
            logger.error(f"Error parsing GSTR-2A Excel: {str(e)}")
            raise

        self.parsed_count = len(invoices)
        logger.info(f"Parsed {self.parsed_count} invoices from GSTR-2A Excel")
        return invoices

    def parse_json(self, file_path: str, period_month: int, period_year: int) -> List[Dict[str, Any]]:
        """
        Parse GSTR-2A JSON file from GST portal.
        JSON structure: { "b2b": [{ "ctin": "...", "inv": [...] }] }
        """
        invoices = []

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Handle different JSON structures
            b2b_data = data.get("b2b", [])
            if not b2b_data and "data" in data:
                b2b_data = data["data"].get("b2b", [])

            for supplier in b2b_data:
                supplier_gstin = supplier.get("ctin", "")
                supplier_name = supplier.get("cfs", "")  # Trade name if available

                for inv in supplier.get("inv", []):
                    try:
                        invoice = self._json_inv_to_invoice(
                            inv, supplier_gstin, supplier_name, period_month, period_year
                        )
                        if invoice:
                            invoices.append(invoice)
                    except Exception as e:
                        self.error_count += 1
                        logger.warning(f"Error parsing JSON invoice: {str(e)}")
                        continue

        except Exception as e:
            logger.error(f"Error parsing GSTR-2A JSON: {str(e)}")
            raise

        self.parsed_count = len(invoices)
        logger.info(f"Parsed {self.parsed_count} invoices from GSTR-2A JSON")
        return invoices

    def _find_header_row(self, df: pd.DataFrame) -> Optional[int]:
        """Find the row containing headers like 'GSTIN' or 'Invoice Number'"""
        for idx in range(min(10, len(df))):
            row_text = " ".join(str(x).lower() for x in df.iloc[idx].values if pd.notna(x))
            if "gstin" in row_text or "invoice number" in row_text or "supplier" in row_text:
                return idx
        return None

    def _row_to_invoice(self, row: pd.Series, period_month: int, period_year: int) -> Optional[Dict[str, Any]]:
        """Convert DataFrame row to invoice dict"""
        # Required fields
        gstin = str(row.get("supplier_gstin", "")).strip()
        inv_no = str(row.get("invoice_number", "")).strip()

        if not gstin or not inv_no or gstin.lower() == "nan" or inv_no.lower() == "nan":
            return None

        # Parse date
        date_val = row.get("invoice_date")
        if isinstance(date_val, str):
            inv_date = self._parse_date(date_val)
        elif isinstance(date_val, datetime):
            inv_date = date_val
        else:
            inv_date = None

        # Parse amounts
        taxable = self._parse_amount(row.get("taxable_amount", 0))
        cgst = self._parse_amount(row.get("cgst", 0))
        sgst = self._parse_amount(row.get("sgst", 0))
        igst = self._parse_amount(row.get("igst", 0))
        cess = self._parse_amount(row.get("cess", 0))
        total = self._parse_amount(row.get("total_amount", 0))

        # Compute total if not provided
        if total == 0:
            total = taxable + cgst + sgst + igst + cess

        return {
            "supplier_gstin": gstin,
            "supplier_name": str(row.get("supplier_name", "")).strip() or None,
            "invoice_number": inv_no,
            "invoice_date": inv_date,
            "taxable_amount": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "cess": cess,
            "total_amount": total,
            "total_tax": cgst + sgst + igst + cess,
            "period_month": period_month,
            "period_year": period_year,
            "source": "gstr2a",
        }

    def _json_inv_to_invoice(self, inv: Dict, supplier_gstin: str, supplier_name: str,
                             period_month: int, period_year: int) -> Optional[Dict[str, Any]]:
        """Convert JSON invoice structure to invoice dict"""
        inv_no = inv.get("inum", "").strip()
        if not inv_no:
            return None

        # Parse date (format: DD-MM-YYYY or DD/MM/YYYY)
        date_str = inv.get("idt", "")
        inv_date = self._parse_date(date_str)

        # Get item details (items array contains tax breakdown)
        items = inv.get("itms", [])
        taxable = 0
        cgst = 0
        sgst = 0
        igst = 0
        cess = 0

        for item in items:
            item_det = item.get("itm_det", {})
            taxable += self._parse_amount(item_det.get("txval", 0))
            cgst += self._parse_amount(item_det.get("camt", 0))
            sgst += self._parse_amount(item_det.get("samt", 0))
            igst += self._parse_amount(item_det.get("iamt", 0))
            cess += self._parse_amount(item_det.get("csamt", 0))

        # Total from header or computed
        total = self._parse_amount(inv.get("val", 0))
        if total == 0:
            total = taxable + cgst + sgst + igst + cess

        return {
            "supplier_gstin": supplier_gstin,
            "supplier_name": supplier_name or None,
            "invoice_number": inv_no,
            "invoice_date": inv_date,
            "taxable_amount": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "cess": cess,
            "total_amount": total,
            "total_tax": cgst + sgst + igst + cess,
            "period_month": period_month,
            "period_year": period_year,
            "source": "gstr2a",
        }

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from various formats"""
        if not date_str or date_str.lower() == "nan":
            return None

        formats = ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    def _parse_amount(self, val) -> float:
        """Parse amount handling strings with commas"""
        if pd.isna(val):
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            cleaned = val.replace(",", "").replace("₹", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0

    def get_parse_stats(self) -> Dict[str, int]:
        """Return parsing statistics"""
        return {
            "parsed": self.parsed_count,
            "errors": self.error_count,
            "success_rate": round((self.parsed_count / max(self.parsed_count + self.error_count, 1)) * 100, 2)
        }
