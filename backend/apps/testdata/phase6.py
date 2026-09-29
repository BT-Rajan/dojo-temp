"""
Phase 6 test data (fictional): the test parent (parent@test.elite.local) has renewed one child online, booked a
class from the portal and signed the rules; one wording override; the message log fills itself as the other
phases' data sends messages.

Never loaded in production (seed_kuwait refuses to run there).
"""

from django.contrib.auth import get_user_model

from apps.notifications import services as ns
from apps.notifications.models import FamilyPreference, MessageLog, MessageTemplate
from apps.portal import services as ps
from apps.portal.models import RenewalPayment

TEST_DOMAIN = "test.elite.local"


def reset_phase6():
    for model in (RenewalPayment, MessageLog, FamilyPreference, MessageTemplate):
        model.objects.all().delete()


class Phase6Data:
    def __init__(self, seed):
        self.users = {u.email.split("@")[0]: u for u in get_user_model().objects.filter(email__endswith=TEST_DOMAIN)}

    def load(self):
        parent = self.users.get("parent")
        if parent is None or not ps.family(parent).exists():
            return
        ps.update_email(parent, "parent.test@example.test")
        renewable = next((c for c in ps.family(parent) if ps.renewal_option(c) is not None), None)
        if renewable is not None:
            payment = ps.start_renewal(parent, renewable, "knet")
            ps.complete_renewal(payment, True, "TEST-KNET-SEED")
        for i, child in enumerate(ps.family(parent)):
            bookable = [r for r in ps.upcoming(child) if r["can_book"]]
            if bookable:
                ps.book(parent, child, bookable[0]["s"])
            if i == 0:
                ps.sign_rules(parent, child, ps.signer_name(parent), True)
        ns.save_template(
            self.users["marketing"],
            "order_ready",
            "Good news! Your order {reference} is ready at {branch}. See you soon. — Elite Academy",
            "خبر سار! طلبك {reference} جاهز في {branch}. نراك قريباً. — أكاديمية إيليت",
        )
