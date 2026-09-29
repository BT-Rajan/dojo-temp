"""
M12 rules (decisions P7-1 to P7-10). Every function takes the acting user and raises ValidationError or
PermissionDenied; the desk shows those as messages. Staff alerts go by WhatsApp (category "staff") and are logged.

The reporting lines come from the staff records: StaffProfile.reports_to (the lead) and StaffProfile.second_lead
(a dotted line, e.g. operations staff who also coach under the Training Lead — EA-COMM-PROC-01 §5.3).
"""

import datetime
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.messaging import send_message
from apps.rbac.models import RoleAssignment
from apps.rbac.services import has_perm, users_with_perm

from .models import (
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
    ReadConfirmation,
    Recipient,
)

WEEKEND = {4, 5}  # Friday and Saturday (P7-2)
CASCADE_DAYS = 2  # EA-COMM-PROC-01 §4.2
HANDOFF_DAYS = 1  # P7-4
LEAD_REPORT_DUE_DAY = 5  # P7-6: by the 5th of the next month

FUNCTION_ROLES = {
    "training_lead": LeadReport.Function.TRAINING,
    "operations_manager": LeadReport.Function.OPERATIONS,
    "marketing_lead": LeadReport.Function.MARKETING,
    "it_admin": LeadReport.Function.IT,
}


def _need(user, perm, message=""):
    if not has_perm(user, perm):
        raise PermissionDenied(message)


def add_working_days(day: datetime.date, n: int) -> datetime.date:
    while n > 0:
        day += datetime.timedelta(days=1)
        if day.weekday() not in WEEKEND:
            n -= 1
    return day


def _tell(users, text):
    """WhatsApp to staff (logged as category 'staff'), after the change is saved."""
    mobiles = [u.mobile for u in users if u is not None and getattr(u, "mobile", "")]
    if mobiles:
        transaction.on_commit(lambda: [send_message(m, text, category="staff", kind="management") for m in mobiles])


def _next_ref(model, prefix):
    last = model.objects.select_for_update().filter(reference__startswith=prefix).order_by("-reference").first()
    n = int(last.reference.rsplit("-", 1)[1]) + 1 if last else 1
    return f"{prefix}{n:04d}"


# ---------------------------------------------------------------------------
# Reporting lines, the org chart and the directory
# ---------------------------------------------------------------------------
def staff_users():
    """Everyone who works at Elite (anyone holding the management screens), active."""
    return users_with_perm("mgmt.use").order_by("full_name")


def ceo_users():
    ids = RoleAssignment.objects.current().filter(role__code="ceo").values("user_id")
    return list(get_user_model().objects.filter(pk__in=ids, is_active=True))


def is_ceo(user) -> bool:
    return RoleAssignment.objects.current().filter(user=user, role__code="ceo").exists()


def _profile(user):
    return getattr(user, "staff_profile", None)


def leads_of(user) -> list:
    """The person's lead, then their second (dotted-line) lead."""
    p = _profile(user)
    if p is None:
        return []
    out = []
    for lead in (p.reports_to, p.second_lead):
        if lead is not None and lead.user.is_active and lead.user not in out:
            out.append(lead.user)
    return out


def team_of(user) -> list:
    """Direct reports and dotted-line reports."""
    from apps.staff.models import StaffProfile

    p = _profile(user)
    if p is None:
        return []
    qs = StaffProfile.objects.filter(Q(reports_to=p) | Q(second_lead=p), user__is_active=True).select_related("user")
    return sorted({sp.user for sp in qs}, key=lambda u: u.full_name)


@transaction.atomic
def set_reporting_line(user, staff, lead, second=None):
    """Sets who a staff member reports to (and a dotted-line second lead); no one can end up above themselves."""
    _need(user, "staff.manage", "Only staff managers change reporting lines.")
    for other in (lead, second):
        node, seen = other, set()
        while node is not None and node.pk not in seen:
            if node.pk == staff.pk:
                raise ValidationError("That would make someone report to themselves through the chain.")
            seen.add(node.pk)
            node = node.reports_to
    if second is not None and lead is not None and second.pk == lead.pk:
        second = None
    staff.reports_to, staff.second_lead, staff.updated_by = lead, second, user
    staff.save(update_fields=["reports_to", "second_lead", "updated_by", "updated_at"])
    record_event(action="reporting_line_changed", instance=staff)
    return staff


def role_codes(user) -> set[str]:
    return set(RoleAssignment.objects.current().filter(user=user).values_list("role__code", flat=True))


def function_of(user):
    for code in role_codes(user):
        if code in FUNCTION_ROLES:
            return FUNCTION_ROLES[code]
    return None


def directory(q=""):
    from apps.staff.models import StaffProfile

    qs = StaffProfile.objects.filter(user__is_active=True).select_related(
        "user", "primary_branch", "reports_to__user", "second_lead__user"
    )
    if q:
        qs = qs.filter(Q(user__full_name__icontains=q) | Q(user__full_name_ar__icontains=q) | Q(job_title__icontains=q))
    roles = defaultdict(list)
    for a in RoleAssignment.objects.current().select_related("role", "branch"):
        roles[a.user_id].append(a.role.name + (f" ({a.branch.code})" if a.branch_id else ""))
    return [{"p": p, "roles": sorted(set(roles[p.user_id]))} for p in qs.order_by("user__full_name")]


