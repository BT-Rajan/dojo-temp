"""
Fictional, Kuwait-realistic data building blocks (EA-SYS-SCOPE-01 M21).
No real person's data is used. Civil IDs are structurally valid but randomly generated.
"""

import datetime
import random

from apps.core.validators import civil_id_check_digit

MALE_NAMES = [
    ("Abdullah", "عبدالله"),
    ("Mohammed", "محمد"),
    ("Fahad", "فهد"),
    ("Yousef", "يوسف"),
    ("Hamad", "حمد"),
    ("Khaled", "خالد"),
    ("Omar", "عمر"),
    ("Ali", "علي"),
    ("Saud", "سعود"),
    ("Bader", "بدر"),
    ("Mishari", "مشاري"),
    ("Faisal", "فيصل"),
    ("Jassim", "جاسم"),
    ("Sulaiman", "سليمان"),
    ("Abdulaziz", "عبدالعزيز"),
    ("Hamza", "حمزة"),
    ("Salem", "سالم"),
    ("Nawaf", "نواف"),
    ("Talal", "طلال"),
    ("Rashed", "راشد"),
    ("Ahmad", "أحمد"),
    ("Hussain", "حسين"),
    ("Zaid", "زيد"),
    ("Adam", "آدم"),
]
FEMALE_NAMES = [
    ("Fatma", "فاطمة"),
    ("Noura", "نورة"),
    ("Sara", "سارة"),
    ("Maryam", "مريم"),
    ("Dana", "دانة"),
    ("Shaikha", "شيخة"),
    ("Hessa", "حصة"),
    ("Lulwa", "لولوة"),
    ("Reem", "ريم"),
    ("Aisha", "عائشة"),
    ("Fajer", "فجر"),
    ("Salma", "سلمى"),
    ("Ghala", "غلا"),
    ("Jana", "جنى"),
    ("Layan", "ليان"),
    ("Hala", "هلا"),
    ("Mariam", "مريم"),
    ("Lina", "لينا"),
]
FAMILY_NAMES = [
    ("Al-Mutairi", "المطيري"),
    ("Al-Ajmi", "العجمي"),
    ("Al-Enezi", "العنزي"),
    ("Al-Rashidi", "الرشيدي"),
    ("Al-Shammari", "الشمري"),
    ("Al-Kandari", "الكندري"),
    ("Al-Awadhi", "العوضي"),
    ("Al-Hajri", "الهاجري"),
    ("Al-Qattan", "القطان"),
    ("Al-Sabbagh", "الصباغ"),
    ("Al-Saleh", "الصالح"),
    ("Al-Sarawi", "الصراوي"),
    ("Al-Mudhaf", "المضف"),
    ("Al-Ghanim", "الغانم"),
    ("Behbehani", "بهبهاني"),
    ("Al-Failakawi", "الفيلكاوي"),
    ("Haddad", "حداد"),
    ("Khalil", "خليل"),
    ("Mansour", "منصور"),
    ("Hassan", "حسن"),
]
EXPAT_FAMILIES = [
    (("Thomas", "توماس"), ("Wilson", "ويلسون"), "British"),
    (("Rahul", "راهول"), ("Nair", "ناير"), "Indian"),
    (("Daniel", "دانيال"), ("Carter", "كارتر"), "American"),
    (("Karim", "كريم"), ("Mansour", "منصور"), "Lebanese"),
]
NATIONALITY_WEIGHTS = [("Kuwaiti", 70), ("Egyptian", 8), ("Syrian", 6), ("Jordanian", 6), ("Lebanese", 5), ("Saudi", 5)]

AREAS_BY_BRANCH = {
    "PRM": ["Hawalli", "Salmiya", "Jabriya", "Rumaithiya", "Mishref", "Bayan", "Salwa", "Surra"],
    "BED": [
        "Sabah Al Salem",
        "Messila",
        "Adan",
        "Qurain",
        "Qusour",
        "Mubarak Al-Kabeer",
        "Fnaitees",
        "Abu Al Hasaniya",
    ],
}


def weighted(rng: random.Random, pairs):
    values, weights = zip(*pairs, strict=True)
    return rng.choices(values, weights=weights, k=1)[0]


def make_civil_id(rng: random.Random, dob: datetime.date, used: set[str]) -> str:
    century = "2" if dob.year < 2000 else "3"
    prefix = f"{century}{dob:%y%m%d}"
    for _ in range(500):
        first_eleven = prefix + f"{rng.randint(0, 9999):04d}"
        check = civil_id_check_digit(first_eleven)
        if check is None:
            continue
        cid = first_eleven + str(check)
        if cid not in used:
            used.add(cid)
            return cid
    raise RuntimeError("Could not generate a unique Civil ID")


def make_mobile(rng: random.Random, used: set[str]) -> str:
    while True:
        number = "+965" + rng.choice("569") + f"{rng.randint(0, 9999999):07d}"
        if number not in used:
            used.add(number)
            return number


def birth_date(rng: random.Random, age: int, today: datetime.date) -> datetime.date:
    try:
        start = today.replace(year=today.year - age - 1)
    except ValueError:  # 29 February
        start = today.replace(year=today.year - age - 1, day=28)
    start += datetime.timedelta(days=1)
    return start + datetime.timedelta(days=rng.randint(0, 364))
