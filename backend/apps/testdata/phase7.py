"""
Phase 7 test data (fictional): reporting lines for the test staff (with one dual line, like the operations-support
coach in the Communication Procedure), a CEO announcement part-way through its cascade, handoffs between leads and an
IT request, last month's leads meeting with action items, monthly lead reports, two escalations, the procedure
library with read confirmations, and a draft Quarterly Business Report for the last finished quarter.

Never loaded in production (seed_kuwait refuses to run there).
"""

import datetime

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.management import quarterly as qbr
from apps.management import services as ms
from apps.management.models import (
    ActionItem,
    AgendaItem,
    Announcement,
    Decision,
    Escalation,
    EscalationNote,
    Handoff,
    LeadReport,
    Meeting,
    MeetingAttendee,
    Procedure,
    ProcedureVersion,
    QuarterlyReport,
    ReadConfirmation,
    Recipient,
)
from apps.staff.models import StaffProfile

TEST_DOMAIN = "test.elite.local"

# person → (lead, second lead)
LINES = {
    "ops": ("ceo", None),
    "training": ("ceo", None),
    "marketing": ("ceo", None),
    "it": ("ceo", None),
    "accounts": ("ceo", None),
    "grappling": ("training", None),
    "striking": ("training", None),
    "coach.prm": ("training", None),
    "coach.bed1": ("training", None),
    "coach.bed2": ("training", None),
    "coach.free": ("training", None),
    "support": ("ops", "training"),  # operations support who also coaches
    "admin.prm": ("support", None),
    "admin.bed": ("support", None),
    "purchasing": ("ops", None),
    "content": ("marketing", None),
}

# code, title, title_ar, kind, owner, version, effective, audience
LIBRARY = [
    ("EA-COMM-PROC-01", "Communication Procedure", "إجراء التواصل", "procedure", "ops", "2.3", (2026, 9, 13), []),
    (
        "EA-COMM-REF-01",
        "Organization Chart & Communication Channels",
        "الهيكل التنظيمي وقنوات التواصل",
        "reference",
        "ops",
        "1.2",
        (2026, 9, 13),
        [],
    ),
    (
        "EA-COMM-PLAY-01",
        "How We Work Together Playbook",
        "دليل كيف نعمل معاً",
        "reference",
        "ops",
        "3.2",
        (2026, 9, 1),
        [],
    ),
    (
        "EA-OPS-PROC-01",
        "Operations Procedure",
        "إجراء العمليات",
        "procedure",
        "ops",
        "1.0",
        (2026, 9, 20),
        ["operations_manager", "branch_admin", "operations_support", "purchasing_coordinator"],
    ),
    (
        "EA-OPS-FRM-09",
        "Incident Report",
        "تقرير الحادثة",
        "form",
        "ops",
        "1.0",
        (2026, 9, 20),
        [],
    ),
    (
        "EA-SYS-POL-01",
        "Acceptable Use and Access Policy",
        "سياسة الاستخدام والصلاحيات",
        "policy",
        "it",
        "1.0",
        (2026, 9, 25),
        [],
    ),
]


def reset_phase7():
    for model in (
        ReadConfirmation,
        ProcedureVersion,
        Procedure,
        EscalationNote,
        Escalation,
        QuarterlyReport,
        LeadReport,
        ActionItem,
        Decision,
        AgendaItem,
        MeetingAttendee,
        Meeting,
        Handoff,
        Recipient,
    ):
        model.objects.all().delete()
    Announcement.objects.filter(root__isnull=False).delete()
    Announcement.objects.all().delete()
    StaffProfile.objects.update(reports_to=None, second_lead=None)


