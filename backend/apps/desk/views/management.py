"""Management screens (M12) and the Quarterly Business Report (RPT-01) — decisions P7-1 to P7-10."""

import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.audit.services import record_event
from apps.management import quarterly as qbr
from apps.management import services as ms
from apps.management.models import (
    ActionItem,
    Announcement,
    Escalation,
    Handoff,
    Meeting,
    Procedure,
    ProcedureVersion,
    QuarterlyReport,
    Recipient,
)
from apps.organization.models import Branch
from apps.rbac.models import Role
from apps.rbac.services import users_with_perm

from ..access import L, can, desk, lang
from .finance import export_doc


def _date(value):
    try:
        return datetime.date.fromisoformat(value or "")
    except ValueError:
        return None


def _time(value):
    try:
        return datetime.time.fromisoformat(value or "")
    except ValueError:
        return None


def _user(pk):
    if not pk:
        return None
    return get_user_model().objects.filter(pk=pk, is_active=True).first()


def _staff():
    return list(ms.staff_users())


def _done(request, en, ar):
    messages.success(request, L(en, ar))


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
@desk("mgmt.use")
def overview(request):
    user = request.user
    to_confirm = Recipient.objects.filter(user=user, is_copy=False, confirmed_at__isnull=True).select_related(
        "announcement__sender"
    )
    to_forward = [
        r.announcement
        for r in Recipient.objects.filter(user=user, is_copy=False).select_related("announcement")
        if ms.needs_forward(user, r.announcement)
    ]
    return render(
        request,
        "desk/management/overview.html",
        {
            "to_confirm": to_confirm,
            "to_forward": to_forward,
            "handoffs": Handoff.objects.filter(receiver=user, status__in=Handoff.OPEN).select_related("sender"),
            "actions": ActionItem.objects.filter(owner=user, status="open").select_related("meeting"),
            "reads": ms.pending_reads(user),
            "escalations": ms.visible_escalations(user).filter(status="open")[:10],
            "minutes": Meeting.objects.filter(
                status="published", attendees__user=user, attendees__acknowledged_at__isnull=True
            ),
            "leads": ms.leads_of(user),
            "team": ms.team_of(user),
        },
    )


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------
@desk("mgmt.use")
def announcements(request):
    qs = ms.visible_announcements(request.user).filter(root__isnull=True)
    return render(
        request,
        "desk/management/announcements.html",
        {
            "posts": [(p, ms.cascade(p)) for p in qs[:50]],
            "received": Recipient.objects.filter(user=request.user).select_related("announcement__sender")[:50],
        },
    )


@desk("mgmt.announce")
def announcement_new(request):
    staff = [u for u in _staff() if u.pk != request.user.pk]
    if request.method == "POST":
        ids = {int(x) for x in request.POST.getlist("to") if x.isdigit()}
        post = ms.post_announcement(
            request.user,
            request.POST.get("title", ""),
            request.POST.get("body", ""),
            [u for u in staff if u.pk in ids],
        )
        _done(
            request,
            "Sent. Each person confirms receipt; leads forward it unchanged.",
            "أُرسل. يؤكد كل شخص الاستلام، ويعيد القادة إرساله كما هو.",
        )
        return redirect("desk:announcement", post.pk)
    team = {u.pk for u in ms.team_of(request.user)}
    leads = {u.pk for u in users_with_perm("mgmt.report")}
    return render(
        request,
        "desk/management/announcement_new.html",
        {"staff": staff, "preselected": team or leads},
    )


