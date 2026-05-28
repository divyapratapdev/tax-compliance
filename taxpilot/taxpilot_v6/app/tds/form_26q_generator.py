
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class Form26QGenerator:
    """
    Generate Form 26Q XML for NSDL TDS return filing.

    Form 26Q: Quarterly TDS return for non-salary payments (Section 200(3))
    """

    def __init__(self, tan: str, pan: str, deductor_name: str, 
                 deductor_address: Optional[str] = None):
        self.tan = tan
        self.pan = pan
        self.deductor_name = deductor_name
        self.deductor_address = deductor_address or ""

    def generate_26q(self, entries: List[Dict[str, Any]], 
                     financial_year: str, quarter: str) -> str:
        """
        Generate 26Q XML for a batch of TDS entries.

        Args:
            entries: List of TDS entry dicts
            financial_year: FY string (e.g., "2025-26")
            quarter: Quarter (Q1/Q2/Q3/Q4)

        Returns:
            XML string formatted per NSDL schema
        """
        # Create root element
        root = ET.Element("Form26Q")

        # Batch Header
        batch_header = ET.SubElement(root, "BatchHeader")
        ET.SubElement(batch_header, "TAN").text = self.tan
        ET.SubElement(batch_header, "PAN").text = self.pan
        ET.SubElement(batch_header, "FormNo").text = "26Q"
        ET.SubElement(batch_header, "Quarter").text = quarter
        ET.SubElement(batch_header, "FinancialYear").text = financial_year
        ET.SubElement(batch_header, "AssessmentYear").text = self._get_ay(financial_year)
        ET.SubElement(batch_header, "DeductorName").text = self.deductor_name
        ET.SubElement(batch_header, "DeductorAddress").text = self.deductor_address
        ET.SubElement(batch_header, "TotalEntries").text = str(len(entries))
        ET.SubElement(batch_header, "TotalTDSAmount").text = str(round(
            sum(e.get("tds_amount", 0) for e in entries), 2
        ))

        # Deductee Details
        deductee_details = ET.SubElement(root, "DeducteeDetails")

        for entry in entries:
            deductee = ET.SubElement(deductee_details, "Deductee")

            # PAN of deductee
            pan = entry.get("vendor_pan", "")
            if not pan:
                pan = "PANNOTAVBL"  # NSDL format for missing PAN
            ET.SubElement(deductee, "PAN").text = pan

            # Name
            ET.SubElement(deductee, "Name").text = entry.get("vendor_name", "Unknown")

            # Section code
            ET.SubElement(deductee, "Section").text = entry.get("tds_section", "")

            # Payment details
            payment_date = entry.get("payment_date")
            if isinstance(payment_date, datetime):
                date_str = payment_date.strftime("%Y%m%d")
            else:
                date_str = str(payment_date or "")

            ET.SubElement(deductee, "DateOfPayment").text = date_str
            ET.SubElement(deductee, "AmountPaid").text = str(entry.get("payment_amount", 0))

            # TDS details
            ET.SubElement(deductee, "TDSRate").text = str(entry.get("tds_rate", 0))
            ET.SubElement(deductee, "TDSAmount").text = str(entry.get("tds_amount", 0))
            ET.SubElement(deductee, "TDSDeducted").text = str(entry.get("tds_deducted", 0))

            # Nature of payment
            section = entry.get("tds_section", "")
            nature = self._get_nature_of_payment(section)
            ET.SubElement(deductee, "NatureOfPayment").text = nature

            # Quarter
            ET.SubElement(deductee, "Quarter").text = entry.get("quarter", quarter)

            # Remarks
            if entry.get("missed_deduction"):
                ET.SubElement(deductee, "Remarks").text = "MISSED_DEDUCTION"

        # Summary
        summary = ET.SubElement(root, "Summary")
        ET.SubElement(summary, "TotalDeductees").text = str(len(entries))
        ET.SubElement(summary, "TotalTDS").text = str(round(
            sum(e.get("tds_amount", 0) for e in entries), 2
        ))
        ET.SubElement(summary, "TotalTDSDeducted").text = str(round(
            sum(e.get("tds_deducted", 0) for e in entries), 2
        ))
        ET.SubElement(summary, "TotalTDSMissed").text = str(round(
            sum(e.get("tds_amount", 0) - e.get("tds_deducted", 0) for e in entries), 2
        ))

        # Pretty print
        xml_str = ET.tostring(root, encoding="unicode")
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ")

        # Remove empty lines
        lines = [line for line in pretty_xml.split("\n") if line.strip()]
        return "\n".join(lines)

    def generate_challan_xml(self, challan_entries: List[Dict[str, Any]],
                             challan_date: str, challan_serial: str,
                             bsr_code: str) -> str:
        """
        Generate Challan details XML for TDS deposit.

        Args:
            challan_entries: Entries covered by this challan
            challan_date: Date of deposit (YYYYMMDD)
            challan_serial: Challan serial number
            bsr_code: BSR code of bank branch
        """
        root = ET.Element("ChallanDetails")

        ET.SubElement(root, "BSRCode").text = bsr_code
        ET.SubElement(root, "DateOfDeposit").text = challan_date
        ET.SubElement(root, "ChallanSerial").text = challan_serial
        ET.SubElement(root, "TotalTDS").text = str(round(
            sum(e.get("tds_amount", 0) for e in challan_entries), 2
        ))

        # Section-wise breakup
        section_breakup = ET.SubElement(root, "SectionBreakup")
        by_section = {}
        for entry in challan_entries:
            section = entry.get("tds_section", "UNKNOWN")
            if section not in by_section:
                by_section[section] = 0
            by_section[section] += entry.get("tds_amount", 0)

        for section, amount in by_section.items():
            sec_elem = ET.SubElement(section_breakup, "Section")
            ET.SubElement(sec_elem, "Code").text = section
            ET.SubElement(sec_elem, "Amount").text = str(round(amount, 2))

        xml_str = ET.tostring(root, encoding="unicode")
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ")
        lines = [line for line in pretty_xml.split("\n") if line.strip()]
        return "\n".join(lines)

    def save_to_file(self, xml_content: str, file_path: str):
        """Save XML to file"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        logger.info(f"26Q XML saved to {file_path}")

    def _get_ay(self, financial_year: str) -> str:
        """Get assessment year from financial year"""
        # FY 2025-26 → AY 2026-27
        start_year = int(financial_year.split("-")[0])
        return f"{start_year + 1}-{str(start_year + 2)[2:]}"

    def _get_nature_of_payment(self, section: str) -> str:
        """Get nature of payment description for section"""
        nature_map = {
            "192": "Salary",
            "194C": "Contractor Payment",
            "194J": "Professional Fees",
            "194I": "Rent",
            "194A": "Interest",
            "194H": "Commission",
            "194B": "Lottery Winnings",
            "194D": "Insurance Commission",
            "194IA": "Property Transfer",
            "194IB": "Rent (Individual)",
            "194K": "Mutual Fund Dividend",
            "194O": "E-commerce Payment",
            "194Q": "Goods Purchase",
            "194R": "Benefit/Perquisite",
            "194S": "Virtual Digital Asset",
        }
        return nature_map.get(section, "Other")