class Phase7Data:
    def __init__(self, seed):
        self.today = timezone.localdate()
        self.users = {u.email.split("@")[0]: u for u in get_user_model().objects.filter(email__endswith=TEST_DOMAIN)}

    def u(self, key):
        return self.users[key]

    def load(self):
        if "ceo" not in self.users or "ops" not in self.users:
            return
        self._lines()
        self._announcement()
        self._handoffs()
        self._meeting()
        self._lead_reports()
        self._escalations()
        self._library()
        self._quarterly()

    def _lines(self):
        profiles = {p.user.email.split("@")[0]: p for p in StaffProfile.objects.select_related("user")}
        for who, (lead, second) in LINES.items():
            p = profiles.get(who)
            if p is None:
                continue
            p.reports_to = profiles.get(lead)
            p.second_lead = profiles.get(second) if second else None
            p.save(update_fields=["reports_to", "second_lead"])

    def _announcement(self):
        leads = [self.u(k) for k in ("ops", "training", "marketing", "it")]
        post = ms.post_announcement(
            self.u("ceo"),
            "Ramadan timetable from next month",
            "Classes move to evening slots during Ramadan. Each branch keeps its usual days; the new times will be on "
            "the website and in the desk two weeks before. Leads: brief your teams and confirm back.",
            leads,
        )
        for key in ("ops", "training"):
            ms.confirm_receipt(self.u(key), post)
        ms.forward(self.u("ops"), post)  # the OM forwards unchanged; the support coach's second lead gets a copy
        fwd = Announcement.objects.get(root=post, sender=self.u("ops"))
        ms.confirm_receipt(self.u("purchasing"), fwd)

    def _handoffs(self):
        h = ms.send_handoff(
            self.u("marketing"),
            kind="leads",
            receiver=self.u("ops"),
            subject="Back-to-school campaign leads",
            detail="23 enquiries from the back-to-school campaign are in the leads list; please make sure each is "
            "contacted within a day.",
        )
        ms.confirm_handoff(self.u("ops"), h, note="All logged; admins calling today.")
        ms.send_handoff(
            self.u("training"),
            kind="stories",
            receiver=self.u("marketing"),
            subject="Progress stories from the September test day",
            detail="Three students (families agreed to photos) earned their next belt. Notes and photos attached in "
            "the gallery.",
        )
        it = ms.send_handoff(
            self.u("ops"),
            kind="it_request",
            subject="Tablet for the Bedaya front desk check-in",
            detail="The Bedaya desk needs a second tablet for check-in at peak times.",
            why="Queues at 5 pm when three classes start together.",
            benefits="Bedaya front desk and parents",
            urgency="high",
        )
        ms.confirm_handoff(self.u("it"), it, committed_date=self.today + datetime.timedelta(days=10))
        ms.send_handoff(
            self.u("admin.prm"),
            kind="it_request",
            subject="Receipt printer paper size",
            detail="Printed receipts are cut off on the right.",
            why="Members can't read the totals.",
            urgency="normal",
        )

    def _meeting(self):
        date = self.today.replace(day=1) - datetime.timedelta(days=3)
        m = ms.create_meeting(self.u("ops"), date, datetime.time(10, 0), "Promenade office")
        staff = {u.pk for u in ms.default_attendees()} - {self.u("it").pk}
        ms.save_minutes(
            self.u("ops"),
            m,
            present_ids=staff,
            agenda=[
                ("Month in review", "Sales up on last month; Bedaya ladies' class full on Mondays.", self.u("ops")),
                (
                    "Test day results",
                    "31 candidates, 28 promoted. Belts handed over at both branches.",
                    self.u("training"),
                ),
                ("Back-to-school campaign", "Leads above target; conversion still being tracked.", self.u("marketing")),
            ],
            decisions=[
                ("Open a second ladies' class at Bedaya on Wednesdays.", self.u("ops")),
                ("Share test-day stories within a week of each test day.", self.u("training")),
            ],
            actions=[
                ("Draft the Wednesday ladies' class timetable", self.u("ops"), self.today + datetime.timedelta(days=7)),
                (
                    "Send three progress stories to Marketing",
                    self.u("training"),
                    self.today - datetime.timedelta(days=2),
                ),
                ("Report conversion from the campaign", self.u("marketing"), self.today + datetime.timedelta(days=14)),
            ],
            next_date=date + datetime.timedelta(days=30),
            next_time=datetime.time(10, 0),
            next_location="Promenade office",
        )
        ms.publish_meeting(self.u("ops"), m)
        for key in ("ceo", "training"):
            ms.acknowledge_minutes(self.u(key), m)

    def _lead_reports(self):
        last = ms.previous_month(self.today)
        ops = ms.save_lead_report(
            self.u("ops"),
            last,
            "Steady month: renewals held and the campaign brought more trials than last month.",
            "Bedaya needs a second check-in tablet (IT request logged).",
        )
        ms.submit_lead_report(self.u("ops"), ops)
        ms.acknowledge_lead_report(self.u("ceo"), ops, "Thanks — keep an eye on the Bedaya queues.")
        tr = ms.save_lead_report(
            self.u("training"),
            last,
            "Test day went well; evaluations on schedule.",
            "Two coaches need first-aid renewal.",
        )
        ms.submit_lead_report(self.u("training"), tr)
        ms.save_lead_report(self.u("marketing"), last, "Draft — campaign figures still coming in.")

    def _escalations(self):
        from apps.organization.models import Branch

        bed = Branch.objects.filter(code="BED").first()
        e = ms.raise_escalation(
            self.u("coach.bed1"),
            kind="conduct",
            description="A parent shouted at another child during the Tuesday junior class. The class was paused and "
            "the parent asked to wait outside.",
            branch=bed,
        )
        ms.name_owner(self.u("training"), e, self.u("support"))
        ms.add_note(self.u("support"), e, "Spoke to the parent; apology given to the other family.")
        s = ms.raise_escalation(
            self.u("admin.prm"),
            kind="safety",
            description="A mat section at Promenade has lifted at the edge; a child tripped (no injury).",
            needs_ceo=True,
            branch=Branch.objects.filter(code="PRM").first(),
        )
        ms.name_owner(self.u("support"), s, self.u("ops"))
        ms.inform_ceo(self.u("ops"), s, "Mat taped off; replacement ordered.")

    def _library(self):
        for code, title, title_ar, kind, owner, version, eff, audience in LIBRARY:
            p = ms.save_procedure(
                self.u("ops"), code=code, title=title, title_ar=title_ar, kind=kind, owner=self.u(owner),
                audience=audience,
            )  # fmt: skip
            v = ms.add_version(
                self.u("ops") if owner == "ops" else self.u("it"),
                p,
                version=version,
                effective_date=datetime.date(*eff),
                changes="First version in the system.",
            )
            ms.approve_version(self.u("ceo"), v)
        comm = Procedure.objects.get(code="EA-COMM-PROC-01").current
        for key in ("ops", "training", "marketing", "admin.prm", "support"):
            ms.confirm_read(self.u(key), comm)
        ops_proc = Procedure.objects.get(code="EA-OPS-PROC-01")
        ms.add_version(
            self.u("ops"),
            ops_proc,
            version="1.1",
            effective_date=self.today + datetime.timedelta(days=7),
            changes="Cash-up now done in the desk; Mindbody steps removed from the guides.",
        )

    def _quarterly(self):
        report = qbr.open_report(self.u("ops"), qbr.last_finished_quarter(self.today))
        qbr.save_text(
            self.u("ops"),
            report,
            summary="A good quarter at both branches: summer camps filled early, and the back-to-school campaign "
            "started strongly. Ramadan planning begins next quarter.",
            strategy="Evening Ramadan timetable, a second ladies' class at Bedaya, the winter camp, and going live "
            "with the new system after the parallel run.",
            comments={"5": "Bedaya evenings are near capacity; Promenade mornings have room."},
        )