@desk("mgmt.use")
def announcement(request, pk):
    post = get_object_or_404(Announcement.objects.select_related("sender", "root"), pk=pk)
    if not ms.can_see(request.user, post):
        raise Http404
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "confirm":
            ms.confirm_receipt(request.user, post)
            _done(request, "Receipt confirmed.", "تم تأكيد الاستلام.")
        elif action == "forward":
            fwd = ms.forward(request.user, post)
            _done(request, "Forwarded unchanged to your team.", "أُعيد إرساله كما هو إلى فريقك.")
            return redirect("desk:announcement", fwd.pk)
        return redirect("desk:announcement", post.pk)
    mine = Recipient.objects.filter(announcement=post, user=request.user).first()
    started = post.original.sender_id == request.user.pk or can(request, "mgmt.meetings")
    return render(
        request,
        "desk/management/announcement.html",
        {
            "post": post,
            "mine": mine,
            "can_forward": ms.needs_forward(request.user, post),
            "team": ms.team_of(request.user),
            "cascade": ms.cascade(post) if started or post.sender_id == request.user.pk else None,
        },
    )


# ---------------------------------------------------------------------------
# Handoffs
# ---------------------------------------------------------------------------
@desk("mgmt.use")
def handoffs(request):
    show = request.GET.get("show", "open")
    qs = ms.visible_handoffs(request.user)
    if show == "open":
        qs = qs.filter(status__in=Handoff.OPEN)
    elif show == "it":
        qs = qs.filter(kind="it_request")
    return render(request, "desk/management/handoffs.html", {"handoffs": qs[:200], "show": show})


@desk("mgmt.use")
def handoff_new(request):
    staff = [u for u in _staff() if u.pk != request.user.pk]
    if request.method == "POST":
        p = request.POST
        h = ms.send_handoff(
            request.user,
            kind=p.get("kind", ""),
            receiver=_user(p.get("receiver")),
            subject=p.get("subject", ""),
            detail=p.get("detail", ""),
            why=p.get("why", ""),
            benefits=p.get("benefits", ""),
            urgency=p.get("urgency", "normal"),
            go_live=_date(p.get("go_live")),
        )
        _done(request, "Sent — waiting for the receiver to confirm.", "أُرسل — بانتظار تأكيد المستلم.")
        return redirect("desk:handoff", h.pk)
    kind = request.GET.get("kind", "")
    kinds = [(v, lbl) for v, lbl in Handoff.Kind.choices if v != "it_notice" or can(request, "system.admin")]
    return render(
        request,
        "desk/management/handoff_new.html",
        {"staff": staff, "kinds": kinds, "kind": kind, "urgencies": Handoff.Urgency.choices},
    )


@desk("mgmt.use")
def handoff(request, pk):
    h = get_object_or_404(ms.visible_handoffs(request.user), pk=pk)
    if request.method == "POST":
        p, action = request.POST, request.POST.get("action")
        if action == "confirm":
            ms.confirm_handoff(request.user, h, _date(p.get("committed_date")), p.get("note", ""))
            _done(request, "Confirmed.", "تم التأكيد.")
        elif action == "decline":
            ms.decline_handoff(request.user, h, p.get("note", ""))
            _done(request, "Declined — the sender has been told.", "رُفض — تم إبلاغ المرسل.")
        elif action == "done":
            ms.complete_handoff(request.user, h, p.get("note", ""))
            _done(request, "Marked done.", "تم التعليم كمنجز.")
        return redirect("desk:handoff", h.pk)
    return render(request, "desk/management/handoff.html", {"h": h, "today": timezone.localdate()})


# ---------------------------------------------------------------------------
# Leads meeting
# ---------------------------------------------------------------------------
@desk("mgmt.use")
def meetings(request):
    if request.method == "POST":
        if not can(request, "mgmt.meetings"):
            raise PermissionDenied
        m = ms.create_meeting(
            request.user,
            _date(request.POST.get("date")),
            _time(request.POST.get("time")),
            request.POST.get("location", ""),
        )
        return redirect("desk:meeting", m.pk)
    return render(
        request,
        "desk/management/meetings.html",
        {
            "meetings": ms.visible_meetings(request.user)[:36],
            "actions": ActionItem.objects.filter(status="open").select_related("owner", "meeting")
            if can(request, "mgmt.meetings")
            else ActionItem.objects.filter(owner=request.user, status="open").select_related("meeting"),
            "today": timezone.localdate(),
        },
    )


