
import pdfplumber
import pandas as pd
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class BankStatementParser:
    """
    Parses Indian bank statements from PDF, Excel, CSV.
    Supports: HDFC, SBI, ICICI, Axis (extensible)
    """

    def __init__(self):
        self.bank_patterns = {
            "hdfc": {
                "headers": ["Date", "Narration", "Chq./Ref.No.", "Value Dt", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"],
                "date_pattern": r"(\d{2}/\d{2}/\d{2,4})",
                "amount_pattern": r"([\d,]+\.\d{2})",
                "narration_multiline": True,
            },
            "sbi": {
                "headers": ["Date", "Description", "Ref No", "Debit", "Credit", "Balance"],
                "date_pattern": r"(\d{2}\s+[A-Za-z]{3}\s+\d{2,4})",  # 01 Jan 2024 or 01/01/2024
                "amount_pattern": r"([\d,]+\.\d{2})",
                "narration_multiline": False,
            },
            "icici": {
                "headers": ["Tran Date", "Value Date", "Particulars", "Location", "Chq.No", "Withdrawals", "Deposits", "Balance (INR)"],
                "date_pattern": r"(\d{2}/\d{2}/\d{4})",
                "amount_pattern": r"([\d,]+\.\d{2})",
                "narration_multiline": True,
            },
            "axis": {
                "headers": ["Date", "Particulars", "Chq No", "Debit", "Credit", "Balance"],
                "date_pattern": r"(\d{2}-\d{2}-\d{4})",
                "amount_pattern": r"([\d,]+\.\d{2})",
                "narration_multiline": False,
            }
        }

        # Indian transaction categorization rules (pre-ML)
        self.category_rules = {
            "salary": ["salary", "payroll", "betterplace", "wages", "remuneration"],
            "tds_payment": ["nsdl tds", "tds payment", "tax deducted", "income tax"],
            "gst_payment": ["gst", "cgst", "sgst", "igst", "tax payment"],
            "upi": ["upi", "unified payment"],
            "neft": ["neft", "national electronic fund transfer"],
            "rtgs": ["rtgs", "real time gross settlement"],
            "imps": ["imps", "immediate payment"],
            "loan_repayment": ["loan", "emi", "repayment", "principal"],
            "utility": ["electricity", "water", "gas", "broadband", "mobile bill", "recharge"],
            "travel": ["uber", "ola", "irctc", "airline", "flight", "hotel", "makemytrip"],
            "vendor_payment": ["vendor", "supplier", "purchase", "procurement"],
            "office_expense": ["rent", "office", "stationery", "furniture", "equipment"],
            "interest": ["interest", "int pd", "int received"],
            "bank_charges": ["charges", "fee", "commission", "penalty"],
        }

    def detect_bank(self, text: str) -> str:
        """Detect bank from statement text"""
        text_lower = text.lower()
        if "hdfc" in text_lower:
            return "hdfc"
        elif "state bank" in text_lower or "sbi" in text_lower:
            return "sbi"
        elif "icici" in text_lower:
            return "icici"
        elif "axis" in text_lower:
            return "axis"
        return "unknown"

    def parse_pdf(self, file_path: str, bank_name: str = "auto") -> List[Dict[str, Any]]:
        """
        Parse bank statement PDF.
        Returns list of transaction dicts.
        """
        transactions = []

        try:
            with pdfplumber.open(file_path) as pdf:
                # Detect bank from first page if auto
                if bank_name == "auto":
                    first_page_text = pdf.pages[0].extract_text() or ""
                    bank_name = self.detect_bank(first_page_text)
                    logger.info(f"Detected bank: {bank_name}")

                pattern = self.bank_patterns.get(bank_name, self.bank_patterns["hdfc"])

                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if not text:
                        continue

                    # Try table extraction first
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            page_txns = self._parse_table(table, bank_name, pattern)
                            transactions.extend(page_txns)
                    else:
                        # Fallback: regex-based line parsing
                        page_txns = self._parse_text_lines(text, bank_name, pattern)
                        transactions.extend(page_txns)

        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {str(e)}")
            raise

        # Post-process: merge multiline narrations, deduplicate
        transactions = self._post_process(transactions, bank_name)

        logger.info(f"Extracted {len(transactions)} transactions from {bank_name} statement")
        return transactions

    def _parse_table(self, table: List[List[str]], bank_name: str, pattern: Dict) -> List[Dict]:
        """Parse extracted table into transactions"""
        transactions = []

        if not table or len(table) < 2:
            return transactions

        # Find header row
        header_row_idx = 0
        for i, row in enumerate(table):
            row_text = " ".join(str(cell or "").lower() for cell in row)
            if any(h.lower() in row_text for h in pattern["headers"]):
                header_row_idx = i
                break

        # Map columns
        headers = [str(h or "").strip().lower() for h in table[header_row_idx]]

        # Find column indices
        date_idx = self._find_column_index(headers, ["date", "tran date", "txn date"])
        narration_idx = self._find_column_index(headers, ["narration", "description", "particulars"])
        ref_idx = self._find_column_index(headers, ["chq", "ref", "cheque"])
        debit_idx = self._find_column_index(headers, ["withdrawal", "debit", "withdrawals"])
        credit_idx = self._find_column_index(headers, ["deposit", "credit", "deposits"])
        balance_idx = self._find_column_index(headers, ["balance", "closing"])

        for row in table[header_row_idx + 1:]:
            if len(row) < 3:
                continue

            try:
                date_str = str(row[date_idx] or "").strip() if date_idx is not None and date_idx < len(row) else ""
                narration = str(row[narration_idx] or "").strip() if narration_idx is not None and narration_idx < len(row) else ""
                ref_no = str(row[ref_idx] or "").strip() if ref_idx is not None and ref_idx < len(row) else ""
                debit_str = str(row[debit_idx] or "").strip() if debit_idx is not None and debit_idx < len(row) else ""
                credit_str = str(row[credit_idx] or "").strip() if credit_idx is not None and credit_idx < len(row) else ""
                balance_str = str(row[balance_idx] or "").strip() if balance_idx is not None and balance_idx < len(row) else ""

                # Skip empty rows
                if not date_str and not narration:
                    continue

                # Parse date
                date = self._parse_date(date_str, bank_name)

                # Parse amounts
                debit = self._parse_amount(debit_str)
                credit = self._parse_amount(credit_str)
                balance = self._parse_amount(balance_str)

                # Determine type and amount
                if debit > 0 and credit == 0:
                    amount = debit
                    txn_type = "debit"
                elif credit > 0 and debit == 0:
                    amount = credit
                    txn_type = "credit"
                elif debit > 0 and credit > 0:
                    # Net amount
                    amount = credit - debit
                    txn_type = "credit" if amount > 0 else "debit"
                    amount = abs(amount)
                else:
                    continue

                # Build full narration
                full_narration = narration
                if ref_no and ref_no.lower() != "nan":
                    full_narration += f" (Ref: {ref_no})"

                category = self._categorize_transaction(full_narration)

                transactions.append({
                    "date": date,
                    "narration": full_narration,
                    "amount": amount,
                    "type": txn_type,
                    "category": category,
                    "raw_debit": debit,
                    "raw_credit": credit,
                    "balance": balance,
                    "ref_no": ref_no,
                })

            except Exception as e:
                logger.warning(f"Error parsing row {row}: {str(e)}")
                continue

        return transactions

    def _parse_text_lines(self, text: str, bank_name: str, pattern: Dict) -> List[Dict]:
        """Fallback: parse text using regex patterns"""
        transactions = []
        lines = text.split("\n")

        date_regex = re.compile(pattern["date_pattern"])
        amount_regex = re.compile(pattern["amount_pattern"])

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Try to find date
            date_match = date_regex.search(line)
            if not date_match:
                continue

            date_str = date_match.group(1)
            date = self._parse_date(date_str, bank_name)

            # Find all amounts in line
            amounts = amount_regex.findall(line)
            if len(amounts) < 2:  # Need at least transaction amount and balance
                continue

            # Heuristic: last amount is usually balance, second last is transaction
            # This is fragile - table extraction is preferred
            try:
                balance = self._parse_amount(amounts[-1])
                txn_amount = self._parse_amount(amounts[-2])

                # Determine debit/credit based on context
                # Look for Dr/Cr indicators
                if "dr" in line.lower() or "debit" in line.lower() or "withdrawal" in line.lower():
                    txn_type = "debit"
                elif "cr" in line.lower() or "credit" in line.lower() or "deposit" in line.lower():
                    txn_type = "credit"
                else:
                    # Guess based on narration keywords
                    txn_type = "debit"  # Default assumption

                # Extract narration (everything between date and amounts)
                narration = self._extract_narration_from_line(line, date_str, amounts)
                category = self._categorize_transaction(narration)

                transactions.append({
                    "date": date,
                    "narration": narration,
                    "amount": txn_amount,
                    "type": txn_type,
                    "category": category,
                    "raw_debit": txn_amount if txn_type == "debit" else 0,
                    "raw_credit": txn_amount if txn_type == "credit" else 0,
                    "balance": balance,
                    "ref_no": "",
                })
            except Exception as e:
                continue

        return transactions

    def _post_process(self, transactions: List[Dict], bank_name: str) -> List[Dict]:
        """Merge multiline narrations, clean data. Max 3 continuation lines to prevent runaway merges."""
        if bank_name not in ["hdfc", "icici"]:
            return transactions

        # For HDFC/ICICI: merge transactions where narration continues on next line
        merged = []
        i = 0
        MAX_CONTINUATION_LINES = 3  # Guard against runaway merges on parse errors

        while i < len(transactions):
            txn = transactions[i].copy()
            continuation_count = 0

            # Check if next line is continuation (no date, has narration)
            while i + 1 < len(transactions) and continuation_count < MAX_CONTINUATION_LINES:
                next_txn = transactions[i + 1]
                if not next_txn.get("date") and next_txn.get("narration"):
                    # This is a continuation
                    txn["narration"] += " " + next_txn["narration"]
                    i += 1
                    continuation_count += 1
                else:
                    break

            merged.append(txn)
            i += 1

        return merged

    def _categorize_transaction(self, narration: str) -> str:
        """Categorize based on keyword rules"""
        narration_lower = narration.lower()

        for category, keywords in self.category_rules.items():
            if any(kw in narration_lower for kw in keywords):
                return category

        return "uncategorized"

    def _parse_date(self, date_str: str, bank_name: str) -> Optional[datetime]:
        """Parse date string based on bank format"""
        if not date_str or date_str.lower() == "nan":
            return None

        formats = {
            "hdfc": ["%d/%m/%y", "%d/%m/%Y"],
            "sbi": ["%d %b %Y", "%d/%m/%Y", "%d-%m-%Y"],
            "icici": ["%d/%m/%Y"],
            "axis": ["%d-%m-%Y", "%d/%m/%Y"],
        }

        for fmt in formats.get(bank_name, formats["hdfc"]):
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue

        return None

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string with Indian number formatting"""
        if not amount_str or amount_str.lower() == "nan":
            return 0.0

        # Remove currency symbols, commas
        cleaned = amount_str.replace("₹", "").replace(",", "").replace("Cr", "").replace("Dr", "").strip()

        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _find_column_index(self, headers: List[str], possible_names: List[str]) -> Optional[int]:
        """Find column index by possible header names"""
        for i, header in enumerate(headers):
            for name in possible_names:
                if name in header:
                    return i
        return None

    def _extract_narration_from_line(self, line: str, date_str: str, amounts: List[str]) -> str:
        """Extract narration from text line"""
        # Remove date and amounts, keep middle part
        temp = line.replace(date_str, "", 1)
        for amt in amounts:
            temp = temp.replace(amt, "", 1)

        # Clean up
        temp = re.sub(r'[\d,.]+', '', temp)  # Remove remaining numbers
        temp = re.sub(r'\s+', ' ', temp).strip()
        return temp

    def parse_excel(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse Excel bank statement"""
        try:
            df = pd.read_excel(file_path)
            return self._dataframe_to_transactions(df)
        except Exception as e:
            logger.error(f"Error parsing Excel {file_path}: {str(e)}")
            raise

    def parse_csv(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse CSV bank statement"""
        try:
            df = pd.read_csv(file_path)
            return self._dataframe_to_transactions(df)
        except Exception as e:
            logger.error(f"Error parsing CSV {file_path}: {str(e)}")
            raise

    def _dataframe_to_transactions(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Convert DataFrame to transaction dicts"""
        transactions = []

        # Try to identify columns
        cols = [c.lower().strip() for c in df.columns]

        date_col = self._find_column_index(cols, ["date", "tran date", "txn date", "transaction date"])
        narration_col = self._find_column_index(cols, ["narration", "description", "particulars", "details"])
        debit_col = self._find_column_index(cols, ["debit", "withdrawal", "withdrawals", "dr"])
        credit_col = self._find_column_index(cols, ["credit", "deposit", "deposits", "cr"])
        balance_col = self._find_column_index(cols, ["balance", "closing balance"])

        for idx, row in df.iterrows():
            try:
                values = row.values

                date_val = values[date_col] if date_col is not None else None
                narration = str(values[narration_col] or "") if narration_col is not None else ""
                debit = self._parse_amount(str(values[debit_col] or "")) if debit_col is not None else 0
                credit = self._parse_amount(str(values[credit_col] or "")) if credit_col is not None else 0
                balance = self._parse_amount(str(values[balance_col] or "")) if balance_col is not None else 0

                # Parse date
                if isinstance(date_val, str):
                    date = self._parse_date(date_val, "hdfc")  # Generic parser
                elif isinstance(date_val, datetime):
                    date = date_val
                else:
                    date = None

                if debit > 0 and credit == 0:
                    amount = debit
                    txn_type = "debit"
                elif credit > 0 and debit == 0:
                    amount = credit
                    txn_type = "credit"
                else:
                    continue

                category = self._categorize_transaction(narration)

                transactions.append({
                    "date": date,
                    "narration": narration,
                    "amount": amount,
                    "type": txn_type,
                    "category": category,
                    "raw_debit": debit,
                    "raw_credit": credit,
                    "balance": balance,
                    "ref_no": "",
                })

            except Exception as e:
                logger.warning(f"Error processing row {idx}: {str(e)}")
                continue

        return transactions