def org_chart():
    """Nested levels from the people who report to no one, following reports_to; dotted lines are listed."""
    from apps.staff.models import StaffProfile

    people = list(
        StaffProfile.objects.filter(user__is_active=True).select_related("user", "primary_branch", "second_lead__user")
    )
    children = defaultdict(list)
    for p in people:
        children[p.reports_to_id].append(p)

    def node(p, depth=0):
        return {
            "p": p,
            "depth": depth,
            "team": [node(c, depth + 1) for c in sorted(children[p.pk], key=lambda x: x.user.full_name)]
            if depth < 8
            else [],
        }

    roots = [p for p in people if p.reports_to_id is None or p.reports_to_id not in {x.pk for x in people}]
    order = {"ceo": 0}
    roots.sort(key=lambda p: (order.get(next(iter(role_codes(p.user)), ""), 1), p.user.full_name))
    dotted = [p for p in people if p.second_lead_id]
    return {"roots": [node(p) for p in roots], "dotted": dotted}


# ---------------------------------------------------------------------------
# Announcements and the cascade (EA-COMM-PROC-01 §4, §5.3)
# ---------------------------------------------------------------------------
def _add_recipients(post, users, sender):
    tree_users = set(
        Recipient.objects.filter(Q(announcement=post.original) | Q(announcement__root=post.original)).values_list(
            "user_id", flat=True
        )
    ) | {post.original.sender_id}
    added = []
    for u in users:
        if u.pk in tree_users or u.pk == sender.pk:
            continue
        Recipient.objects.create(announcement=post, user=u)
        tree_users.add(u.pk)
        added.append(u)
    # The other lead of anyone with two lines sees the instruction too (§5.3).
    copies = []
    for u in added:
        for lead in leads_of(u):
            if lead.pk not in tree_users and lead.pk != sender.pk:
                Recipient.objects.create(announcement=post, user=lead, is_copy=True)
                tree_users.add(lead.pk)
                copies.append(lead)
    return added, copies


@transaction.atomic
def post_announcement(user, title, body, recipients) -> Announcement:
    _need(user, "mgmt.announce", "Only the CEO and the function leads post announcements.")
    title, body = (title or "").strip(), (body or "").strip()
    if not title or not body:
        raise ValidationError("Write a title and the announcement.")
    recipients = [u for u in recipients if u.is_active and u.pk != user.pk]
    if not recipients:
        raise ValidationError("Choose who receives it.")
    today = timezone.localdate()
    post = Announcement.objects.create(
        title=title,
        body=body,
        sender=user,
        confirm_by=add_working_days(today, CASCADE_DAYS),
        created_by=user,
        updated_by=user,
    )
    added, copies = _add_recipients(post, recipients, user)
    record_event(action="announcement_posted", instance=post)
    _tell(added, f"New from {user.full_name}: {title}. Please read and confirm in the desk by {post.confirm_by:%d/%m}.")
    _tell(copies, f"For your information (a member of your team received it): {title} — from {user.full_name}.")
    return post


def _recipient(user, post):
    r = Recipient.objects.filter(announcement=post, user=user).first()
    if r is None:
        raise PermissionDenied("This was not sent to you.")
    return r


@transaction.atomic
def confirm_receipt(user, post) -> Recipient:
    r = _recipient(user, post)
    if r.confirmed_at is None:
        r.confirmed_at = timezone.now()
        r.save(update_fields=["confirmed_at"])
    return r


def needs_forward(user, post) -> bool:
    r = Recipient.objects.filter(announcement=post, user=user, is_copy=False).first()
    if r is None or not team_of(user):
        return False
    return not Announcement.objects.filter(sender=user, root=post.original).exists()


@transaction.atomic
def forward(user, post, extra=()) -> Announcement:
    """Forward the same text, unchanged, to the person's team (§4.2)."""
    r = Recipient.objects.filter(announcement=post, user=user, is_copy=False).first()
    if r is None:
        raise PermissionDenied("Only someone who received this can forward it.")
    if Announcement.objects.filter(sender=user, root=post.original).exists():
        raise ValidationError("You have already forwarded this to your team.")
    team = team_of(user) + [u for u in extra if u not in team_of(user)]
    if not team:
        raise ValidationError("Nobody reports to you, so there is nothing to forward.")
    if r.confirmed_at is None:
        r.confirmed_at = timezone.now()
        r.save(update_fields=["confirmed_at"])
    original = post.original
    fwd = Announcement.objects.create(
        title=original.title,
        body=original.body,
        sender=user,
        forwarded_from=post,
        root=original,
        confirm_by=add_working_days(timezone.localdate(), CASCADE_DAYS),
        created_by=user,
        updated_by=user,
    )
    added, copies = _add_recipients(fwd, team, user)
    if not added and not copies:
        raise ValidationError("Everyone in your team has already received it.")
    record_event(action="announcement_forwarded", instance=fwd)
    _tell(
        added,
        f"From {user.full_name} (forwarded): {original.title}. Please read and confirm by {fwd.confirm_by:%d/%m}.",
    )
    _tell(
        copies, f"For your information (a member of your team received it): {original.title} — from {user.full_name}."
    )
    return fwd


def visible_announcements(user):
    received = Recipient.objects.filter(user=user).values("announcement_id")
    mine = Announcement.objects.filter(sender=user).values("pk")
    roots_i_started = Announcement.objects.filter(sender=user, root__isnull=True).values("pk")
    qs = Announcement.objects.filter(Q(pk__in=received) | Q(pk__in=mine) | Q(root__in=roots_i_started))
    if has_perm(user, "mgmt.meetings"):  # the OM keeps the communication records (§8)
        qs = Announcement.objects.all()
    return qs.select_related("sender", "root").distinct()


def can_see(user, post) -> bool:
    return visible_announcements(user).filter(pk=post.pk).exists()