def _rows(p, prefix, fields, n):
    out = []
    for i in range(n):
        out.append([p.get(f"{prefix}{i}_{f}", "") for f in fields])
    return out


@desk("mgmt.use")
def meeting(request, pk):
    m = get_object_or_404(ms.visible_meetings(request.user), pk=pk)
    editable = m.status == "draft" and can(request, "mgmt.meetings")
    if request.method == "POST":
        p, action = request.POST, request.POST.get("action")
        if action in ("save", "publish") and editable:
            n = int(p.get("rows") or 0)
            n = min(max(n, 0), 40)
            ms.save_minutes(
                request.user,
                m,
                present_ids={int(x) for x in p.getlist("present") if x.isdigit()},
                agenda=[(t, s, _user(r)) for t, s, r in _rows(p, "ag", ("topic", "summary", "by"), n)],
                decisions=[(t, _user(o)) for t, o in _rows(p, "de", ("text", "owner"), n)],
                actions=[(a, _user(o), _date(d)) for a, o, d in _rows(p, "ac", ("action", "owner", "due"), n)],
                next_date=_date(p.get("next_date")),
                next_time=_time(p.get("next_time")),
                next_location=p.get("next_location", ""),
                location=p.get("location", ""),
                time=_time(p.get("time")),
            )
            if action == "publish":
                ms.publish_meeting(request.user, m)
                _done(
                    request,
                    "Minutes sent. Action items are now on the owners' task lists.",
                    "أُرسل المحضر. بنود العمل الآن في قوائم مهام أصحابها.",
                )
            else:
                _done(request, "Minutes saved.", "تم حفظ المحضر.")
        elif action == "ack":
            ms.acknowledge_minutes(request.user, m)
            _done(request, "Minutes acknowledged.", "تم الاطلاع على المحضر.")
        elif action == "item":
            item = get_object_or_404(ActionItem, pk=p.get("item"))
            ms.update_action(request.user, item, p.get("status", ""), p.get("note", ""))
            _done(request, "Action item updated.", "تم تحديث بند العمل.")
        return redirect("desk:meeting", m.pk)
    attendees = list(m.attendees.select_related("user"))
    blank = 3
    return render(
        request,
        "desk/management/meeting.html",
        {
            "m": m,
            "editable": editable,
            "attendees": attendees,
            "mine": next((a for a in attendees if a.user_id == request.user.pk), None),
            "agenda": list(m.agenda.select_related("raised_by")) + [None] * (blank if editable else 0),
            "decisions": list(m.decisions.select_related("owner")) + [None] * (blank if editable else 0),
            "actions": list(m.actions.select_related("owner")) + [None] * (blank if editable else 0),
            "carried": ms.carried_actions(m),
            "staff": _staff(),
            "rows": 40,
            "statuses": ActionItem.Status.choices,
        },
    )


# ---------------------------------------------------------------------------
# Monthly lead reports
# ---------------------------------------------------------------------------
@desk(any_of=["mgmt.report", "mgmt.approve"])
def lead_reports(request):
    user = request.user
    function = ms.function_of(user) if can(request, "mgmt.report") else None
    last = ms.previous_month(timezone.localdate())
    if request.method == "POST" and function:
        month = _date(request.POST.get("month")) or last
        report = ms.save_lead_report(user, month)
        return redirect("desk:lead_report", report.pk)
    return render(
        request,
        "desk/management/lead_reports.html",
        {
            "reports": ms.visible_lead_reports(user)[:60],
            "function": function,
            "last_month": last,
            "this_month": timezone.localdate().replace(day=1),
            "due": ms.lead_report_due(last),
        },
    )


