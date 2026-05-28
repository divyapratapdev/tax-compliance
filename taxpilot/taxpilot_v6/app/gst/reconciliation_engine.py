
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)

class GSTReconciliationEngine:
    """
    3-Pass GST Reconciliation Engine.

    Pass 1: Exact Match — GSTIN + Invoice Number + Date + Amount (within ₹ tolerance)
    Pass 2: Pattern Match — Normalize invoice numbers (remove special chars, zeros) + fuzzy match
    Pass 3: GSTIN Logic — Same PAN, different state codes or typos

    Mismatch categories:
    - MATCHED: All fields align, ITC safe
    - AMOUNT_MISMATCH: GSTIN + Invoice match, but amount differs
    - MISSING_IN_2A: In books but supplier didn't file
    - MISSING_IN_BOOKS: Supplier filed but not in books
    - GSTIN_MISMATCH: Invoice matches but GSTIN differs
    """

    def __init__(self, amount_tolerance: float = 1.0, date_tolerance_days: int = 5):
        """
        Args:
            amount_tolerance: ₹ tolerance for amount matching (default ₹1 for rounding)
            date_tolerance_days: Days tolerance for invoice date matching
        """
        self.amount_tolerance = amount_tolerance
        self.date_tolerance = timedelta(days=date_tolerance_days)

    def reconcile(self, 
                  client_invoices: List[Dict[str, Any]], 
                  gstr2a_invoices: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run full reconciliation between client invoices and GSTR-2A data.

        Returns:
            {
                "matched": [...],
                "amount_mismatch": [...],
                "missing_in_2a": [...],
                "missing_in_books": [...],
                "gstin_mismatch": [...],
                "summary": {...}
            }
        """
        # Create lookup indexes for fast matching
        books_index = self._build_index(client_invoices)
        gstr2a_index = self._build_index(gstr2a_invoices)

        results = {
            "matched": [],
            "amount_mismatch": [],
            "missing_in_2a": [],
            "missing_in_books": [],
            "gstin_mismatch": [],
        }

        # Track which invoices have been matched
        matched_books_ids = set()
        matched_gstr2a_ids = set()

        # === PASS 1: Exact Match ===
        logger.info("Starting Pass 1: Exact Match")
        for books_inv in client_invoices:
            match = self._exact_match(books_inv, gstr2a_index)
            if match:
                gstr2a_inv, match_type = match

                if match_type == "full":
                    results["matched"].append({
                        "books_invoice": books_inv,
                        "gstr2a_invoice": gstr2a_inv,
                        "match_type": "exact",
                        "confidence": "high"
                    })
                else:  # amount_mismatch
                    results["amount_mismatch"].append({
                        "books_invoice": books_inv,
                        "gstr2a_invoice": gstr2a_inv,
                        "difference": round(books_inv["total_amount"] - gstr2a_inv["total_amount"], 2),
                        "suggested_action": "Verify correct amount with supplier"
                    })

                matched_books_ids.add(books_inv.get("id", books_inv["invoice_number"]))
                matched_gstr2a_ids.add(gstr2a_inv.get("id", gstr2a_inv["invoice_number"]))

        # === PASS 2: Pattern/Fuzzy Match on remaining ===
        logger.info("Starting Pass 2: Pattern Match")
        remaining_books = [inv for inv in client_invoices 
                          if inv.get("id", inv["invoice_number"]) not in matched_books_ids]
        remaining_gstr2a = [inv for inv in gstr2a_invoices 
                           if inv.get("id", inv["invoice_number"]) not in matched_gstr2a_ids]

        for books_inv in remaining_books:
            match = self._pattern_match(books_inv, remaining_gstr2a)
            if match:
                gstr2a_inv, match_type = match

                if match_type == "full":
                    results["matched"].append({
                        "books_invoice": books_inv,
                        "gstr2a_invoice": gstr2a_inv,
                        "match_type": "pattern",
                        "confidence": "medium"
                    })
                else:
                    results["amount_mismatch"].append({
                        "books_invoice": books_inv,
                        "gstr2a_invoice": gstr2a_inv,
                        "difference": round(books_inv["total_amount"] - gstr2a_inv["total_amount"], 2),
                        "suggested_action": "Verify invoice number format and amount with supplier"
                    })

                matched_books_ids.add(books_inv.get("id", books_inv["invoice_number"]))
                matched_gstr2a_ids.add(gstr2a_inv.get("id", gstr2a_inv["invoice_number"]))

        # === PASS 3: GSTIN Logic (same PAN, different state code) ===
        logger.info("Starting Pass 3: GSTIN Logic")
        remaining_books = [inv for inv in client_invoices 
                          if inv.get("id", inv["invoice_number"]) not in matched_books_ids]
        remaining_gstr2a = [inv for inv in gstr2a_invoices 
                           if inv.get("id", inv["invoice_number"]) not in matched_gstr2a_ids]

        for books_inv in remaining_books:
            match = self._gstin_logic_match(books_inv, remaining_gstr2a)
            if match:
                gstr2a_inv, match_type = match

                results["gstin_mismatch"].append({
                    "books_invoice": books_inv,
                    "gstr2a_invoice": gstr2a_inv,
                    "books_gstin": books_inv["supplier_gstin"],
                    "gstr2a_gstin": gstr2a_inv["supplier_gstin"],
                    "suggested_action": "Verify supplier GSTIN — possible state code change or typo"
                })

                matched_books_ids.add(books_inv.get("id", books_inv["invoice_number"]))
                matched_gstr2a_ids.add(gstr2a_inv.get("id", gstr2a_inv["invoice_number"]))

        # === Final Classification ===
        # Remaining in books = Missing in 2A
        for books_inv in client_invoices:
            if books_inv.get("id", books_inv["invoice_number"]) not in matched_books_ids:
                results["missing_in_2a"].append({
                    "books_invoice": books_inv,
                    "suggested_action": "Follow up with supplier to file GSTR-1, or claim ITC conditionally"
                })

        # Remaining in GSTR-2A = Missing in books
        for gstr2a_inv in gstr2a_invoices:
            if gstr2a_inv.get("id", gstr2a_inv["invoice_number"]) not in matched_gstr2a_ids:
                results["missing_in_books"].append({
                    "gstr2a_invoice": gstr2a_inv,
                    "suggested_action": "Add missing purchase entry to books"
                })

        # Generate summary
        summary = self._generate_summary(results, client_invoices, gstr2a_invoices)
        results["summary"] = summary

        return results

    def _build_index(self, invoices: List[Dict[str, Any]]) -> Dict:
        """Build lookup index by GSTIN for fast matching"""
        index = {}
        for inv in invoices:
            gstin = inv.get("supplier_gstin", "")
            if gstin not in index:
                index[gstin] = []
            index[gstin].append(inv)
        return index

    def _exact_match(self, books_inv: Dict, gstr2a_index: Dict) -> Optional[Tuple[Dict, str]]:
        """
        Pass 1: Exact match on GSTIN + Invoice Number + Date + Amount.
        Returns (matched_invoice, match_type) or None.
        """
        gstin = books_inv.get("supplier_gstin", "")
        inv_no = books_inv.get("invoice_number", "")

        if gstin not in gstr2a_index:
            return None

        candidates = gstr2a_index[gstin]

        for candidate in candidates:
            # Check invoice number exact match
            if candidate["invoice_number"] != inv_no:
                continue

            # Check date within tolerance
            if not self._dates_match(books_inv.get("invoice_date"), candidate.get("invoice_date")):
                continue

            # Check amount within tolerance
            amount_diff = abs(books_inv.get("total_amount", 0) - candidate.get("total_amount", 0))
            if amount_diff <= self.amount_tolerance:
                return candidate, "full"
            else:
                # GSTIN + Invoice + Date match, but amount differs
                return candidate, "amount_mismatch"

        return None

    def _pattern_match(self, books_inv: Dict, gstr2a_invoices: List[Dict]) -> Optional[Tuple[Dict, str]]:
        """
        Pass 2: Pattern match — normalize invoice numbers and use fuzzy matching.
        """
        gstin = books_inv.get("supplier_gstin", "")
        books_inv_norm = self._normalize_invoice_number(books_inv.get("invoice_number", ""))
        books_date = books_inv.get("invoice_date")
        books_amount = books_inv.get("total_amount", 0)

        best_match = None
        best_score = 0.0

        for candidate in gstr2a_invoices:
            # GSTIN must match
            if candidate["supplier_gstin"] != gstin:
                continue

            # Normalize candidate invoice number
            cand_inv_norm = self._normalize_invoice_number(candidate.get("invoice_number", ""))

            # Fuzzy match on invoice number
            similarity = SequenceMatcher(None, books_inv_norm, cand_inv_norm).ratio()

            if similarity < 0.8:  # Require 80% similarity
                continue

            # Date check
            if not self._dates_match(books_date, candidate.get("invoice_date")):
                continue

            # Score based on similarity and amount closeness
            amount_diff = abs(books_amount - candidate.get("total_amount", 0))
            amount_score = max(0, 1 - (amount_diff / max(books_amount, 1)))

            score = (similarity * 0.6) + (amount_score * 0.4)

            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= 0.7:
            amount_diff = abs(books_amount - best_match.get("total_amount", 0))
            if amount_diff <= self.amount_tolerance:
                return best_match, "full"
            else:
                return best_match, "amount_mismatch"

        return None

    def _gstin_logic_match(self, books_inv: Dict, gstr2a_invoices: List[Dict]) -> Optional[Tuple[Dict, str]]:
        """
        Pass 3: GSTIN Logic — same PAN, different state codes.
        GSTIN format: 2-digit state + 10-char PAN + 1 entity + 1 checksum + Z
        """
        books_gstin = books_inv.get("supplier_gstin", "")
        books_pan = self._extract_pan(books_gstin)
        books_inv_no = books_inv.get("invoice_number", "")

        if not books_pan:
            return None

        for candidate in gstr2a_invoices:
            cand_gstin = candidate.get("supplier_gstin", "")
            cand_pan = self._extract_pan(cand_gstin)

            # Same PAN, different GSTIN
            if cand_pan == books_pan and cand_gstin != books_gstin:
                # Check if invoice number matches
                if candidate["invoice_number"] == books_inv_no:
                    return candidate, "gstin_mismatch"

                # Fuzzy match on invoice number
                cand_inv_norm = self._normalize_invoice_number(candidate.get("invoice_number", ""))
                books_inv_norm = self._normalize_invoice_number(books_inv_no)
                similarity = SequenceMatcher(None, books_inv_norm, cand_inv_norm).ratio()

                if similarity >= 0.85:
                    # Also require amount proximity within 10% to prevent false positives
                    # (e.g., INV2026003 vs INV2026004 from different months)
                    books_amount = books_inv.get("total_amount", 0)
                    cand_amount = candidate.get("total_amount", 0)
                    max_amount = max(books_amount, cand_amount, 1)
                    amount_diff_pct = abs(books_amount - cand_amount) / max_amount

                    if amount_diff_pct <= 0.10:
                        return candidate, "gstin_mismatch"

        return None

    def _normalize_invoice_number(self, inv_no: str) -> str:
        """
        Normalize invoice number for fuzzy matching.
        Remove special chars, leading zeros, financial year suffixes.
        """
        if not inv_no:
            return ""

        # Convert to uppercase
        normalized = inv_no.upper()

        # Remove common special characters
        for char in ["/", "-", "\\", "_", "#", "@", "$", "%", "&", "*"]:
            normalized = normalized.replace(char, "")

        # Remove leading zeros
        normalized = normalized.lstrip("0")

        # Remove common financial year suffixes (e.g., "/24-25", "-2024")
        import re
        normalized = re.sub(r"(20)?[0-9]{2}[-/]?(20)?[0-9]{2}$", "", normalized)
        normalized = re.sub(r"[-/]?(20)?[0-9]{4}$", "", normalized)

        return normalized.strip()

    def _extract_pan(self, gstin: str) -> str:
        """Extract 10-char PAN from 15-char GSTIN"""
        if len(gstin) == 15:
            return gstin[2:12]
        return ""

    def _dates_match(self, date1, date2) -> bool:
        """Check if two dates are within tolerance"""
        if not date1 or not date2:
            return True  # If either date is missing, don't reject match

        if isinstance(date1, str):
            date1 = datetime.strptime(date1, "%Y-%m-%d") if date1 else None
        if isinstance(date2, str):
            date2 = datetime.strptime(date2, "%Y-%m-%d") if date2 else None

        if not date1 or not date2:
            return True

        return abs((date1 - date2).days) <= self.date_tolerance.days

    def _generate_summary(self, results: Dict, books_invoices: List, gstr2a_invoices: List) -> Dict:
        """Generate reconciliation summary with ITC calculations"""

        # ITC safe = matched invoices total tax
        itc_safe = sum(
            m["books_invoice"].get("total_tax", 0) 
            for m in results["matched"]
        )

        # ITC at risk = missing in 2A + amount mismatch
        itc_at_risk = sum(
            m["books_invoice"].get("total_tax", 0) 
            for m in results["missing_in_2a"]
        )
        itc_at_risk += sum(
            min(m["books_invoice"].get("total_tax", 0), m["gstr2a_invoice"].get("total_tax", 0))
            for m in results["amount_mismatch"]
        )

        # ITC missing in books = supplier filed but we don't have
        itc_missing = sum(
            m["gstr2a_invoice"].get("total_tax", 0) 
            for m in results["missing_in_books"]
        )

        return {
            "total_books_invoices": len(books_invoices),
            "total_gstr2a_invoices": len(gstr2a_invoices),
            "matched_count": len(results["matched"]),
            "amount_mismatch_count": len(results["amount_mismatch"]),
            "missing_in_2a_count": len(results["missing_in_2a"]),
            "missing_in_books_count": len(results["missing_in_books"]),
            "gstin_mismatch_count": len(results["gstin_mismatch"]),
            "match_rate": round(len(results["matched"]) / max(len(books_invoices), 1) * 100, 2),
            "itc_safe_amount": round(itc_safe, 2),
            "itc_at_risk_amount": round(itc_at_risk, 2),
            "itc_missing_in_books_amount": round(itc_missing, 2),
            "total_itc_potential": round(itc_safe + itc_at_risk + itc_missing, 2),
        }