def cascade(post) -> dict:
    """Everyone the original reached, who has confirmed and which leads still have to forward it."""
    original = post.original
    posts = [original, *Announcement.objects.filter(root=original).select_related("sender").order_by("sent_at")]
    rows = []
    for p in posts:
        for r in p.recipients.select_related("user"):
            rows.append(
                {
                    "r": r,
                    "post": p,
                    "pending_forward": (not r.is_copy) and needs_forward(r.user, p),
                    "late": r.confirmed_at is None and not r.is_copy and p.confirm_by < timezone.localdate(),
                }
            )
    to_confirm = [x for x in rows if not x["r"].is_copy]
    return {
        "posts": posts,
        "rows": rows,
        "confirmed": sum(1 for x in to_confirm if x["r"].confirmed_at),
        "total": len(to_confirm),
        "forwards_pending": [x for x in rows if x["pending_forward"]],
    }


def remind_announcements(today=None) -> int:
    today = today or timezone.localdate()
    n = 0
    late = Recipient.objects.filter(
        is_copy=False, confirmed_at__isnull=True, announcement__confirm_by__lt=today
    ).exclude(reminded_on=today)
    for r in late.select_related("announcement", "user"):
        _tell([r.user], f'Reminder: please read and confirm "{r.announcement.title}" in the desk.')
        r.reminded_on = today
        r.save(update_fields=["reminded_on"])
        n += 1
    for r in Recipient.objects.filter(
        is_copy=False, announcement__confirm_by__lt=today, confirmed_at__isnull=False
    ).select_related("announcement", "user"):
        if r.reminded_on != today and needs_forward(r.user, r.announcement):
            _tell(
                [r.user],
                f'Reminder: forward "{r.announcement.title}" to your team (due {r.announcement.confirm_by:%d/%m}).',
            )
            r.reminded_on = today
            r.save(update_fields=["reminded_on"])
            n += 1
    return n


# ---------------------------------------------------------------------------
# Handoffs between leads and requests to Systems & IT (§5.2, scope 7.1)
# ---------------------------------------------------------------------------
def it_receivers():
    return users_with_perm("system.admin").order_by("full_name")


@transaction.atomic
def send_handoff(user, *, kind, receiver=None, subject, detail, why="", benefits="", urgency="normal", go_live=None):
    _need(user, "mgmt.use")
    if kind not in Handoff.Kind.values:
        raise ValidationError("Choose what kind of handoff this is.")
    subject, detail = (subject or "").strip(), (detail or "").strip()
    if not subject or not detail:
        raise ValidationError("Write the subject and what is being handed over.")
    if kind == Handoff.Kind.IT_REQUEST:
        if receiver is None:
            receiver = it_receivers().first()
        if not (why or "").strip():
            raise ValidationError("Say why the change is needed.")
    if kind == Handoff.Kind.IT_NOTICE:
        _need(user, "system.admin", "Only Systems & IT sends system change notices.")
        if go_live is None:
            raise ValidationError("Give the go-live date of the change.")
    if kind == Handoff.Kind.UPDATE and receiver is not None and not is_ceo(receiver):
        raise ValidationError("Updates between monthly reports go to the CEO.")
    if kind == Handoff.Kind.UPDATE and receiver is None:
        receiver = next(iter(ceo_users()), None)
    if receiver is None or not receiver.is_active or not has_perm(receiver, "mgmt.use"):
        raise ValidationError("Choose who receives it.")
    if receiver.pk == user.pk:
        raise ValidationError("A handoff goes to someone else.")
    if urgency not in Handoff.Urgency.values:
        urgency = Handoff.Urgency.NORMAL
    h = Handoff.objects.create(
        reference=_next_ref(Handoff, f"HO-{timezone.localdate():%Y}-"),
        kind=kind,
        sender=user,
        receiver=receiver,
        subject=subject,
        detail=detail,
        why=(why or "").strip(),
        benefits=(benefits or "").strip()[:255],
        urgency=urgency,
        go_live=go_live,
        confirm_by=add_working_days(timezone.localdate(), HANDOFF_DAYS),
        created_by=user,
        updated_by=user,
    )
    record_event(action="handoff_sent", instance=h)
    _tell(
        [receiver],
        f"{h.reference} from {user.full_name}: {subject}. Please confirm in the desk by {h.confirm_by:%d/%m}.",
    )
    return h


def _lock_handoff(h):
    return Handoff.objects.select_for_update().get(pk=h.pk)


@transaction.atomic
def confirm_handoff(user, h, committed_date=None, note="") -> Handoff:
    h = _lock_handoff(h)
    if h.receiver_id != user.pk:
        raise PermissionDenied("Only the receiver confirms a handoff.")
    if h.status != Handoff.Status.SENT:
        raise ValidationError("This handoff has already been answered.")
    if h.kind == Handoff.Kind.IT_REQUEST:
        if committed_date is None:
            raise ValidationError("Give a committed date before starting (Systems & IT confirms a timeline).")
        if committed_date < timezone.localdate():
            raise ValidationError("The committed date can't be in the past.")
    h.status, h.confirmed_at, h.committed_date = Handoff.Status.CONFIRMED, timezone.now(), committed_date
    h.response = (note or "").strip()
    h.updated_by = user
    h.save()
    extra = f" Committed date: {committed_date:%d/%m/%Y}." if committed_date else ""
    _tell([h.sender], f"{h.reference} confirmed by {user.full_name}.{extra}")
    return h


@transaction.atomic
def decline_handoff(user, h, note) -> Handoff:
    h = _lock_handoff(h)
    if h.receiver_id != user.pk:
        raise PermissionDenied("Only the receiver answers a handoff.")
    if h.status not in Handoff.OPEN:
        raise ValidationError("This handoff is already closed.")
    if not (note or "").strip():
        raise ValidationError("Say why, so the sender knows what to do next.")
    h.status, h.response, h.updated_by = Handoff.Status.DECLINED, note.strip(), user
    h.save()
    _tell([h.sender], f"{h.reference} was declined by {user.full_name}: {note.strip()}")
    return h