@desk(any_of=["mgmt.report", "mgmt.approve"])
def lead_report(request, pk):
    report = get_object_or_404(ms.visible_lead_reports(request.user), pk=pk)
    if request.method == "POST":
        p, action = request.POST, request.POST.get("action")
        if action in ("save", "submit"):
            if report.author_id != request.user.pk:
                raise PermissionDenied
            report = ms.save_lead_report(request.user, report.month, p.get("summary", ""), p.get("concerns", ""))
            if action == "submit":
                ms.submit_lead_report(request.user, report)
                _done(request, "Sent to the CEO.", "أُرسل إلى الرئيس التنفيذي.")
            else:
                _done(request, "Saved.", "تم الحفظ.")
        elif action == "ack":
            ms.acknowledge_lead_report(request.user, report, p.get("note", ""))
            _done(request, "Acknowledged.", "تم الاطلاع.")
        return redirect("desk:lead_report", report.pk)
    rows = report.data.get("rows") if report.status != "draft" else ms.report_figures(report.function, report.month)
    return render(
        request,
        "desk/management/lead_report.html",
        {
            "r": report,
            "rows": rows,
            "mine": report.author_id == request.user.pk,
            "due": ms.lead_report_due(report.month),
        },
    )


# ---------------------------------------------------------------------------
# Escalation log
# ---------------------------------------------------------------------------
@desk("mgmt.use")
def escalations(request):
    from apps.operations.models import Incident

    status = request.GET.get("status", "open")
    qs = ms.visible_escalations(request.user)
    if status in ("open", "closed"):
        qs = qs.filter(status=status)
    incidents = []
    if can(request, "mgmt.escalations"):
        incidents = Incident.objects.filter(needs_ceo=True).select_related("branch").order_by("-occurred_at")[:30]
    return render(
        request,
        "desk/management/escalations.html",
        {"escalations": qs[:200], "status": status, "incidents": incidents},
    )


@desk("mgmt.use")
def escalation_new(request):
    if request.method == "POST":
        p = request.POST
        call = None
        if p.get("direct") == "1" and p.get("call_at"):
            try:
                call = timezone.make_aware(datetime.datetime.fromisoformat(p["call_at"]))
            except ValueError:
                call = None
        e = ms.raise_escalation(
            request.user,
            kind=p.get("kind", ""),
            description=p.get("description", ""),
            needs_ceo=p.get("needs_ceo") == "1",
            branch=Branch.objects.filter(pk=p.get("branch") or None).first(),
            direct_to_ceo=p.get("direct") == "1",
            direct_call_at=call,
        )
        _done(request, "Logged. Your lead has been told.", "تم التسجيل وإبلاغ قائدك.")
        return redirect("desk:escalation", e.pk)
    return render(
        request,
        "desk/management/escalation_new.html",
        {
            "kinds": Escalation.Kind.choices,
            "branches": Branch.objects.filter(is_active=True).order_by("-code"),
            "leads": ms.leads_of(request.user),
            "now": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        },
    )


@desk("mgmt.use")
def escalation(request, pk):
    e = get_object_or_404(ms.visible_escalations(request.user), pk=pk)
    if request.method == "POST":
        p, action = request.POST, request.POST.get("action")
        if action == "owner":
            ms.name_owner(request.user, e, _user(p.get("owner")))
            _done(request, "Owner named.", "تم تحديد المسؤول.")
        elif action == "ceo":
            ms.inform_ceo(request.user, e, p.get("note", ""))
            _done(request, "The CEO has been told.", "تم إبلاغ الرئيس التنفيذي.")
        elif action == "note":
            ms.add_note(request.user, e, p.get("text", ""))
        elif action == "close":
            ms.close_escalation(request.user, e, p.get("outcome", ""))
            _done(request, "Closed.", "أُغلقت.")
        return redirect("desk:escalation", e.pk)
    return render(
        request,
        "desk/management/escalation.html",
        {
            "e": e,
            "manage": ms._can_manage(request.user, e),
            "staff": _staff(),
            "notes": e.notes.select_related("by"),
        },
    )


