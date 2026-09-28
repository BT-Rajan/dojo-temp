"""Kuwait-specific validation: Civil ID and mobile numbers."""

import datetime
import re

from django.core.exceptions import ValidationError

CIVIL_ID_WEIGHTS = (2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
MOBILE_RE = re.compile(r"^(?:\+965|00965)?([4569]\d{7})$")


def civil_id_check_digit(first_eleven: str) -> int | None:
    total = sum(int(d) * w for d, w in zip(first_eleven, CIVIL_ID_WEIGHTS, strict=True))
    check = 11 - (total % 11)
    return check if check <= 9 else None


def civil_id_birth_date(civil_id: str) -> datetime.date | None:
    century = {"2": 1900, "3": 2000}.get(civil_id[0])
    if century is None:
        return None
    try:
        return datetime.date(century + int(civil_id[1:3]), int(civil_id[3:5]), int(civil_id[5:7]))
    except ValueError:
        return None


def validate_civil_id(value: str) -> None:
    """
    Kuwait Civil ID: 12 digits = century (2=1900s, 3=2000s) + YYMMDD + 4-digit serial + check digit.
    """
    if not re.fullmatch(r"\d{12}", value or ""):
        raise ValidationError("Civil ID must be exactly 12 digits.", code="civil_id_format")
    if civil_id_birth_date(value) is None:
        raise ValidationError("Civil ID does not contain a valid date of birth.", code="civil_id_date")
    if civil_id_check_digit(value[:11]) != int(value[11]):
        raise ValidationError("Civil ID check digit is not valid.", code="civil_id_checksum")


def normalize_kuwait_mobile(value: str) -> str:
    """Return the number as +965XXXXXXXX or raise ValidationError."""
    # Parents on Arabic keyboards type Arabic-Indic digits; accept them.
    compact = re.sub(r"[\s\-()]", "", (value or "").translate(ARABIC_DIGITS))
    match = MOBILE_RE.match(compact)
    if not match:
        raise ValidationError("Enter a Kuwait mobile number: 8 digits starting with 4, 5, 6 or 9.", code="mobile")
    return "+965" + match.group(1)


def validate_kuwait_mobile(value: str) -> None:
    normalize_kuwait_mobile(value)