@transaction.atomic
def complete_handoff(user, h, note="") -> Handoff:
    h = _lock_handoff(h)
    if user.pk not in (h.receiver_id, h.sender_id):
        raise PermissionDenied
    if h.status != Handoff.Status.CONFIRMED:
        raise ValidationError("Confirm the handoff first.")
    h.status, h.done_at, h.updated_by = Handoff.Status.DONE, timezone.now(), user
    if note:
        h.response = (h.response + "\n" + note.strip()).strip()
    h.save()
    other = h.sender if user.pk == h.receiver_id else h.receiver
    _tell([other], f"{h.reference} is done: {h.subject}.")
    return h


def visible_handoffs(user):
    qs = Handoff.objects.select_related("sender", "receiver")
    if has_perm(user, "mgmt.meetings"):
        return qs
    return qs.filter(Q(sender=user) | Q(receiver=user))


def remind_handoffs(today=None) -> int:
    today = today or timezone.localdate()
    n = 0
    for h in Handoff.objects.filter(status=Handoff.Status.SENT, confirm_by__lt=today).exclude(reminded_on=today):
        _tell([h.receiver], f"Reminder: {h.reference} from {h.sender.full_name} is waiting for your confirmation.")
        h.reminded_on = today
        h.save(update_fields=["reminded_on"])
        n += 1
    return n


# ---------------------------------------------------------------------------
# The monthly leads meeting (MOM template)
# ---------------------------------------------------------------------------
def default_attendees():
    ids = {u.pk for u in ceo_users()} | set(users_with_perm("mgmt.report").values_list("pk", flat=True))
    return get_user_model().objects.filter(pk__in=ids).order_by("full_name")


@transaction.atomic
def create_meeting(user, date, time=None, location="", attendees=None) -> Meeting:
    _need(user, "mgmt.meetings", "The Operations Manager records the leads meeting.")
    if date is None:
        raise ValidationError("Choose the meeting date.")
    m = Meeting.objects.create(date=date, time=time, location=location, prepared_by=user, created_by=user)
    for u in attendees if attendees is not None else default_attendees():
        MeetingAttendee.objects.create(meeting=m, user=u)
    record_event(action="meeting_created", instance=m)
    return m


def carried_actions(meeting):
    """Open action items from earlier meetings, reviewed at the start of this one."""
    return ActionItem.objects.filter(meeting__date__lt=meeting.date, status=ActionItem.Status.OPEN).select_related(
        "owner", "meeting"
    )


@transaction.atomic
def save_minutes(user, meeting, *, present_ids, agenda, decisions, actions, next_date=None, next_time=None,
                 next_location="", location=None, time=None) -> Meeting:  # fmt: skip
    """`agenda`: [(topic, summary, raised_by)], `decisions`: [(text, owner)], `actions`: [(action, owner, due)]."""
    _need(user, "mgmt.meetings", "The Operations Manager records the leads meeting.")
    meeting = Meeting.objects.select_for_update().get(pk=meeting.pk)
    if meeting.status != Meeting.Status.DRAFT:
        raise ValidationError("The minutes have been sent; they can't be changed.")
    for a in meeting.attendees.all():
        a.present = a.user_id in present_ids
        a.save(update_fields=["present"])
    meeting.agenda.all().delete()
    for topic, summary, raised_by in agenda:
        if topic.strip():
            AgendaItem.objects.create(
                meeting=meeting, topic=topic.strip(), summary=summary.strip(), raised_by=raised_by
            )
    meeting.decisions.all().delete()
    for text, owner in decisions:
        if text.strip():
            Decision.objects.create(meeting=meeting, text=text.strip(), owner=owner)
    meeting.actions.all().delete()
    for action, owner, due in actions:
        if not action.strip():
            continue
        if owner is None or due is None:
            raise ValidationError("Every action item needs an owner and a due date.")
        ActionItem.objects.create(meeting=meeting, action=action.strip(), owner=owner, due=due)
    meeting.next_date, meeting.next_time, meeting.next_location = next_date, next_time, next_location.strip()
    if location is not None:
        meeting.location = location.strip()
    if time is not None:
        meeting.time = time
    meeting.updated_by = user
    meeting.save()
    return meeting


@transaction.atomic
def publish_meeting(user, meeting) -> Meeting:
    _need(user, "mgmt.meetings", "The Operations Manager sends the minutes.")
    meeting = Meeting.objects.select_for_update().get(pk=meeting.pk)
    if meeting.status != Meeting.Status.DRAFT:
        raise ValidationError("The minutes have already been sent.")
    if not meeting.attendees.filter(present=True).exists():
        raise ValidationError("Mark who was present.")
    if not meeting.agenda.exists():
        raise ValidationError("Add at least one agenda item.")
    meeting.status, meeting.published_at, meeting.updated_by = Meeting.Status.PUBLISHED, timezone.now(), user
    meeting.save()
    record_event(action="meeting_minutes_sent", instance=meeting)
    people = {a.user for a in meeting.attendees.select_related("user")} | {
        a.owner for a in meeting.actions.select_related("owner")
    }
    _tell(people, f"Minutes of the leads meeting of {meeting.date:%d/%m/%Y} are in the desk. Please acknowledge them.")
    return meeting


