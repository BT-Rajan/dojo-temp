"""Belt keys and names shared by the website blocks (design system: Belt colours)."""

BELTS = {
    "white": ("White", "أبيض"),
    "yellow": ("Yellow", "أصفر"),
    "orange": ("Orange", "برتقالي"),
    "red": ("Red", "أحمر"),
    "purple": ("Purple", "بنفسجي"),
    "blue": ("Blue", "أزرق"),
    "green": ("Green", "أخضر"),
    "brown": ("Brown", "بني"),
    "brownblack": ("Brown / Black stripe", "بني بخط أسود"),
    "black": ("Black", "أسود"),
}
BELT_CHOICES = [(k, v[0]) for k, v in BELTS.items()]

# The Kajukenbo path — the backbone of direction B ("The Path").
KAJUKENBO_PATH = ["white", "yellow", "purple", "blue", "green", "brown", "brownblack", "black"]

STEP_NAMES = {
    "white": ("White belt", "الحزام الأبيض"),
    "yellow": ("Yellow belt", "الحزام الأصفر"),
    "purple": ("Purple belt", "الحزام البنفسجي"),
    "blue": ("Blue belt", "الحزام الأزرق"),
    "green": ("Green belt", "الحزام الأخضر"),
    "brown": ("Brown belt", "الحزام البني"),
    "brownblack": ("Brown / black stripe", "بني بخط أسود"),
    "black": ("Black belt", "الحزام الأسود"),
}

# Page belt markers (brand book: Direction B) — used as defaults for new pages.
PAGE_BELTS = {
    "trial": "white",
    "about": "yellow",
    "programs": "purple",
    "schedule": "purple",
    "branches": "blue",
    "contact": "blue",
    "portal": "green",
    "events": "brown",
    "gallery": "brown",
    "shop": "black",
}


def belt_css_var(key: str) -> str:
    return "--belt-c: var(--belt-" + ("brown" if key == "brownblack" else key) + ")"


def parse_path(value: str) -> list[str]:
    return [k.strip() for k in (value or "").split(",") if k.strip() in BELTS]
