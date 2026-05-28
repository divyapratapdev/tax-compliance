
"""
TDS Rate Table — Income Tax Act, 1961
Complete rates, thresholds, and conditions for TDS deduction.
Updated for FY 2025-26 (AY 2026-27).
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class VendorType(str, Enum):
    INDIVIDUAL = "individual"
    HUF = "huf"
    COMPANY = "company"
    LLP = "llp"
    AOP = "aop"
    TRUST = "trust"
    UNKNOWN = "unknown"

@dataclass
class TDSSection:
    code: str
    description: str
    threshold_single: float          # Single payment threshold
    threshold_aggregate: float       # Annual aggregate threshold
    rate_individual: float             # Rate for individuals/HUF
    rate_company: float                # Rate for companies/LLPs
    rate_no_pan: float                 # Rate when PAN not available
    rate_special: Optional[Dict[str, float]] = None  # Special rates (e.g., plant_machinery)
    notes: str = ""

# Complete TDS Sections
TDS_SECTIONS: Dict[str, TDSSection] = {
    "192": TDSSection(
        code="192",
        description="Salary",
        threshold_single=0,              # No threshold — always applicable
        threshold_aggregate=0,
        rate_individual=0,               # Based on tax slabs (computed separately)
        rate_company=0,
        rate_no_pan=0,
        notes="Computed per tax slabs, not flat rate. Handled separately from 26Q."
    ),
    "194C": TDSSection(
        code="194C",
        description="Payment to contractors/sub-contractors",
        threshold_single=30000,          # ₹30,000 per single payment
        threshold_aggregate=100000,      # ₹1,00,000 per FY aggregate
        rate_individual=1.0,             # 1% for individuals/HUF
        rate_company=2.0,                # 2% for companies/LLPs
        rate_no_pan=20.0,                # 20% if PAN not furnished
        notes="Advertising contracts also covered. Transport contractors exempt if PAN provided."
    ),
    "194J": TDSSection(
        code="194J",
        description="Professional/technical services, royalty, non-compete",
        threshold_single=30000,          # ₹30,000 per single payment
        threshold_aggregate=30000,       # ₹30,000 per FY aggregate
        rate_individual=10.0,            # 10% standard
        rate_company=10.0,
        rate_no_pan=20.0,
        rate_special={
            "technical_services": 2.0,    # 2% for technical services (not professional)
        },
        notes="Director fees: ₹30,000 threshold. Technical services: 2% rate."
    ),
    "194I": TDSSection(
        code="194I",
        description="Rent on land, building, furniture, plant, machinery",
        threshold_single=240000,         # ₹2,40,000 per FY (annual)
        threshold_aggregate=240000,
        rate_individual=10.0,            # 10% for land/building/furniture
        rate_company=10.0,
        rate_no_pan=20.0,
        rate_special={
            "plant_machinery": 2.0,       # 2% for plant and machinery
        },
        notes="Hotel accommodation < 1 month: not rent. Hotel > 1 month: rent."
    ),
    "194A": TDSSection(
        code="194A",
        description="Interest other than securities (bank deposits, loans)",
        threshold_single=40000,          # ₹40,000 for non-senior citizens
        threshold_aggregate=40000,
        rate_individual=10.0,
        rate_company=10.0,
        rate_no_pan=20.0,
        rate_special={
            "senior_citizen": 50000,     # ₹50,000 threshold for senior citizens
        },
        notes="Senior citizen threshold: ₹50,000. Co-operative society interest: exempt up to ₹40,000."
    ),
    "194H": TDSSection(
        code="194H",
        description="Commission or brokerage",
        threshold_single=15000,          # ₹15,000 per FY
        threshold_aggregate=15000,
        rate_individual=5.0,
        rate_company=5.0,
        rate_no_pan=20.0,
        notes="Insurance commission: separate section 194D."
    ),
    "194B": TDSSection(
        code="194B",
        description="Winnings from lottery, crossword, puzzle, card game",
        threshold_single=10000,
        threshold_aggregate=10000,
        rate_individual=30.0,
        rate_company=30.0,
        rate_no_pan=30.0,
        notes="Flat 30% + cess. No threshold exemption."
    ),
    "194BB": TDSSection(
        code="194BB",
        description="Winnings from horse race",
        threshold_single=10000,
        threshold_aggregate=10000,
        rate_individual=30.0,
        rate_company=30.0,
        rate_no_pan=30.0,
        notes="Same as 194B — 30% flat."
    ),
    "194D": TDSSection(
        code="194D",
        description="Insurance commission",
        threshold_single=15000,
        threshold_aggregate=15000,
        rate_individual=5.0,             # 5% for individuals
        rate_company=10.0,               # 10% for companies
        rate_no_pan=20.0,
        notes="Insurance agent commission. Separate from 194H."
    ),
    "194DA": TDSSection(
        code="194DA",
        description="Payment in respect of life insurance policy",
        threshold_single=0,              # No threshold
        threshold_aggregate=0,
        rate_individual=5.0,             # 5% on income component (not premium)
        rate_company=5.0,
        rate_no_pan=20.0,
        notes="Only on income component, not entire premium. Exempt if premium < 10% of sum assured."
    ),
    "194E": TDSSection(
        code="194E",
        description="Payment to non-resident sportsmen/associations",
        threshold_single=0,
        threshold_aggregate=0,
        rate_individual=20.0,
        rate_company=20.0,
        rate_no_pan=20.0,
        notes="Plus cess. DTAA may apply."
    ),
    "194EE": TDSSection(
        code="194EE",
        description="Payment under National Savings Scheme",
        threshold_single=2500,
        threshold_aggregate=2500,
        rate_individual=10.0,
        rate_company=10.0,
        rate_no_pan=20.0,
        notes="NSS withdrawals."
    ),
    "194F": TDSSection(
        code="194F",
        description="Repurchase of units by mutual fund/UTI",
        threshold_single=0,
        threshold_aggregate=0,
        rate_individual=20.0,
        rate_company=20.0,
        rate_no_pan=20.0,
        notes="Now covered under 194J/194C in most cases."
    ),
    "194G": TDSSection(
        code="194G",
        description="Commission on sale of lottery tickets",
        threshold_single=15000,
        threshold_aggregate=15000,
        rate_individual=5.0,
        rate_company=5.0,
        rate_no_pan=20.0,
        notes="Lottery ticket agent commission."
    ),
    "194I(a)": TDSSection(
        code="194I(a)",
        description="Rent — Plant and Machinery",
        threshold_single=240000,
        threshold_aggregate=240000,
        rate_individual=2.0,
        rate_company=2.0,
        rate_no_pan=20.0,
        notes="Sub-section (a) — P&M at 2%."
    ),
    "194I(b)": TDSSection(
        code="194I(b)",
        description="Rent — Land/Building/Furniture",
        threshold_single=240000,
        threshold_aggregate=240000,
        rate_individual=10.0,
        rate_company=10.0,
        rate_no_pan=20.0,
        notes="Sub-section (b) — Land/Building at 10%."
    ),
    "194IA": TDSSection(
        code="194IA",
        description="Payment on transfer of immovable property",
        threshold_single=5000000,        # ₹50 lakh
        threshold_aggregate=5000000,
        rate_individual=1.0,
        rate_company=1.0,
        rate_no_pan=20.0,
        notes="Property purchase TDS. Buyer deducts, not seller."
    ),
    "194IB": TDSSection(
        code="194IB",
        description="Rent by individual/HUF (not liable to audit)",
        threshold_single=50000,          # ₹50,000 per month
        threshold_aggregate=50000,
        rate_individual=5.0,
        rate_company=5.0,
        rate_no_pan=20.0,
        notes="Individual/HUF paying rent > ₹50,000/month. No TAN required."
    ),
    "194IC": TDSSection(
        code="194IC",
        description="Payment under specified agreement (JV development)",
        threshold_single=0,
        threshold_aggregate=0,
        rate_individual=10.0,
        rate_company=10.0,
        rate_no_pan=20.0,
        notes="Joint development agreements."
    ),
    "194J(a)": TDSSection(
        code="194J(a)",
        description="Professional services",
        threshold_single=30000,
        threshold_aggregate=30000,
        rate_individual=10.0,
        rate_company=10.0,
        rate_no_pan=20.0,
        notes="CA fees, legal, medical, engineering, architectural."
    ),
    "194J(b)": TDSSection(
        code="194J(b)",
        description="Technical services",
        threshold_single=30000,
        threshold_aggregate=30000,
        rate_individual=2.0,
        rate_company=2.0,
        rate_no_pan=20.0,
        notes="Technical consultancy, managerial services."
    ),
    "194K": TDSSection(
        code="194K",
        description="Payment of income from mutual fund units",
        threshold_single=5000,
        threshold_aggregate=5000,
        rate_individual=10.0,
        rate_company=10.0,
        rate_no_pan=20.0,
        notes="Dividend income from mutual funds."
    ),
    "194LA": TDSSection(
        code="194LA",
        description="Payment of compensation on acquisition of immovable property",
        threshold_single=250000,         # ₹2.5 lakh
        threshold_aggregate=250000,
        rate_individual=10.0,
        rate_company=10.0,
        rate_no_pan=20.0,
        notes="Government acquisition compensation."
    ),
    "194LB": TDSSection(
        code="194LB",
        description="Payment of interest on infrastructure debt fund",
        threshold_single=0,
        threshold_aggregate=0,
        rate_individual=5.0,
        rate_company=5.0,
        rate_no_pan=20.0,
        notes="Non-resident interest."
    ),
    "194LBA": TDSSection(
        code="194LBA",
        description="Payment of income by business trust",
        threshold_single=0,
        threshold_aggregate=0,
        rate_individual=10.0,
        rate_company=10.0,
        rate_no_pan=20.0,
        notes="REITs/InVITs distributions."
    ),
    "194LBB": TDSSection(
        code="194LBB",
        description="Payment of income by investment fund",
        threshold_single=0,
        threshold_aggregate=0,
        rate_individual=10.0,
        rate_company=10.0,
        rate_no_pan=20.0,
        notes="AIF category I/II income."
    ),
    "194LBC": TDSSection(
        code="194LBC",
        description="Payment of income by securitisation trust",
        threshold_single=0,
        threshold_aggregate=0,
        rate_individual=25.0,            # 25% for residents
        rate_company=10.0,               # 10% for companies
        rate_no_pan=20.0,
        notes="Securitisation trust income."
    ),
    "194LC": TDSSection(
        code="194LC",
        description="Payment of interest by Indian company to non-resident",
        threshold_single=0,
        threshold_aggregate=0,
        rate_individual=5.0,
        rate_company=5.0,
        rate_no_pan=20.0,
        notes="External commercial borrowing interest."
    ),
    "194LD": TDSSection(
        code="194LD",
        description="Payment of interest on rupee-denominated bonds",
        threshold_single=0,
        threshold_aggregate=0,
        rate_individual=5.0,
        rate_company=5.0,
        rate_no_pan=20.0,
        notes="Government securities to non-residents."
    ),
    "194M": TDSSection(
        code="194M",
        description="Payment to resident contractors/professionals by individual/HUF",
        threshold_single=5000000,        # ₹50 lakh
        threshold_aggregate=5000000,
        rate_individual=5.0,
        rate_company=5.0,
        rate_no_pan=20.0,
        notes="Individual/HUF not liable to audit. No TAN required."
    ),
    "194N": TDSSection(
        code="194N",
        description="Cash withdrawal exceeding threshold",
        threshold_single=10000000,       # ₹1 crore ( ₹2 crore for co-op banks)
        threshold_aggregate=10000000,
        rate_individual=2.0,             # 2% above ₹1 crore
        rate_company=2.0,
        rate_no_pan=20.0,
        rate_special={
            "above_2cr": 5.0,            # 5% above ₹2 crore
        },
        notes="Bank cash withdrawals. Co-operative banks: ₹2 crore threshold."
    ),
    "194O": TDSSection(
        code="194O",
        description="Payment by e-commerce operator to participant",
        threshold_single=500000,         # ₹5 lakh
        threshold_aggregate=500000,
        rate_individual=1.0,             # 1% (0.5% for FY 2023-24)
        rate_company=1.0,
        rate_no_pan=5.0,
        notes="Amazon, Flipkart, Swiggy paying sellers."
    ),
    "194Q": TDSSection(
        code="194Q",
        description="Payment for purchase of goods",
        threshold_single=5000000,        # ₹50 lakh per FY
        threshold_aggregate=5000000,
        rate_individual=0.1,             # 0.1%
        rate_company=0.1,
        rate_no_pan=5.0,
        notes="Buyer with turnover > ₹10 crore. Applies to goods only, not services."
    ),
    "194R": TDSSection(
        code="194R",
        description="Deduction on benefit/perquisite to resident",
        threshold_single=20000,          # ₹20,000 per FY
        threshold_aggregate=20000,
        rate_individual=10.0,
        rate_company=10.0,
        rate_no_pan=20.0,
        notes="Free samples, gifts, perks to business associates."
    ),
    "194S": TDSSection(
        code="194S",
        description="Payment for transfer of virtual digital asset (VDA)",
        threshold_single=50000,          # ₹50,000 for specified persons
        threshold_aggregate=50000,
        rate_individual=1.0,             # 1% for specified persons
        rate_company=1.0,
        rate_no_pan=20.0,
        rate_special={
            "others": 10.0,              # 10% for non-specified persons
        },
        notes="Crypto/NFT payments. Specified person: resident with no tax return filed."
    ),
    "195": TDSSection(
        code="195",
        description="Payment to non-resident (other than salary)",
        threshold_single=0,
        threshold_aggregate=0,
        rate_individual=0,               # Per DTAA or 10-30% depending on nature
        rate_company=0,
        rate_no_pan=0,
        notes="Rates vary by income type and DTAA. Requires case-by-case determination."
    ),
}

# Category to TDS Section mapping (from categorization engine categories)
CATEGORY_TO_TDS_SECTION = {
    "professional_fees": "194J",
    "vendor_payment": "194C",        # Contractor payments
    "interest_income": "194A",        # When paying interest (not receiving)
    "rent": "194I",
    "commission": "194H",
    "insurance": "194D",              # Insurance commission
    "travel": None,                   # No TDS on travel
    "salary": "192",                  # Handled separately (not 26Q)
    "upi_transfer": None,
    "neft_rtgs": None,
    "bank_charges": None,
    "utility": None,
    "office_expense": "194C",         # If to contractor
    "loan_repayment": None,           # Principal repayment — no TDS
    "gst_payment": None,              # Tax payment — no TDS
    "tds_payment": None,              # TDS deposit — no TDS
    "investment": "194K",             # Mutual fund dividend
    "uncategorized": None,
}

# Transaction narration keywords to TDS section (fallback when category is unclear)
NARRATION_TO_SECTION = {
    "contractor": "194C",
    "subcontractor": "194C",
    "works contract": "194C",
    "advertising": "194C",
    "ca fees": "194J",
    "chartered accountant": "194J",
    "legal fees": "194J",
    "consultation": "194J",
    "consulting": "194J",
    "professional": "194J",
    "technical": "194J(b)",
    "royalty": "194J",
    "non compete": "194J",
    "rent": "194I",
    "lease": "194I",
    "tenancy": "194I",
    "landlord": "194I",
    "interest": "194A",
    "fd interest": "194A",
    "deposit interest": "194A",
    "commission": "194H",
    "brokerage": "194H",
    "lottery": "194B",
    "winnings": "194B",
    "insurance commission": "194D",
    "agent commission": "194D",
    "mutual fund": "194K",
    "dividend": "194K",
    "property purchase": "194IA",
    "immovable property": "194IA",
    "compensation": "194LA",
    "ecommerce": "194O",
    "amazon seller": "194O",
    "flipkart seller": "194O",
    "goods purchase": "194Q",
    "crypto": "194S",
    "bitcoin": "194S",
    "nft": "194S",
    "virtual asset": "194S",
}

def get_tds_rate(section_code: str, vendor_type: VendorType = VendorType.INDIVIDUAL, 
                 has_pan: bool = True, special_condition: Optional[str] = None) -> float:
    """
    Get applicable TDS rate for a section.

    Args:
        section_code: TDS section code (e.g., "194C")
        vendor_type: Type of vendor (individual/company)
        has_pan: Whether vendor has PAN
        special_condition: Special condition (e.g., "plant_machinery", "technical_services")

    Returns:
        Applicable TDS rate as percentage
    """
    section = TDS_SECTIONS.get(section_code)
    if not section:
        return 0.0

    # No PAN → 20% (or section rate if higher)
    if not has_pan:
        return max(section.rate_no_pan, section.rate_individual)

    # Special condition rate
    if special_condition and section.rate_special:
        if special_condition in section.rate_special:
            return section.rate_special[special_condition]

    # Standard rate by vendor type
    if vendor_type == VendorType.COMPANY or vendor_type == VendorType.LLP:
        return section.rate_company

    return section.rate_individual

def get_section_from_category(category: str) -> Optional[str]:
    """Map transaction category to TDS section"""
    return CATEGORY_TO_TDS_SECTION.get(category)

def get_section_from_narration(narration: str) -> Optional[str]:
    """Extract TDS section from transaction narration keywords"""
    narration_lower = narration.lower()
    for keyword, section in NARRATION_TO_SECTION.items():
        if keyword in narration_lower:
            return section
    return None

def get_threshold(section_code: str, threshold_type: str = "single") -> float:
    """Get threshold amount for a section"""
    section = TDS_SECTIONS.get(section_code)
    if not section:
        return 0.0

    if threshold_type == "single":
        return section.threshold_single
    elif threshold_type == "aggregate":
        return section.threshold_aggregate

    return 0.0