@transaction.atomic
def acknowledge_minutes(user, meeting) -> MeetingAttendee:
    meeting = Meeting.objects.get(pk=meeting.pk)
    if meeting.status != Meeting.Status.PUBLISHED:
        raise ValidationError("The minutes haven't been sent yet.")
    a = MeetingAttendee.objects.filter(meeting=meeting, user=user).first()
    if a is None:
        raise PermissionDenied("You weren't on this meeting's list.")
    if a.acknowledged_at is None:
        a.acknowledged_at = timezone.now()
        a.save(update_fields=["acknowledged_at"])
    if has_perm(user, "mgmt.approve") and meeting.reviewed_by_id is None:
        Meeting.objects.filter(pk=meeting.pk).update(reviewed_by=user, reviewed_at=timezone.now())
    return a


@transaction.atomic
def update_action(user, item, status, note="") -> ActionItem:
    item = ActionItem.objects.select_for_update().get(pk=item.pk)
    if item.owner_id != user.pk and not has_perm(user, "mgmt.meetings"):
        raise PermissionDenied("Only the owner or the Operations Manager updates an action item.")
    if status not in ActionItem.Status.values:
        raise ValidationError("Choose a status.")
    if status == ActionItem.Status.DROPPED and not note.strip():
        raise ValidationError("Say why the action was dropped.")
    item.status, item.note = status, (note or item.note).strip()[:255]
    item.done_at = timezone.now() if status == ActionItem.Status.DONE else None
    item.save()
    return item


def visible_meetings(user):
    qs = Meeting.objects.all()
    if has_perm(user, "mgmt.meetings"):
        return qs
    return (
        qs.filter(status=Meeting.Status.PUBLISHED).filter(Q(attendees__user=user) | Q(actions__owner=user)).distinct()
    )


# ---------------------------------------------------------------------------
# Monthly upward reports (§6.1)
# ---------------------------------------------------------------------------
def month_bounds(month):
    import calendar

    return month, month.replace(day=calendar.monthrange(month.year, month.month)[1])


def previous_month(day):
    first = day.replace(day=1)
    return (first - datetime.timedelta(days=1)).replace(day=1)


