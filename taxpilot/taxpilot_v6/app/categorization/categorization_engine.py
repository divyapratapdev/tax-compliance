
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV
from typing import List, Dict, Any, Tuple, Optional
import re
import logging
from datetime import datetime
import os
import json

logger = logging.getLogger(__name__)

class TransactionCategorizer:
    """
    ML-powered transaction categorization for Indian accounting.

    Categories:
    - salary: Payroll, wages, remuneration
    - vendor_payment: Supplier payments, purchases
    - gst_payment: CGST, SGST, IGST payments to government
    - tds_payment: TDS deposits to NSDL
    - upi_transfer: UPI payments (personal/misc)
    - neft_rtgs: Bank transfers
    - loan_repayment: EMI, loan payments
    - utility: Electricity, internet, phone
    - travel: Uber, Ola, flights, hotels
    - office_expense: Rent, stationery, furniture
    - interest_income: Bank interest, FD interest
    - bank_charges: Fees, penalties, commission
    - professional_fees: CA fees, legal, consulting
    - insurance: Premium payments
    - investment: Mutual funds, stocks, deposits
    - uncategorized: Unknown / needs review
    """

    CATEGORIES = [
        "salary", "vendor_payment", "gst_payment", "tds_payment",
        "upi_transfer", "neft_rtgs", "loan_repayment", "utility",
        "travel", "office_expense", "interest_income", "bank_charges",
        "professional_fees", "insurance", "investment", "uncategorized"
    ]

    # High-confidence rule patterns (never override ML if matched)
    RULE_PATTERNS = {
        "salary": [
            r"\bsalary\b", r"\bpayroll\b", r"\bwages\b",
            r"\bremuneration\b", r"\bmonthly pay\b", r"\bnet pay\b",
            r"\bsalary credit\b", r"\beps\b.*\bsalary\b"
        ],
        "gst_payment": [
            r"\bgst\b.*\bpayment\b", r"\bcgst\b", r"\bsgst\b",
            r"\bigst\b", r"\bgst\b.*\btax\b", r"\bgst\b.*\bdeposit\b",
            r"\bchallan\b.*\bgst\b", r"\bgst\b.*\bchallan\b"
        ],
        "tds_payment": [
            r"\btds\b", r"\bnsdl\b", r"\btax\b.*\bdeducted\b",
            r"\b194c\b", r"\b194j\b", r"\b194i\b",
            r"\btds\b.*\bpayment\b", r"\btds\b.*\bdeposit\b"
        ],
        "upi_transfer": [
            r"\bupi\b", r"\bunified\b.*\bpayment\b",
            r"\bupi\b.*\btransfer\b", r"\bupi\b.*\bpay\b"
        ],
        "neft_rtgs": [
            r"\bneft\b", r"\brtgs\b", r"\bnational\b.*\belectronic\b",
            r"\breal\b.*\btime\b.*\bgross\b"
        ],
        "loan_repayment": [
            r"\bemi\b", r"\bloan\b.*\brepayment\b", r"\bloan\b.*\bpayment\b",
            r"\bhousing\b.*\bloan\b", r"\bpersonal\b.*\bloan\b",
            r"\bterm\b.*\bloan\b", r"\bprincipal\b.*\brepayment\b"
        ],
        "utility": [
            r"\belectricity\b", r"\bwater\b.*\bbill\b", r"\bgas\b.*\bbill\b",
            r"\bbroadband\b", r"\binternet\b", r"\bmobile\b.*\bbill\b",
            r"\brecharge\b", r"\bpostpaid\b", r"\bprepaid\b",
            r"\bpower\b.*\bsupply\b", r"\bescom\b", r"\bmsedcl\b"
        ],
        "travel": [
            r"\buber\b", r"\bola\b", r"\birctc\b", r"\bairline\b",
            r"\bflight\b", r"\bhotel\b", r"\bmakemytrip\b",
            r"\bcleartrip\b", r"\bgoibibo\b", r"\byatra\b",
            r"\btrip\b", r"\btaxi\b", r"\bcab\b"
        ],
        "office_expense": [
            r"\brent\b", r"\boffice\b.*\bsupply\b", r"\bstationery\b",
            r"\bfurniture\b", r"\bequipment\b", r"\bprinter\b",
            r"\bmaintenance\b", r"\bcleaning\b", r"\bsecurity\b"
        ],
        "interest_income": [
            r"\binterest\b.*\breceived\b", r"\binterest\b.*\bcredit\b",
            r"\bfd\b.*\binterest\b", r"\bsavings\b.*\binterest\b",
            r"\bint\b.*\brcvd\b", r"\bint\b.*\bcr\b"
        ],
        "bank_charges": [
            r"\bcharges\b", r"\bfee\b", r"\bcommission\b",
            r"\bpenalty\b", r"\blate\b.*\bfee\b", r"\bprocessing\b.*\bfee\b",
            r"\bannual\b.*\bfee\b", r"\bmaintenance\b.*\bfee\b"
        ],
        "professional_fees": [
            r"\bca\b.*\bfee\b", r"\bconsultation\b", r"\bconsulting\b",
            r"\blegal\b.*\bfee\b", r"\bprofessional\b.*\bfee\b",
            r"\bchartered\b.*\baccountant\b", r"\battorney\b"
        ],
        "insurance": [
            r"\binsurance\b", r"\bpremium\b", r"\blic\b",
            r"\bhealth\b.*\binsurance\b", r"\blife\b.*\binsurance\b",
            r"\bvehicle\b.*\binsurance\b", r"\bgic\b", r"\blic\b"
        ],
        "investment": [
            r"\bmutual\b.*\bfund\b", r"\bsip\b", r"\bstock\b",
            r"\bshares\b", r"\bequity\b", r"\bfixed\b.*\bdeposit\b",
            r"\brecurring\b.*\bdeposit\b", r"\bnps\b", r"\bepf\b"
        ],
        "vendor_payment": [
            r"\bpurchase\b", r"\bsupplier\b", r"\bvendor\b.*\bpayment\b",
            r"\bprocurement\b", r"\bgoods\b.*\bpurchase\b"
        ]
    }

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or "app/categorization/models/categorizer.pkl"
        self.pipeline = None
        self.is_trained = False

        # Load pre-trained model if exists
        if os.path.exists(self.model_path):
            self._load_model()

    def _load_model(self):
        """Load trained model from disk"""
        try:
            self.pipeline = joblib.load(self.model_path)
            self.is_trained = True
            logger.info(f"Loaded categorization model from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            self.pipeline = None
            self.is_trained = False

    def _save_model(self):
        """Save trained model to disk"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        temp_path = f"{self.model_path}.tmp.{os.getpid()}"
        joblib.dump(self.pipeline, temp_path)
        os.replace(temp_path, self.model_path)
        logger.info(f"Saved categorization model to {self.model_path}")

    def _preprocess_text(self, narration: str) -> str:
        """
        Preprocess transaction narration for ML.
        - Lowercase
        - Remove extra spaces
        - Keep alphanumeric and key symbols
        """
        if not narration:
            return ""

        # Lowercase
        text = narration.lower()

        # Remove account numbers, UPI IDs (noise)
        text = re.sub(r"\b\d{9,}\b", "", text)  # Long numbers
        text = re.sub(r"\b[A-Z0-9]+@[A-Z0-9]+\b", "", text)  # UPI IDs

        # Normalize spaces
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def _apply_rules(self, narration: str) -> Tuple[Optional[str], float]:
        """
        Apply rule-based categorization.
        Returns (category, confidence) or (None, 0.0) if no rule matches.
        """
        if not narration:
            return None, 0.0

        text = narration.lower()

        for category, patterns in self.RULE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    # Rule match = high confidence
                    return category, 1.0

        return None, 0.0

    def _build_pipeline(self):
        """Build scikit-learn TF-IDF + SVM pipeline"""
        # LinearSVC with probability calibration via CalibratedClassifierCV
        base_clf = LinearSVC(C=1.0, class_weight="balanced", max_iter=10000, dual="auto")
        calibrated_clf = CalibratedClassifierCV(base_clf, cv=3)

        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),  # Unigrams + bigrams
                min_df=2,
                max_df=0.95,
                sublinear_tf=True,
                stop_words="english"
            )),
            ("clf", calibrated_clf)
        ])

        return pipeline

    def train(self, transactions: List[Dict[str, Any]], force: bool = False) -> Dict[str, Any]:
        """
        Train the ML classifier on labeled transaction data.

        Args:
            transactions: List of dicts with "narration" and "category" keys
            force: Retrain even if model exists

        Returns:
            Training metrics
        """
        if self.is_trained and not force:
            logger.info("Model already trained. Use force=True to retrain.")
            return {"status": "already_trained"}

        if len(transactions) < 50:
            logger.warning(f"Only {len(transactions)} samples. Need at least 50 for reliable training.")

        # Preprocess
        X = []
        y = []

        for txn in transactions:
            narration = self._preprocess_text(txn.get("narration", ""))
            category = txn.get("category", "uncategorized")

            if narration and category in self.CATEGORIES:
                X.append(narration)
                y.append(category)

        if len(set(y)) < 2:
            return {
                "status": "failed",
                "error": f"Need at least 2 categories. Found: {set(y)}"
            }

        # Build and train
        self.pipeline = self._build_pipeline()
        self.pipeline.fit(X, y)
        self.is_trained = True

        # Save
        self._save_model()

        # Metrics
        from sklearn.model_selection import cross_val_score
        scores = cross_val_score(self.pipeline, X, y, cv=5, scoring="f1_weighted")

        metrics = {
            "status": "trained",
            "samples": len(X),
            "categories": list(set(y)),
            "cv_f1_score": round(float(scores.mean()), 4),
            "cv_f1_std": round(float(scores.std()), 4),
        }

        logger.info(f"Model trained: {metrics}")
        return metrics

    def predict(self, narration: str) -> Dict[str, Any]:
        """
        Categorize a single transaction.

        Returns:
            {
                "category": str,
                "confidence": float (0-1),
                "method": "rule" | "ml" | "uncategorized",
                "needs_review": bool
            }
        """
        if not narration or not narration.strip():
            return {
                "category": "uncategorized",
                "confidence": 0.0,
                "method": "uncategorized",
                "needs_review": True
            }

        # Step 1: Try rules first (high confidence, deterministic)
        rule_cat, rule_conf = self._apply_rules(narration)
        if rule_cat:
            return {
                "category": rule_cat,
                "confidence": rule_conf,
                "method": "rule",
                "needs_review": False  # Rules are trusted
            }

        # Step 2: ML prediction
        if not self.is_trained:
            return {
                "category": "uncategorized",
                "confidence": 0.0,
                "method": "uncategorized",
                "needs_review": True
            }

        preprocessed = self._preprocess_text(narration)

        # Predict class and probability
        predicted = self.pipeline.predict([preprocessed])[0]
        probabilities = self.pipeline.predict_proba([preprocessed])[0]

        # Get confidence for predicted class
        class_idx = list(self.pipeline.classes_).index(predicted)
        confidence = float(probabilities[class_idx])

        # Flag for review if confidence < 0.9
        needs_review = confidence < 0.9

        return {
            "category": predicted,
            "confidence": round(confidence, 4),
            "method": "ml",
            "needs_review": needs_review,
            "all_probabilities": {
                cls: round(float(prob), 4)
                for cls, prob in zip(self.pipeline.classes_, probabilities)
            }
        }

    def predict_batch(self, narrations: List[str]) -> List[Dict[str, Any]]:
        """Categorize multiple transactions at once"""
        return [self.predict(n) for n in narrations]

    def get_category_distribution(self, transactions: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get distribution of categories in transaction set"""
        dist = {cat: 0 for cat in self.CATEGORIES}
        for txn in transactions:
            cat = txn.get("category", "uncategorized")
            if cat in dist:
                dist[cat] += 1
            else:
                dist["uncategorized"] += 1
        return dist

    def export_training_data(self, transactions: List[Dict[str, Any]], output_path: str):
        """Export labeled transactions for external training or backup"""
        data = []
        for txn in transactions:
            data.append({
                "narration": txn.get("narration", ""),
                "category": txn.get("category", "uncategorized"),
                "amount": txn.get("amount", 0),
                "date": txn.get("date", ""),
                "preprocessed": self._preprocess_text(txn.get("narration", ""))
            })

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Exported {len(data)} training samples to {output_path}")


class TallyExporter:
    """
    Export categorized transactions to Tally-compatible XML format.
    Supports voucher creation with GST and TDS splits.
    """

    LEDGER_MAP = {
        "salary": "Salary A/c",
        "vendor_payment": "Purchase A/c",
        "gst_payment": "GST Output Tax A/c",
        "tds_payment": "TDS Payable A/c",
        "upi_transfer": "UPI Transfer A/c",
        "neft_rtgs": "Bank Transfer A/c",
        "loan_repayment": "Loan Repayment A/c",
        "utility": "Utilities A/c",
        "travel": "Travel Expenses A/c",
        "office_expense": "Office Expenses A/c",
        "interest_income": "Interest Received A/c",
        "bank_charges": "Bank Charges A/c",
        "professional_fees": "Professional Fees A/c",
        "insurance": "Insurance Premium A/c",
        "investment": "Investment A/c",
        "uncategorized": "Suspense A/c"
    }

    def __init__(self, company_name: str = "TaxPilot Client"):
        self.company_name = company_name

    def generate_voucher_xml(self, transactions: List[Dict[str, Any]]) -> str:
        """
        Generate Tally XML for a batch of transactions.
        Each transaction becomes a voucher entry.
        """
        xml_parts = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<ENVELOPE>',
            '  <HEADER>',
            '    <TALLYREQUEST>Import Data</TALLYREQUEST>',
            '  </HEADER>',
            '  <BODY>',
            '    <IMPORTDATA>',
            '      <REQUESTDESC>',
            '        <REPORTNAME>Vouchers</REPORTNAME>',
            '      </REQUESTDESC>',
            '      <REQUESTDATA>'
        ]

        for txn in transactions:
            xml_parts.extend(self._transaction_to_voucher(txn))

        xml_parts.extend([
            '      </REQUESTDATA>',
            '    </IMPORTDATA>',
            '  </BODY>',
            '</ENVELOPE>'
        ])

        return "\n".join(xml_parts)

    def _transaction_to_voucher(self, txn: Dict[str, Any]) -> List[str]:
        """Convert single transaction to Tally voucher XML"""
        category = txn.get("category", "uncategorized")
        ledger = self.LEDGER_MAP.get(category, "Suspense A/c")

        date = txn.get("date")
        if isinstance(date, datetime):
            date_str = date.strftime("%Y%m%d")
        else:
            date_str = str(date or "20240101")

        amount = abs(float(txn.get("amount", 0)))
        txn_type = txn.get("type", "debit")
        narration = txn.get("narration", "")

        # Escape XML special characters
        narration = narration.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        voucher_type = "Payment" if txn_type == "debit" else "Receipt"

        lines = [
            '        <TALLYMESSAGE xmlns:UDF="TallyUDF">',
            '          <VOUCHER VCHTYPE="{}" ACTION="Create">'.format(voucher_type),
            '            <DATE>{}</DATE>'.format(date_str),
            '            <NARRATION>{}</NARRATION>'.format(narration),
            '            <VOUCHERTYPENAME>{}</VOUCHERTYPENAME>'.format(voucher_type),
        ]

        if txn_type == "debit":
            lines.extend([
                '            <ALLLEDGERENTRIES.LIST>',
                '              <LEDGERNAME>{}</LEDGERNAME>'.format(ledger),
                '              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                '              <AMOUNT>-{}</AMOUNT>'.format(amount),
                '            </ALLLEDGERENTRIES.LIST>',
                '            <ALLLEDGERENTRIES.LIST>',
                '              <LEDGERNAME>Bank A/c</LEDGERNAME>',
                '              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                '              <AMOUNT>{}</AMOUNT>'.format(amount),
                '            </ALLLEDGERENTRIES.LIST>'
            ])
        else:
            lines.extend([
                '            <ALLLEDGERENTRIES.LIST>',
                '              <LEDGERNAME>Bank A/c</LEDGERNAME>',
                '              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                '              <AMOUNT>-{}</AMOUNT>'.format(amount),
                '            </ALLLEDGERENTRIES.LIST>',
                '            <ALLLEDGERENTRIES.LIST>',
                '              <LEDGERNAME>{}</LEDGERNAME>'.format(ledger),
                '              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                '              <AMOUNT>{}</AMOUNT>'.format(amount),
                '            </ALLLEDGERENTRIES.LIST>'
            ])

        lines.extend([
            '          </VOUCHER>',
            '        </TALLYMESSAGE>'
        ])

        return lines

    def save_to_file(self, xml_content: str, output_path: str):
        """Save XML to file"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        logger.info(f"Tally XML exported to {output_path}")
