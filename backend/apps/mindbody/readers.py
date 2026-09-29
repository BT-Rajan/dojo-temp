"""
Reading Mindbody exports. Mindbody gives CSV, real Excel files, and ".xls" files that are really HTML
tables (as seen in Elite's inventory exports). All three are read into rows of text; the header row is
found by recognising column names, so report titles above the table are skipped.
"""

import csv
import datetime
import io
import re
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Canonical field → header names Mindbody uses (normalised: lower case, single spaces, no punctuation).
ALIASES = {
    "clients": {
        "id": ["id", "client id", "clientid", "client number", "mbo id"],
        "first_name": ["first name", "firstname", "first"],
        "last_name": ["last name", "lastname", "last"],
        "name": ["client", "client name", "name", "full name"],
        "mobile": ["mobile phone", "cell phone", "mobile", "cell", "mobile number", "phone", "home phone"],
        "email": ["email", "email address", "e mail"],
        "birth": ["birth date", "birthdate", "date of birth", "dob", "birthday"],
        "gender": ["gender", "sex"],
        "location": ["home location", "location", "home studio", "site"],
        "created": ["creation date", "date created", "member since", "first visit"],
        "emergency_name": ["emergency contact name", "emergency contact"],
        "emergency_phone": ["emergency contact phone", "emergency phone", "emergency contact number"],
        "emergency_relationship": ["emergency contact relationship", "emergency relationship"],
    },
    "relationships": {
        "client_id": ["client id", "clientid", "id"],
        "related_id": ["related client id", "relationship client id", "related id", "related client"],
        "relationship": ["relationship", "relationship name", "relation"],
    },
    "memberships": {
        "client_id": ["client id", "clientid", "id"],
        "option": ["pricing option", "pricing option name", "series", "service", "item"],
        "client": ["client", "client name", "name"],
        "location": ["location", "site", "purchase location"],
        "start": ["activation date", "active date", "start date", "purchase date", "sale date", "date purchased"],
        "end": ["expiration date", "expiration", "expires", "exp date", "expiry date"],
        "remaining": ["remaining", "remaining count", "sessions remaining", "remaining visits"],
        "paid": ["amount paid", "paid", "price", "total"],
    },
    "visits": {
        "client_id": ["client id", "clientid", "id"],
        "client": ["client", "client name", "name"],
        "date": ["visit date", "date", "class date"],
        "time": ["time", "start time", "class time", "visit time"],
        "class": ["class", "class name", "service", "visit type", "description", "class appointment"],
        "location": ["location", "site"],
        "staff": ["staff", "teacher", "instructor", "staff name"],
    },
    "sales": {
        "sale_id": ["sale id", "saleid", "sale", "receipt", "receipt number", "sale number"],
        "date": ["sale date", "date", "purchase date"],
        "client_id": ["client id", "clientid", "id"],
        "client": ["client", "client name", "name"],
        "item": ["item name", "item", "description", "product", "service"],
        "location": ["location", "site"],
        "quantity": ["quantity", "qty"],
        "amount": ["item total", "total", "amount", "line total", "total paid", "item price", "price"],
        "method": ["payment method", "method", "payment type", "paid by", "payment"],
    },
    "inventory": {
        "barcode": ["barcode", "sku"],
        "product": ["product name", "product", "item", "name"],
        "supplier": ["supplier", "vendor"],
        "colour": ["color", "colour"],
        "size": ["size"],
        "location": ["location"],
        "quantity": ["in stock", "quantity", "on hand", "qty"],
        "cost": ["our cost", "cost", "unit cost"],
        "price": ["retail price", "price", "sell price"],
        "reorder": ["reorder level", "reorder"],
        "max": ["max level", "maximum"],
    },
}
REQUIRED = {
    "clients": [("id", "name", "first_name")],
    "relationships": [("client_id",), ("related_id",)],
    "memberships": [("option",), ("end",), ("client_id", "client")],
    "visits": [("date",), ("client_id", "client")],
    "sales": [("date",), ("item",), ("amount",)],
    "inventory": [("product",), ("quantity",)],
}


