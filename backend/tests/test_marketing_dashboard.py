"""The Marketing dashboard counts leads from every source (walk-in, phone, website, SAQR…), not only website forms."""

import datetime

from django.utils import timezone

from apps.leads import services as ls
from apps.reports.services import marketing_dashboard


def test_all_sources_are_counted_with_labels(branches, make_user):
    prm = branches["PRM"]
    desk = make_user("branch_admin", branch=prm)
    for i, source in enumerate(["walk_in", "phone", "website", "saqr", "whatsapp"]):
        ls.intake(name=f"Lead {i}", mobile=f"+9655000{i:04d}", branch=prm, source=source, user=desk)
    today = timezone.localdate()
    data = marketing_dashboard([prm], today - datetime.timedelta(days=27), today, "ar")
    assert data["leads"] == 5 and data["funnel"]["total"] == 5
    labels = {r["label"] for r in data["by_source"]}
    assert "زيارة مباشرة" in labels and "محادثة صقر" in labels
    en = marketing_dashboard([prm], today - datetime.timedelta(days=27), today, "en")
    assert {r["label"] for r in en["by_source"]} >= {"Walk-in", "Phone", "Website trial form"}