# ---------------------------------------------------------------------------
# Procedure library
# ---------------------------------------------------------------------------
@desk("mgmt.use")
def procedures(request):
    rows = []
    for p in Procedure.objects.filter(is_active=True).select_related("owner"):
        v = p.current
        rows.append(
            {
                "p": p,
                "v": v,
                "draft": p.versions.filter(status="draft").first(),
                "read": v is not None and v.reads.filter(user=request.user).exists(),
                "must": ms.must_read(request.user, p),
            }
        )
    return render(
        request,
        "desk/management/procedures.html",
        {"rows": rows, "staff": _staff(), "kinds": Procedure.Kind.choices, "roles": _roles()},
    )


def _roles():
    return list(Role.objects.exclude(code="guardian").order_by("name").values_list("code", "name"))


@desk("mgmt.procedures")
def procedure_new(request):
    if request.method == "POST":
        p = request.POST
        proc = ms.save_procedure(
            request.user,
            code=p.get("code", ""),
            title=p.get("title", ""),
            title_ar=p.get("title_ar", ""),
            kind=p.get("kind", ""),
            owner=_user(p.get("owner")),
            audience=p.getlist("audience"),
        )
        _done(request, "Added to the library. Now add its first version.", "أُضيف للمكتبة. أضف الآن إصداره الأول.")
        return redirect("desk:procedure", proc.pk)
    return redirect("desk:procedures")


@desk("mgmt.use")
def procedure(request, pk):
    proc = get_object_or_404(Procedure.objects.select_related("owner"), pk=pk)
    if request.method == "POST":
        p, action = request.POST, request.POST.get("action")
        if action == "read":
            v = get_object_or_404(ProcedureVersion, pk=p.get("version"), procedure=proc)
            ms.confirm_read(request.user, v)
            _done(request, "Thank you — reading confirmed.", "شكراً — تم تأكيد القراءة.")
        elif action == "version":
            ms.add_version(
                request.user,
                proc,
                version=p.get("version_no", ""),
                effective_date=_date(p.get("effective_date")),
                changes=p.get("changes", ""),
                upload=request.FILES.get("file"),
            )
            _done(request, "Version sent for approval.", "أُرسل الإصدار للاعتماد.")
        elif action in ("approve", "return"):
            v = get_object_or_404(ProcedureVersion, pk=p.get("version"), procedure=proc)
            if action == "approve":
                ms.approve_version(request.user, v)
                _done(request, "Approved — staff are asked to read it.", "اعتُمد — طُلب من الموظفين قراءته.")
            else:
                ms.return_version(request.user, v, p.get("note", ""))
                _done(request, "Returned.", "أُعيد.")
        elif action == "edit":
            ms.save_procedure(
                request.user,
                code=p.get("code", ""),
                title=p.get("title", ""),
                title_ar=p.get("title_ar", ""),
                kind=p.get("kind", ""),
                owner=_user(p.get("owner")),
                audience=p.getlist("audience"),
                procedure=proc,
            )
            _done(request, "Saved.", "تم الحفظ.")
        return redirect("desk:procedure", proc.pk)
    current = proc.current
    return render(
        request,
        "desk/management/procedure.html",
        {
            "proc": proc,
            "current": current,
            "versions": proc.versions.select_related("prepared_by", "approved_by"),
            "status": ms.read_status(current) if current and can(request, "mgmt.procedures") else None,
            "read": current is not None and current.reads.filter(user=request.user).exists(),
            "must": ms.must_read(request.user, proc),
            "staff": _staff(),
            "kinds": Procedure.Kind.choices,
            "roles": _roles(),
            "today": timezone.localdate(),
        },
    )


@desk("mgmt.use")
def procedure_file(request, pk):
    v = get_object_or_404(ProcedureVersion, pk=pk)
    if not v.file or (v.status != "approved" and not (can(request, "mgmt.procedures") or can(request, "mgmt.approve"))):
        raise Http404
    record_event(action="procedure_downloaded", instance=v)
    from apps.core.files import content_type_for

    name = f"{v.procedure.code}-v{v.version}.{'pdf' if v.file.name.endswith('.pdf') else 'jpg'}"
    response = FileResponse(v.file.open("rb"), content_type=content_type_for(v.file.name))
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    response["Cache-Control"] = "private, no-store"
    return response


