"""Values every website template needs: language, direction, menu, key pages, cart size.

Everything that queries the database is lazy, so a template that doesn't use it costs nothing.
"""

from django.utils.functional import SimpleLazyObject
from django.utils.translation import get_language

SKIP_PREFIXES = ("/cms/", "/api/", "/static/", "/media/")

# slug of a page directly under Home -> name the templates use (key.trial_page …)
KEY_PAGES = {
    "book-a-trial": "trial_page",
    "schedule": "schedule_page",
    "programs": "programs_page",
    "branches": "branches_page",
    "events": "events_page",
    "gallery": "gallery_page",
    "shop": "shop_page",
    "about": "about_page",
    "contact": "contact_page",
    "portal": "portal_page",
}


def site(request):
    if request.path.startswith(SKIP_PREFIXES):
        return {}
    from .models import HomePage

    lang = "ar" if get_language() == "ar" else "en"
    home = SimpleLazyObject(lambda: HomePage.objects.live().first())

    def key_pages():
        if not home:
            return {}
        pages = home.get_children().live().filter(slug__in=KEY_PAGES).specific()
        return {KEY_PAGES[p.slug]: p for p in pages}

    def menu():
        if not home:
            return []
        return list(home.get_children().live().in_menu().public().specific())

    def branch_pages():
        from .models import BranchPage

        return sorted(
            BranchPage.objects.live().public().select_related("branch"),
            key=lambda b: 0 if b.branch.code == "PRM" else 1,
        )

    def cart_size():
        from .shop_views import cart_count

        return cart_count(request)

    return {
        "lang": lang,
        "dir": "rtl" if lang == "ar" else "ltr",
        "other_lang": "en" if lang == "ar" else "ar",
        "home_page": home,
        "menu_pages": SimpleLazyObject(menu),
        "key": SimpleLazyObject(key_pages),
        "cart_size": SimpleLazyObject(cart_size),
        "branch_pages": SimpleLazyObject(branch_pages),
    }
