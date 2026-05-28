
import pytesseract
from PIL import Image
import cv2
import numpy as np
import pdf2image
import re
from datetime import datetime
from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)

class InvoiceOCR:
    """
    OCR engine for Indian GST invoices.
    Extracts: vendor name, GSTIN, invoice number, date, amounts, tax components.
    Uses Tesseract with image preprocessing for accuracy.
    """

    def __init__(self, tesseract_cmd: Optional[str] = None):
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

        # GSTIN regex: 15 chars, 2 state code + 10 PAN + 1 entity + 1 checksum + 1 Z
        self.gstin_pattern = re.compile(r'[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}')

        # Amount patterns — using explicit digit range instead of \d to avoid warnings
        self.amount_pattern = re.compile(r'[0-9,]+\.[0-9]{2}')

        # Date patterns
        self.date_patterns = [
            re.compile(r'([0-9]{2}/[0-9]{2}/[0-9]{4})'),      # DD/MM/YYYY
            re.compile(r'([0-9]{2}-[0-9]{2}-[0-9]{4})'),      # DD-MM-YYYY
            re.compile(r'([0-9]{2}\.[0-9]{2}\.[0-9]{4})'),    # DD.MM.YYYY
            re.compile(r'([0-9]{2}\s+[A-Za-z]{3}\s+[0-9]{4})'),  # DD MMM YYYY
        ]

        # Common invoice keywords to identify vendor name
        self.invoice_keywords = ["invoice", "tax invoice", "bill", "receipt", "voucher"]

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.
        Handles: noise, skew, low contrast, poor lighting.
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Resize if too small (Tesseract works better on larger text)
        height, width = gray.shape
        if height < 1000 or width < 800:
            scale = max(1000 / height, 800 / width)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

        # Adaptive thresholding for better contrast
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )

        # Deskew if needed (simplified - check for major skew)
        coords = np.column_stack(np.where(binary > 0))
        if len(coords) > 100:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            if abs(angle) > 0.5:  # Significant skew
                (h, w) = binary.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                binary = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        return binary

    def process_image(self, image_path: str) -> Dict[str, Any]:
        """
        Process an invoice image (JPG, PNG, etc.)
        Returns extracted invoice data.
        """
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not read image: {image_path}")

            # Preprocess
            processed = self.preprocess_image(image)

            # OCR
            text = pytesseract.image_to_string(processed, lang='eng')

            # Extract structured data
            return self._extract_invoice_data(text)

        except Exception as e:
            logger.error(f"Error processing image {image_path}: {str(e)}")
            raise

    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Process an invoice PDF.
        Converts to images then OCRs each page.
        """
        try:
            # Convert PDF to images
            images = pdf2image.convert_from_path(pdf_path, dpi=300)

            all_text = []
            for i, image in enumerate(images):
                # Convert PIL to OpenCV format
                open_cv_image = np.array(image)
                open_cv_image = open_cv_image[:, :, ::-1].copy()  # RGB to BGR

                # Preprocess and OCR
                processed = self.preprocess_image(open_cv_image)
                text = pytesseract.image_to_string(processed, lang='eng')
                all_text.append(text)

            combined_text = "\n".join(all_text)
            return self._extract_invoice_data(combined_text)

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            raise

    def _extract_invoice_data(self, text: str) -> Dict[str, Any]:
        """
        Extract structured invoice data from OCR text.
        Uses regex patterns and heuristics.
        """
        lines = text.split("\n")
        text_lower = text.lower()

        result = {
            "vendor_name": None,
            "vendor_gstin": None,
            "invoice_number": None,
            "invoice_date": None,
            "taxable_amount": 0,
            "cgst": 0,
            "sgst": 0,
            "igst": 0,
            "total": 0,
            "raw_text": text,
        }

        # Extract GSTIN
        gstin_matches = self.gstin_pattern.findall(text)
        if gstin_matches:
            # Usually first GSTIN is vendor's, second is buyer's
            result["vendor_gstin"] = gstin_matches[0]

        # Extract amounts
        amounts = self._extract_amounts(text, lines)
        result.update(amounts)

        # Extract invoice number
        result["invoice_number"] = self._extract_invoice_number(text, lines)

        # Extract date
        result["invoice_date"] = self._extract_date(text)

        # Extract vendor name
        result["vendor_name"] = self._extract_vendor_name(text, lines, result["vendor_gstin"])

        return result

    def _extract_amounts(self, text: str, lines: list) -> Dict[str, float]:
        """Extract taxable amount, CGST, SGST, IGST, total"""
        amounts = {
            "taxable_amount": 0,
            "cgst": 0,
            "sgst": 0,
            "igst": 0,
            "total": 0,
        }

        text_lower = text.lower()

        # Look for specific tax lines
        for line in lines:
            line_lower = line.lower()

            # CGST
            if "cgst" in line_lower or "central tax" in line_lower:
                amt = self._find_amount_in_line(line)
                if amt > 0:
                    amounts["cgst"] = amt

            # SGST/UTGST
            elif any(kw in line_lower for kw in ["sgst", "state tax", "utgst"]):
                amt = self._find_amount_in_line(line)
                if amt > 0:
                    amounts["sgst"] = amt

            # IGST
            elif "igst" in line_lower or "integrated tax" in line_lower:
                amt = self._find_amount_in_line(line)
                if amt > 0:
                    amounts["igst"] = amt

            # Taxable value / Amount before tax
            elif any(kw in line_lower for kw in ["taxable value", "amount before tax", "subtotal", "net amount"]):
                amt = self._find_amount_in_line(line)
                if amt > 0 and amounts["taxable_amount"] == 0:
                    amounts["taxable_amount"] = amt

            # Total / Grand Total / Invoice Value
            elif any(kw in line_lower for kw in ["grand total", "invoice value", "total amount", "bill amount"]):
                amt = self._find_amount_in_line(line)
                if amt > 0:
                    amounts["total"] = amt

        # If total not found, compute from taxable + taxes
        if amounts["total"] == 0 and amounts["taxable_amount"] > 0:
            amounts["total"] = amounts["taxable_amount"] + amounts["cgst"] + amounts["sgst"] + amounts["igst"]

        # If taxable not found but total and taxes found
        if amounts["taxable_amount"] == 0 and amounts["total"] > 0:
            tax_sum = amounts["cgst"] + amounts["sgst"] + amounts["igst"]
            if tax_sum > 0:
                amounts["taxable_amount"] = amounts["total"] - tax_sum

        # Fallback: find largest amount as total, second largest as taxable
        if amounts["total"] == 0:
            all_amounts = self.amount_pattern.findall(text)
            parsed = [self._parse_amount(a) for a in all_amounts]
            parsed = [p for p in parsed if p > 0]

            if parsed:
                parsed.sort(reverse=True)
                amounts["total"] = parsed[0]
                if len(parsed) > 1:
                    amounts["taxable_amount"] = parsed[1]

        return amounts

    def _extract_invoice_number(self, text: str, lines: list) -> Optional[str]:
        """Extract invoice number from text"""
        # Common patterns — FIXED: using .+ instead of broken character classes
        patterns = [
            re.compile(r'invoice\s*(?:no|number|#|num)[:.\s]*([A-Za-z0-9\-/]+)', re.IGNORECASE),
            re.compile(r'inv\s*(?:no|#)[:.\s]*([A-Za-z0-9\-/]+)', re.IGNORECASE),
            re.compile(r'bill\s*(?:no|number|#)[:.\s]*([A-Za-z0-9\-/]+)', re.IGNORECASE),
        ]

        for pattern in patterns:
            match = pattern.search(text)
            if match:
                return match.group(1).strip()

        # Fallback: look for line with "Invoice" and extract alphanumeric
        for line in lines:
            if "invoice" in line.lower() and any(c.isdigit() for c in line):
                # Extract alphanumeric sequence with digits
                numbers = re.findall(r'[A-Za-z]*[0-9]+[A-Za-z0-9\-/]*', line)
                if numbers:
                    return numbers[0]

        return None

    def _extract_date(self, text: str) -> Optional[datetime]:
        """Extract invoice date from text"""
        for pattern in self.date_patterns:
            match = pattern.search(text)
            if match:
                date_str = match.group(1)
                for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y"]:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except ValueError:
                        continue
        return None

    def _extract_vendor_name(self, text: str, lines: list, vendor_gstin: Optional[str]) -> Optional[str]:
        """Extract vendor/seller name from invoice"""
        text_lower = text.lower()

        # Look for "Seller", "Billed By", "From", "Vendor" sections
        # FIXED: using .+ instead of broken newline character classes
        seller_patterns = [
            re.compile(r'seller[:.\s]*(.+)', re.IGNORECASE),
            re.compile(r'billed by[:.\s]*(.+)', re.IGNORECASE),
            re.compile(r'from[:.\s]*(.+)', re.IGNORECASE),
            re.compile(r'supplier[:.\s]*(.+)', re.IGNORECASE),
            re.compile(r'vendor[:.\s]*(.+)', re.IGNORECASE),
        ]

        for pattern in seller_patterns:
            match = pattern.search(text)
            if match:
                name = match.group(1).strip()
                if len(name) > 2 and not any(kw in name.lower() for kw in ["gstin", "address", "phone"]):
                    return name

        # Fallback: first few lines often contain company name
        # Skip lines with "tax invoice", "invoice", "gstin" etc.
        for line in lines[:10]:
            line = line.strip()
            if len(line) > 3 and len(line) < 100:
                if not any(kw in line.lower() for kw in ["invoice", "tax", "gstin", "date", "bill", "no.", "address", "phone", "email"]):
                    if not line.replace(" ", "").isdigit():  # Not just numbers
                        return line

        return None

    def _find_amount_in_line(self, line: str) -> float:
        """Find the first valid amount in a line"""
        matches = self.amount_pattern.findall(line)
        for match in matches:
            try:
                return float(match.replace(",", ""))
            except ValueError:
                continue
        return 0.0

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string"""
        try:
            return float(amount_str.replace(",", "").replace("₹", "").strip())
        except ValueError:
            return 0.0