# ---------------------------------------------------------------------------
# Staff directory and org chart
# ---------------------------------------------------------------------------
@desk("mgmt.use")
def directory(request):
    q = request.GET.get("q", "").strip()
    return render(
        request,
        "desk/management/directory.html",
        {"people": ms.directory(q), "q": q, "chart": ms.org_chart() if not q else None},
    )


# ---------------------------------------------------------------------------
# Quarterly Business Report (RPT-01)
# ---------------------------------------------------------------------------
@desk(any_of=["mgmt.qbr", "mgmt.approve"])
def quarterly(request):
    if request.method == "POST":
        if not can(request, "mgmt.qbr"):
            raise PermissionDenied
        report = qbr.open_report(request.user, _date(request.POST.get("quarter")) or qbr.last_finished_quarter())
        return redirect("desk:quarterly_report", report.pk)
    last = qbr.last_finished_quarter()
    return render(
        request,
        "desk/management/quarterly.html",
        {
            "reports": QuarterlyReport.objects.select_related("prepared_by", "approved_by"),
            "last": last,
            "last_label": qbr.label(last),
            "due": qbr.quarter_end(last) + datetime.timedelta(days=QuarterlyReport.DUE_DAYS),
            "has_last": QuarterlyReport.objects.filter(quarter_start=last).exists(),
            "current_label": qbr.label(qbr.quarter_start(timezone.localdate())),
        },
    )


@desk(any_of=["mgmt.qbr", "mgmt.approve"])
def quarterly_preview(request):
    """The current quarter so far, live (nothing is saved)."""
    start = qbr.quarter_start(timezone.localdate())
    doc = qbr.document(qbr.build(start), None, lang())
    if request.GET.get("format"):
        return export_doc(request, qbr.export_doc(doc), f"RPT-01-{start.year}-Q{(start.month - 1) // 3 + 1}-so-far")
    return render(request, "desk/management/quarterly_preview.html", {"doc": doc})


@desk(any_of=["mgmt.qbr", "mgmt.approve"])
def quarterly_report(request, pk):
    report = get_object_or_404(QuarterlyReport.objects.select_related("prepared_by", "approved_by"), pk=pk)
    if request.method == "POST":
        p, action = request.POST, request.POST.get("action")
        if action in ("save", "submit"):
            qbr.save_text(
                request.user,
                report,
                summary=p.get("summary", ""),
                strategy=p.get("strategy", ""),
                comments={n: p.get(f"c{n}", "") for n in range(3, 12)},
                difference_note=p.get("difference_note", ""),
            )
            if action == "submit":
                qbr.submit(request.user, report)
                _done(
                    request,
                    "Submitted to the CEO. The figures are now frozen.",
                    "أُرسل للرئيس التنفيذي. الأرقام الآن مثبّتة.",
                )
            else:
                _done(request, "Saved.", "تم الحفظ.")
        elif action == "approve":
            qbr.approve(request.user, report)
            _done(request, "Approved.", "اعتُمد.")
        elif action == "return":
            qbr.return_report(request.user, report, p.get("note", ""))
            _done(request, "Returned to the OM.", "أُعيد لمدير العمليات.")
        return redirect("desk:quarterly_report", report.pk)
    data = qbr.figures(report)
    doc = qbr.document(data, report, lang())
    if request.GET.get("format"):
        return export_doc(request, qbr.export_doc(doc), report.reference)
    editable = report.status in ("draft", "returned") and can(request, "mgmt.qbr")
    inc = data["income"]
    return render(
        request,
        "desk/management/quarterly_report.html",
        {
            "r": report,
            "doc": doc,
            "editable": editable,
            "sections": qbr.SECTIONS[2:],
            "comments": report.comments or {},
            "difference": inc["difference"],
            "unverified": inc["unverified"],
            "export_url": reverse("desk:quarterly_report", args=[report.pk]),
        },
    )