def lead_report_due(month) -> datetime.date:
    nxt = (month.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return nxt.replace(day=LEAD_REPORT_DUE_DAY)


def _row(en, ar, value, last=None):
    return {"en": en, "ar": ar, "value": value, "last": last}


def report_figures(function, month) -> list[dict]:
    """Pre-filled figures for one lead's monthly report, this month vs last month (both branches)."""
    from apps.reports.services import _range

    m0, m1 = month_bounds(month)
    p0, p1 = month_bounds(previous_month(month))

    def both(fn):
        return fn(m0, m1), fn(p0, p1)

    rows = []
    if function == LeadReport.Function.TRAINING:
        from apps.classes.models import Attendance, ClassSession
        from apps.operations.models import Incident
        from apps.training.models import Evaluation, ProgressNote, Promotion, TestDay

        def count(model, **kw):
            return lambda a, z: model.objects.filter(**{k: (a, z) if v is None else v for k, v in kw.items()}).count()

        rows += [
            _row("Visits (check-ins)", "الزيارات", *both(count(Attendance, session__date__range=None))),
            _row("Classes held", "الحصص المنعقدة", *both(count(ClassSession, date__range=None, status="scheduled"))),
            _row("Evaluations recorded", "التقييمات المسجلة", *both(count(Evaluation, date__range=None))),
            _row("Promotions", "الترقيات", *both(count(Promotion, date__range=None))),
            _row("Test days held", "أيام الاختبار", *both(count(TestDay, date__range=None, status="closed"))),
            _row(
                "Progress notes sent",
                "تقارير التقدم المرسلة",
                *both(count(ProgressNote, month__range=None, status="sent")),
            ),
            _row("Incidents in class", "حوادث في الحصص", *both(count(Incident, session__date__range=None))),
            _row("Open incidents", "حوادث مفتوحة", Incident.objects.filter(status="open").count()),
        ]
    elif function == LeadReport.Function.OPERATIONS:
        from apps.leads.models import Lead
        from apps.operations.models import Complaint
        from apps.reports.services import _week_measures, active_memberships

        def measures(a, z):
            from apps.organization.models import Branch

            tot = defaultdict(int)
            for b in Branch.objects.filter(is_active=True):
                for k, v in _week_measures(b, a, z).items():
                    tot[k] += v
            return tot

        this, last = measures(m0, m1), measures(p0, p1)

        def leads(a, z):
            s0, e1 = _range(a, z)
            return Lead.objects.filter(created_at__gte=s0, created_at__lt=e1).count()

        conv = f"{round(this['trials_converted'] * 100 / this['trials_attended'])}%" if this["trials_attended"] else "—"
        conv_last = (
            f"{round(last['trials_converted'] * 100 / last['trials_attended'])}%" if last["trials_attended"] else "—"
        )
        rows += [
            _row("New leads", "عملاء محتملون جدد", *both(leads)),
            _row("Trials attended", "تجارب حضرت", this["trials_attended"], last["trials_attended"]),
            _row("Trial conversion", "تحويل التجارب", conv, conv_last),
            _row("New members", "أعضاء جدد", this["new"], last["new"]),
            _row("Renewals", "التجديدات", this["renewals"], last["renewals"]),
            _row("Members lost", "الأعضاء المفقودون", this["lost"], last["lost"]),
            _row(
                "Active members (month end)",
                "الأعضاء النشطون (نهاية الشهر)",
                active_memberships(m1).values("member_id").distinct().count(),
                active_memberships(p1).values("member_id").distinct().count(),
            ),
            _row("Complaints received", "الشكاوى المستلمة", this["complaints_received"], last["complaints_received"]),
            _row("Open complaints", "شكاوى مفتوحة", Complaint.objects.filter(status="open").count()),
        ]
    elif function == LeadReport.Function.MARKETING:
        from apps.leads.models import Broadcast, Campaign, Lead, MessagingOptIn, ReviewRequest

        def count(model, field):
            def fn(a, z):
                s0, e1 = _range(a, z)
                return model.objects.filter(**{f"{field}__gte": s0, f"{field}__lt": e1}).count()

            return fn

        def joined(a, z):
            s0, e1 = _range(a, z)
            return Lead.objects.filter(created_at__gte=s0, created_at__lt=e1, stage="joined").count()

        rows += [
            _row("Leads", "العملاء المحتملون", *both(count(Lead, "created_at"))),
            _row("Leads who joined", "انضموا", *both(joined)),
            _row("Broadcasts sent", "الرسائل الجماعية", *both(count(Broadcast, "sent_at"))),
            _row("Review requests sent", "طلبات التقييم", *both(count(ReviewRequest, "sent_at"))),
            _row("WhatsApp opt-ins recorded", "موافقات واتساب", *both(count(MessagingOptIn, "recorded_at"))),
        ]
        for c in Campaign.objects.filter(start__lte=m1).filter(Q(end__isnull=True) | Q(end__gte=m0))[:10]:
            from apps.leads.services import campaign_stats

            s = campaign_stats(c)
            rows.append(
                _row(
                    f"Campaign {c.name}: leads / joined / cost per lead",
                    f"حملة {c.name}: عملاء / انضموا / تكلفة العميل",
                    f"{s['leads']} / {s['joined']} / {s['cost_per_lead'] if s['cost_per_lead'] is not None else '—'}",
                )
            )
    elif function == LeadReport.Function.IT:

        def received(a, z):
            s0, e1 = _range(a, z)
            return Handoff.objects.filter(kind="it_request", created_at__gte=s0, created_at__lt=e1).count()

        def done(a, z):
            s0, e1 = _range(a, z)
            return Handoff.objects.filter(kind="it_request", done_at__gte=s0, done_at__lt=e1).count()

        open_qs = Handoff.objects.filter(kind="it_request", status__in=Handoff.OPEN)
        rows += [
            _row("Requests received", "الطلبات المستلمة", *both(received)),
            _row("Requests done", "الطلبات المنجزة", *both(done)),
            _row("Open requests", "الطلبات المفتوحة", open_qs.count()),
            _row(
                "Past their committed date",
                "تجاوزت الموعد الملتزم به",
                open_qs.filter(committed_date__lt=timezone.localdate()).count(),
            ),
            _row("Waiting for a timeline", "بانتظار تحديد موعد", open_qs.filter(status="sent").count()),
        ]
    return rows


@transaction.atomic
def save_lead_report(user, month, summary="", concerns="") -> LeadReport:
    _need(user, "mgmt.report", "Monthly reports are written by the function leads.")
    function = function_of(user)
    if function is None:
        raise ValidationError("Your role doesn't have a monthly report.")
    month = month.replace(day=1)
    if month > timezone.localdate():
        raise ValidationError("Choose a month that has started.")
    report, _ = LeadReport.objects.get_or_create(
        month=month, function=function, defaults={"author": user, "created_by": user}
    )
    if report.status != LeadReport.Status.DRAFT:
        raise ValidationError("This report has already been sent to the CEO.")
    report.summary, report.concerns, report.author, report.updated_by = summary.strip(), concerns.strip(), user, user
    report.save()
    return report


@transaction.atomic
def submit_lead_report(user, report) -> LeadReport:
    from apps.reports.services import jsonable

    report = LeadReport.objects.select_for_update().get(pk=report.pk)
    if report.author_id != user.pk:
        raise PermissionDenied("Only the lead who wrote it sends it.")
    if report.status != LeadReport.Status.DRAFT:
        raise ValidationError("Already sent.")
    if not report.summary.strip():
        raise ValidationError("Write the summary before sending.")
    report.data = jsonable({"rows": report_figures(report.function, report.month)})
    report.status, report.submitted_at = LeadReport.Status.SUBMITTED, timezone.now()
    report.save()
    record_event(action="lead_report_sent", instance=report)
    _tell(
        ceo_users(),
        f"{report.get_function_display()} report for {report.month:%m/%Y} from {user.full_name} is in the desk.",
    )
    return report


@transaction.atomic
def acknowledge_lead_report(user, report, note="") -> LeadReport:
    _need(user, "mgmt.approve", "The CEO acknowledges the monthly reports.")
    report = LeadReport.objects.select_for_update().get(pk=report.pk)
    if report.status != LeadReport.Status.SUBMITTED:
        raise ValidationError("This report isn't waiting for acknowledgement.")
    report.status, report.acknowledged_by, report.acknowledged_at = LeadReport.Status.ACKNOWLEDGED, user, timezone.now()
    report.ceo_note = note.strip()
    report.save()
    _tell([report.author], f"Your {report.get_function_display()} report for {report.month:%m/%Y} was acknowledged.")
    return report


def visible_lead_reports(user):
    qs = LeadReport.objects.select_related("author", "acknowledged_by")
    if has_perm(user, "mgmt.approve"):
        return qs
    return qs.filter(author=user)


# ---------------------------------------------------------------------------
# Escalation log (§6.2, §6.3)
# ---------------------------------------------------------------------------
@transaction.atomic
def raise_escalation(user, *, kind, description, needs_ceo=False, branch=None, direct_to_ceo=False,
                     direct_call_at=None, incident=None) -> Escalation:  # fmt: skip
    _need(user, "mgmt.use")
    if kind not in Escalation.Kind.values:
        raise ValidationError("Choose safety, conduct or other.")
    if not (description or "").strip():
        raise ValidationError("Describe the concern.")
    now = timezone.now()
    leads = leads_of(user)
    lead = leads[0] if leads else next(iter(ceo_users()), None)
    if direct_to_ceo:  # the lead wasn't answering or acting (§6.3): only the CEO and the person who raised it see it
        lead = next(iter(ceo_users()), None)
    e = Escalation(
        reference=_next_ref(Escalation, f"ESC-{timezone.localdate():%Y}-"),
        kind=kind,
        raised_by=user,
        raised_at=now,
        branch=branch,
        lead=lead,
        description=description.strip(),
        needs_ceo=bool(needs_ceo),
        incident=incident,
        direct_to_ceo=bool(direct_to_ceo),
        created_by=user,
    )
    if e.needs_ceo:
        e.ceo_due_at = now + datetime.timedelta(hours=Escalation.CEO_HOURS)
    if e.direct_to_ceo:
        e.direct_call_at = direct_call_at or now
        e.ceo_informed_at, e.ceo_informed_by = e.direct_call_at, user
    e.save()
    record_event(action="escalation_raised", instance=e)
    if e.direct_to_ceo:
        _tell(ceo_users(), f"{e.reference}: {user.full_name} called you about a {e.get_kind_display().lower()} concern "
                           "that wasn't being addressed. It is logged in the desk.")  # fmt: skip
    else:
        _tell([lead], f"{e.reference}: {user.full_name} raised a {e.get_kind_display().lower()} concern. Name an owner "
                      "today" + (" and tell the CEO within 24 hours." if e.needs_ceo else "."))  # fmt: skip
    return e


def visible_escalations(user):
    qs = Escalation.objects.select_related("raised_by", "lead", "owner", "branch")
    if is_ceo(user):
        return qs
    mine = Q(raised_by=user) | Q(lead=user) | Q(owner=user)
    if has_perm(user, "mgmt.escalations"):
        return qs.filter(mine | Q(direct_to_ceo=False))
    return qs.filter(mine)


def _can_manage(user, e) -> bool:
    return (
        user.pk in (e.lead_id, e.owner_id)
        or is_ceo(user)
        or (has_perm(user, "mgmt.escalations") and not e.direct_to_ceo)
    )


def _lock_escalation(user, e):
    e = Escalation.objects.select_for_update().get(pk=e.pk)
    if not _can_manage(user, e):
        raise PermissionDenied("Only the lead, the owner or the log keeper can do this.")
    if e.status != Escalation.Status.OPEN:
        raise ValidationError("This escalation is closed.")
    return e


@transaction.atomic
def name_owner(user, e, owner) -> Escalation:
    e = _lock_escalation(user, e)
    if owner is None or not owner.is_active:
        raise ValidationError("Choose the owner.")
    e.owner, e.owner_named_at, e.updated_by = owner, timezone.now(), user
    e.save()
    EscalationNote.objects.create(escalation=e, by=user, text=f"Owner named: {owner.full_name}")
    if owner.pk != user.pk:
        _tell([owner], f"You own {e.reference} ({e.get_kind_display().lower()} concern). Details are in the desk.")
    return e


@transaction.atomic
def inform_ceo(user, e, note="") -> Escalation:
    e = _lock_escalation(user, e)
    if e.ceo_informed_at:
        raise ValidationError("The CEO has already been told.")
    e.ceo_informed_at, e.ceo_informed_by, e.updated_by = timezone.now(), user, user
    e.save()
    EscalationNote.objects.create(escalation=e, by=user, text=("CEO told. " + note.strip()).strip())
    _tell(
        ceo_users(),
        f"{e.reference} ({e.get_kind_display().lower()}): {e.description[:200]}"
        + (f" — {note.strip()}" if note.strip() else ""),
    )
    return e


@transaction.atomic
def add_note(user, e, text) -> EscalationNote:
    if not visible_escalations(user).filter(pk=e.pk).exists():
        raise PermissionDenied
    if not (text or "").strip():
        raise ValidationError("Write the note.")
    return EscalationNote.objects.create(escalation=e, by=user, text=text.strip())


@transaction.atomic
def close_escalation(user, e, outcome) -> Escalation:
    e = _lock_escalation(user, e)
    if not (outcome or "").strip():
        raise ValidationError("Write the outcome.")
    if e.owner_id is None:
        raise ValidationError("Name an owner first.")
    if e.needs_ceo and e.ceo_informed_at is None:
        raise ValidationError("Tell the CEO before closing a safety or removal matter.")
    e.status, e.outcome, e.closed_at, e.closed_by, e.updated_by = (
        Escalation.Status.CLOSED, outcome.strip(), timezone.now(), user, user
    )  # fmt: skip
    e.save()
    record_event(action="escalation_closed", instance=e)
    _tell([e.raised_by], f"{e.reference} is closed: {outcome.strip()[:200]}")
    return e


def auto_escalate(now=None) -> int:
    """The 24-hour rule: a safety or removal matter the CEO hasn't been told about goes to the CEO automatically."""
    now = now or timezone.now()
    n = 0
    for e in Escalation.objects.filter(
        status="open", needs_ceo=True, ceo_informed_at__isnull=True, ceo_due_at__lt=now
    ).select_related("raised_by", "lead"):
        e.ceo_informed_at, e.ceo_auto = now, True
        e.save(update_fields=["ceo_informed_at", "ceo_auto"])
        EscalationNote.objects.create(escalation=e, by=e.raised_by, text="Sent to the CEO automatically (24 hours).")
        _tell(
            ceo_users() + ([e.lead] if e.lead else []),
            f"{e.reference} was not passed to the CEO within 24 hours, so the system sent it: {e.description[:200]}",
        )
        n += 1
    return n


# ---------------------------------------------------------------------------
# Procedure library
# ---------------------------------------------------------------------------
@transaction.atomic
def save_procedure(user, *, code, title, title_ar="", kind="procedure", owner, audience=(), procedure=None):
    _need(user, "mgmt.procedures", "Only the procedure owners edit the library.")
    code, title = (code or "").strip().upper(), (title or "").strip()
    if not code or not title:
        raise ValidationError("Give the document number and title.")
    if kind not in Procedure.Kind.values:
        raise ValidationError("Choose the document type.")
    if owner is None:
        raise ValidationError("Choose the owner.")
    if Procedure.objects.filter(code=code).exclude(pk=getattr(procedure, "pk", None)).exists():
        raise ValidationError("That document number is already in the library.")
    from apps.rbac.models import Role

    audience = sorted(set(audience) & set(Role.objects.values_list("code", flat=True)) - {"guardian"})
    p = procedure or Procedure(created_by=user)
    p.code, p.title, p.title_ar, p.kind, p.owner, p.audience, p.updated_by = (
        code, title, title_ar.strip(), kind, owner, audience, user
    )  # fmt: skip
    p.save()
    return p


@transaction.atomic
def add_version(user, procedure, *, version, effective_date, changes, upload=None) -> ProcedureVersion:
    _need(user, "mgmt.procedures", "Only the procedure owners edit the library.")
    version, changes = (version or "").strip(), (changes or "").strip()
    if not version or effective_date is None or not changes:
        raise ValidationError("Give the version number, the effective date and what changed.")
    if procedure.versions.filter(version=version).exists():
        raise ValidationError("That version number already exists.")
    if procedure.versions.filter(status=ProcedureVersion.Status.DRAFT).exists():
        raise ValidationError("A version is already waiting for approval.")
    v = ProcedureVersion(
        procedure=procedure,
        version=version,
        effective_date=effective_date,
        changes=changes,
        prepared_by=user,
        created_by=user,
    )
    if upload is not None:
        from apps.core.files import clean_document

        v.file = clean_document(upload)
    v.save()
    _tell([u for u in users_with_perm("mgmt.approve") if u.pk != user.pk],
          f"{procedure.code} v{version} is waiting for your approval.")  # fmt: skip
    return v


@transaction.atomic
def approve_version(user, v) -> ProcedureVersion:
    _need(user, "mgmt.approve", "The CEO approves procedures.")
    v = ProcedureVersion.objects.select_for_update().select_related("procedure").get(pk=v.pk)
    if v.status != ProcedureVersion.Status.DRAFT:
        raise ValidationError("This version isn't waiting for approval.")
    if v.prepared_by_id == user.pk:
        raise PermissionDenied("Someone else approves a version you prepared.")
    v.status, v.approved_by, v.approved_at, v.updated_by = ProcedureVersion.Status.APPROVED, user, timezone.now(), user
    v.save()
    record_event(action="procedure_approved", instance=v)
    _tell(
        audience_users(v.procedure),
        f"New version: {v.procedure.code} {v.procedure.title} v{v.version}, effective {v.effective_date:%d/%m/%Y}. "
        "Please read it and confirm in the desk.",
    )
    return v


@transaction.atomic
def return_version(user, v, note) -> ProcedureVersion:
    _need(user, "mgmt.approve", "The CEO approves procedures.")
    v = ProcedureVersion.objects.select_for_update().get(pk=v.pk)
    if v.status != ProcedureVersion.Status.DRAFT:
        raise ValidationError("This version isn't waiting for approval.")
    if not (note or "").strip():
        raise ValidationError("Say what needs changing.")
    v.status, v.return_note, v.updated_by = ProcedureVersion.Status.RETURNED, note.strip()[:255], user
    v.save()
    _tell([v.prepared_by], f"{v.procedure.code} v{v.version} was returned: {note.strip()}")
    return v


def audience_users(procedure):
    qs = staff_users()
    if procedure.audience:
        ids = RoleAssignment.objects.current().filter(role__code__in=procedure.audience).values("user_id")
        qs = qs.filter(pk__in=ids)
    return list(qs)


def must_read(user, procedure) -> bool:
    if not has_perm(user, "mgmt.use"):
        return False
    return not procedure.audience or bool(role_codes(user) & set(procedure.audience))


@transaction.atomic
def confirm_read(user, v) -> ReadConfirmation:
    v = ProcedureVersion.objects.get(pk=v.pk)
    if v.status != ProcedureVersion.Status.APPROVED:
        raise ValidationError("Only approved versions are confirmed.")
    if not has_perm(user, "mgmt.use"):
        raise PermissionDenied
    rc, _ = ReadConfirmation.objects.get_or_create(version=v, user=user)
    return rc


def pending_reads(user) -> list:
    out = []
    for p in Procedure.objects.filter(is_active=True).select_related("owner"):
        v = p.current
        if v is not None and must_read(user, p) and not v.reads.filter(user=user).exists():
            out.append(v)
    return out


def read_status(v) -> dict:
    readers = {r.user_id: r for r in v.reads.select_related("user")}
    people = audience_users(v.procedure)
    return {
        "read": [readers[u.pk] for u in people if u.pk in readers],
        "missing": [u for u in people if u.pk not in readers],
        "total": len(people),
    }


# ---------------------------------------------------------------------------
# Daily and hourly jobs
# ---------------------------------------------------------------------------
def hourly_jobs() -> dict:
    return {"escalations_sent_to_ceo": auto_escalate()}


def daily_jobs() -> dict:
    from .quarterly import remind_quarterly

    return {
        "announcement_reminders": remind_announcements(),
        "handoff_reminders": remind_handoffs(),
        "quarterly_reminders": remind_quarterly(),
    }