def norm(text) -> str:
    text = str(text or "").strip().lower().replace("_", " ")
    text = re.sub(r"[#:.*()/\\-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.row, self.cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.row is not None:
            self.row.append((self.cell or "").strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data


def raw_rows(content: bytes) -> list[list]:
    if content[:2] == b"PK":
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        return [["" if v is None else v for v in row] for row in ws.iter_rows(values_only=True)]
    if content[:8] == bytes.fromhex("D0CF11E0A1B11AE1"):
        import xlrd

        sheet = xlrd.open_workbook(file_contents=content).sheet_by_index(0)
        return [sheet.row_values(i) for i in range(sheet.nrows)]
    text = None
    for enc in ("utf-8-sig", "cp1256", "latin-1"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if "<table" in text[:5000].lower() or "<tr" in text[:5000].lower():
        parser = _Tables()
        parser.feed(text)
        return parser.rows
    return list(csv.reader(io.StringIO(text), delimiter=_delimiter(text)))


def _delimiter(text: str) -> str:
    """The separator used most on the busiest lines (report titles above the table have none)."""
    lines = [ln for ln in text.splitlines()[:50] if ln.strip()]
    best, score = ",", 0
    for sep in (",", ";", "\t"):
        top = max((ln.count(sep) for ln in lines), default=0)
        if top > score:
            best, score = sep, top
    return best


def table(content: bytes, kind: str):
    """Returns (rows as dicts of canonical fields, header mapping, unknown headers). Raises ValueError."""
    aliases = ALIASES[kind]
    lookup = {}
    for field, names in aliases.items():
        for name in names:
            lookup.setdefault(name, field)
    rows = raw_rows(content)
    for index, row in enumerate(rows[:40]):
        mapping, unknown = {}, []
        for col, header in enumerate(row):
            field = lookup.get(norm(header))
            if field and field not in mapping.values():
                mapping[col] = field
            elif norm(header):
                unknown.append(str(header))
        found = set(mapping.values())
        if all(any(f in found for f in group) for group in REQUIRED[kind]):
            out = []
            for n, data in enumerate(rows[index + 1 :], start=index + 2):
                if not any(str(c).strip() for c in data):
                    continue
                record = {"_row": n}
                for col, field in mapping.items():
                    record[field] = data[col] if col < len(data) else ""
                out.append(record)
            return out, mapping, unknown
    wanted = ", ".join(" or ".join(aliases[f][0] for f in group) for group in REQUIRED[kind])
    raise ValueError(f"Couldn't find the column headings. This file needs: {wanted}.")


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------
def text(value) -> str:
    return str(value).strip() if value is not None else ""


def number(value):
    if value in (None, ""):
        return None
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value))
    cleaned = str(value).translate(ARABIC_DIGITS)
    cleaned = re.sub(r"[^\d.\-]", "", cleaned.replace("(", "-"))
    try:
        return Decimal(cleaned) if cleaned not in ("", "-", ".") else None
    except InvalidOperation:
        return None


def integer(value):
    n = number(value)
    return int(n) if n is not None else None


_DATE_FORMATS = {"dmy": ["%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d.%m.%Y"], "mdy": ["%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y"]}


def date_order(values) -> str:
    """Kuwait exports are day/month/year; month/day/year is recognised when a middle part is above 12."""
    for v in values:
        m = re.match(r"\s*(\d{1,2})[/\-.](\d{1,2})[/\-.]\d{2,4}", str(v or ""))
        if m:
            first, second = int(m.group(1)), int(m.group(2))
            if first > 12:
                return "dmy"
            if second > 12:
                return "mdy"
    return "dmy"


def date(value, order="dmy"):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    raw = str(value).strip().translate(ARABIC_DIGITS)
    part = raw.split(" ")[0].split("T")[0]
    for fmt in ["%Y-%m-%d", *_DATE_FORMATS[order]]:
        try:
            return datetime.datetime.strptime(part, fmt).date()
        except ValueError:
            continue
    return None


def time(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value.time().replace(second=0, microsecond=0)
    if isinstance(value, datetime.time):
        return value
    raw = str(value).strip().upper().replace(".", ":")
    m = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)?", raw)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if m.group(3) == "PM" and hour < 12:
        hour += 12
    if m.group(3) == "AM" and hour == 12:
        hour = 0
    return datetime.time(hour % 24, minute)


def split_name(value):
    """'Al-Test, Salem' → ('Salem', 'Al-Test'); 'Salem Al-Test' → ('Salem', 'Al-Test')."""
    value = text(value)
    if "," in value:
        last, first = [p.strip() for p in value.split(",", 1)]
        return first, last
    parts = value.split()
    return (parts[0], " ".join(parts[1:])) if len(parts) > 1 else (value, "")
