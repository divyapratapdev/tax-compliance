import re

def validate_gstin(gstin: str) -> tuple[bool, str]:
    """Validate GSTIN format and checksum per GSTN specification."""
    if not gstin or not isinstance(gstin, str):
        return False, "GSTIN must be a non-empty string"
    
    gstin = gstin.strip().upper()
    if not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', gstin):
        return False, "Invalid GSTIN format"
    
    try:
        state_code = int(gstin[:2])
    except ValueError:
        return False, "Invalid state code format"
        
    if state_code < 1 or state_code > 38: # 38 is ladakh
        return False, f"Invalid state code: {state_code:02d}"
        
    # Luhn mod-36 checksum
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    total = 0
    for i, c in enumerate(gstin[:-1]):
        try:
            val = chars.index(c)
        except ValueError:
            return False, f"Invalid character in GSTIN: {c}"
        factor = (2 if i % 2 else 1)
        digit = val * factor
        total += (digit // 36) + (digit % 36)
        
    check = (36 - (total % 36)) % 36
    if chars[check] != gstin[-1]:
        return False, f"GSTIN checksum mismatch. Expected {chars[check]}, got {gstin[-1]}"
        
    return True, "Valid"

def validate_pan(pan: str) -> tuple[bool, str]:
    """Validate PAN format: AAAAA9999A"""
    if not pan or not isinstance(pan, str):
        return False, "PAN must be a non-empty string"
        
    pan = pan.strip().upper()
    if not re.match(r'^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$', pan):
        return False, "Invalid PAN format. Must be 5 letters, 4 numbers, 1 letter."
        
    return True, "Valid"

def get_entity_type_from_pan(pan: str) -> str:
    """Extract entity type from the 4th character of PAN."""
    if not pan or len(pan) < 4:
        return "Unknown"
    
    char = pan[3].upper()
    mapping = {
        'C': 'Company',
        'P': 'Individual',
        'H': 'HUF',
        'F': 'Firm',
        'A': 'AOP',
        'T': 'Trust',
        'B': 'BOI',
        'L': 'Local Authority',
        'J': 'Artificial Juridical Person',
        'G': 'Government'
    }
    return mapping.get(char, "Unknown")
