"""Daily operations (M9): my tasks, shift opening, incidents, complaints, cover & handover."""

import datetime

from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.classes.models import ClassSession
from apps.operations import services as ops
from apps.operations.models import SHIFT_CHECKS, Complaint, Handover, Incident, ShiftOpening
from apps.rbac.services import has_perm, users_with_perm

from ..access import L, can, desk, lang
from ..lookup import search_members, visible_members
from ..tasks import my_tasks

User = get_user_model()


def _dt(value):
    """'2026-09-29T14:30' from a datetime-local input → aware datetime (or None)."""
    if not value:
        return None
    try:
        return timezone.make_aware(datetime.datetime.fromisoformat(value))
    except ValueError:
        return None


def _date(value, default=None):
    try:
        return datetime.date.fromisoformat(value) if value else default
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# My tasks
# ---------------------------------------------------------------------------
@desk()
def tasks(request):
    return render(request, "desk/ops/tasks.html", {"tasks": my_tasks(request)})


# ---------------------------------------------------------------------------
# Shift opening (FRM-01)
# ---------------------------------------------------------------------------
@desk("ops.shift")
def shift_opening(request):
    branch, today = request.branch, timezone.localdate()
    shift = (
        request.POST.get("shift")
        or request.GET.get("shift")
        or ("morning" if timezone.localtime().hour < 14 else "evening")
    )
    if request.method == "POST":
        done = request.POST.getlist("done")
        notes = {code: request.POST.get(f"note_{code}", "") for code, *_ in SHIFT_CHECKS}
        ops.complete_shift_opening(
            branch,
            today,
            shift,
            request.user,
            done=done,
            notes=notes,
            hazard=request.POST.get("hazard", ""),
            confirmed=request.POST.get("confirm") == "1",
        )
        messages.success(request, L("Shift opened. Have a good shift.", "تم فتح النوبة. نوبة موفقة."))
        return redirect("desk:home")
    existing = (
        ShiftOpening.objects.filter(branch=branch, date=today, shift=shift).select_related("completed_by").first()
    )
    history = ShiftOpening.objects.filter(branch=branch).select_related("completed_by")[:14]
    checks = [{"code": c, "label": ar if lang() == "ar" else en} for c, en, ar in SHIFT_CHECKS]
    return render(
        request,
        "desk/ops/shift.html",
        {"checks": checks, "shift": shift, "existing": existing, "history": history, "today": today},
    )


# ---------------------------------------------------------------------------
# Incidents (FRM-09)
# ---------------------------------------------------------------------------
def _incidents_for(request):
    qs = Incident.objects.filter(branch=request.branch).select_related("member", "created_by", "follow_up_owner")
    if not can(request, "ops.manage"):
        qs = qs.filter(created_by=request.user)
    return qs


@desk(any_of=["ops.incident", "ops.manage"])
def incidents(request):
    status = request.GET.get("status", "open")
    qs = _incidents_for(request)
    if status in ("open", "closed"):
        qs = qs.filter(status=status)
    return render(request, "desk/ops/incidents.html", {"incidents": qs[:100], "status": status})


class IncidentForm(forms.Form):
    occurred_at = forms.DateTimeField(widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    kind = forms.ChoiceField(choices=Incident.Kind.choices)
    member = forms.IntegerField(required=False, widget=forms.HiddenInput)
    people = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    session = forms.ModelChoiceField(queryset=ClassSession.objects.none(), required=False)
    what_happened = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))
    action_taken = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))
    guardian_informed_name = forms.CharField(required=False, max_length=150)
    guardian_informed_at = forms.DateTimeField(
        required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    witnesses = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    needs_ceo = forms.BooleanField(required=False)

    def __init__(self, branch, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["session"].queryset = ClassSession.objects.filter(
            branch=branch, date__range=(today - datetime.timedelta(days=2), today)
        ).order_by("-date", "-start")
        labels = {
            "occurred_at": ("Date and time", "التاريخ والوقت"),
            "kind": ("Type", "النوع"),
            "people": ("Person(s) involved (name, age, guardian)", "الأشخاص المعنيون (الاسم والعمر وولي الأمر)"),
            "session": ("Class and instructor", "الحصة والمدرب"),
            "what_happened": ("What happened", "ما الذي حدث"),
            "action_taken": (
                "Action taken (first aid, ambulance, class stopped)",
                "الإجراء المتخذ (إسعاف أولي، إسعاف، إيقاف الحصة)",
            ),
            "guardian_informed_name": ("Parent / guardian informed (who)", "ولي الأمر الذي أُبلغ"),
            "guardian_informed_at": ("Guardian informed at", "وقت إبلاغ ولي الأمر"),
            "witnesses": ("Witnesses", "الشهود"),
            "needs_ceo": (
                "A safety matter or a decision to remove someone — the CEO must know within 24 hours",
                "مسألة سلامة أو قرار باستبعاد شخص — يجب إبلاغ الرئيس التنفيذي خلال 24 ساعة",
            ),
        }
        for name, (en, ar) in labels.items():
            self.fields[name].label = L(en, ar)
        self.fields["kind"].choices = [
            (v, L(en, ar))
            for (v, en), ar in zip(Incident.Kind.choices, ["إصابة", "خطر على السلامة", "سلوك", "أخرى"], strict=True)
        ]


@desk("ops.incident")
def incident_new(request):
    form = IncidentForm(
        request.branch, request.POST or None, initial={"occurred_at": timezone.localtime().strftime("%Y-%m-%dT%H:%M")}
    )
    member = None
    member_id = request.POST.get("member") or request.GET.get("member")
    if member_id:
        member = visible_members(request.user).filter(pk=member_id).first()
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        session = data.pop("session")
        data.pop("member")
        incident = ops.report_incident(
            request.branch,
            request.user,
            member=member,
            session=session,
            instructor=session.instructors.first() if session else None,
            **data,
        )
        messages.success(
            request,
            L(
                f"Incident {incident.reference} reported. The OM has been told.",
                f"تم تسجيل الحادثة {incident.reference} وإبلاغ مدير العمليات.",
            ),
        )
        return redirect("desk:incident", pk=incident.pk)
    found = search_members(request.user, request.GET.get("q", "")) if request.GET.get("q") else None
    return render(request, "desk/ops/incident_new.html", {"form": form, "member": member, "found": found})


def _incident_for(request, pk):
    """Visible to the OM of the incident's branch and to the person who reported it."""
    incident = get_object_or_404(Incident.objects.select_related("member", "created_by", "follow_up_owner"), pk=pk)
    if has_perm(request.user, "ops.manage", incident.branch_id) or incident.created_by_id == request.user.pk:
        return incident
    raise Http404


@desk(any_of=["ops.incident", "ops.manage"])
def incident_detail(request, pk):
    incident = _incident_for(request, pk)
    manages = has_perm(request.user, "ops.manage", incident.branch_id)
    staff = users_with_perm("ops.incident", incident.branch_id) if manages else []
    return render(request, "desk/ops/incident.html", {"i": incident, "staff": staff})


@require_POST
@desk("ops.manage")
def incident_action(request, pk):
    incident = _incident_for(request, pk)
    if not has_perm(request.user, "ops.manage", incident.branch_id):
        raise PermissionDenied
    action = request.POST.get("action")
    if action == "escalate":
        ops.escalate_to_ceo(incident, request.user, request.POST.get("note", ""))
        messages.success(request, L("Sent to the CEO.", "تم الإرسال إلى الرئيس التنفيذي."))
    elif action == "follow_up":
        owner = User.objects.filter(pk=request.POST.get("owner") or 0, is_active=True).first()
        ops.update_incident_follow_up(incident, request.user, owner=owner, due=_date(request.POST.get("due")))
        messages.success(request, L("Follow-up saved.", "تم حفظ المتابعة."))
    elif action == "close":
        ops.close_incident(incident, request.user, request.POST.get("note", ""))
        messages.success(request, L("Incident closed.", "تم إغلاق الحادثة."))
    return redirect("desk:incident", pk=pk)


# ---------------------------------------------------------------------------
# Complaints (FRM-10)
# ---------------------------------------------------------------------------
COMPLAINT_AR = {
    "money": "المال أو الفواتير",
    "refund": "استرداد",
    "staff": "سلوك الموظفين",
    "safety": "السلامة",
    "leaving": "يهدد بالمغادرة",
    "classes": "الحصص أو الجدول",
    "facility": "المرافق",
    "other": "أخرى",
}
CHANNEL_AR = {"desk": "الاستقبال", "whatsapp": "واتساب", "saqr": "محادثة صقر", "call": "اتصال هاتفي"}


def _complaints_for(request):
    qs = Complaint.objects.filter(branch=request.branch).select_related("member", "handled_by")
    if not can(request, "ops.manage"):
        qs = qs.filter(handled_by=request.user) | qs.filter(escalated=False)
    return qs


@desk(any_of=["ops.complaint", "ops.manage"])
def complaints(request):
    status = request.GET.get("status", "open")
    qs = _complaints_for(request)
    if status in ("open", "closed"):
        qs = qs.filter(status=status)
    return render(
        request, "desk/ops/complaints.html", {"complaints": qs.order_by("-received_at")[:100], "status": status}
    )


@desk("ops.complaint")
def complaint_new(request):
    member = None
    member_id = request.POST.get("member") or request.GET.get("member")
    if member_id:
        member = visible_members(request.user).filter(pk=member_id).first()
    if request.method == "POST":
        complaint = ops.log_complaint(
            request.branch,
            request.user,
            member=member,
            contact_name=request.POST.get("contact_name", "").strip()[:150],
            contact_mobile=request.POST.get("contact_mobile", "").strip()[:16],
            channel=request.POST.get("channel", "desk"),
            category=request.POST.get("category", "other"),
            details=request.POST.get("details", "").strip(),
            received_at=_dt(request.POST.get("received_at")) or timezone.now(),
        )
        messages.success(
            request,
            L(
                f"Complaint {complaint.reference} logged. Reply within 24 hours.",
                f"تم تسجيل الشكوى {complaint.reference}. الرد خلال 24 ساعة.",
            ),
        )
        return redirect("desk:complaint", pk=complaint.pk)
    return render(
        request,
        "desk/ops/complaint_new.html",
        {
            "member": member,
            "channels": [(v, CHANNEL_AR[v] if lang() == "ar" else label) for v, label in Complaint.Channel.choices],
            "categories": [
                (v, COMPLAINT_AR[v] if lang() == "ar" else label) for v, label in Complaint.Category.choices
            ],
            "escalate": sorted(Complaint.ESCALATE),
            "now": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
            "found": search_members(request.user, request.GET.get("q", "")) if request.GET.get("q") else None,
        },
    )


@desk(any_of=["ops.complaint", "ops.manage"])
def complaint_detail(request, pk):
    complaint = get_object_or_404(Complaint.objects.select_related("member", "handled_by"), pk=pk)
    visible = (
        has_perm(request.user, "ops.manage", complaint.branch_id)
        or complaint.handled_by_id == request.user.pk
        or (has_perm(request.user, "ops.complaint", complaint.branch_id) and not complaint.escalated)
    )
    if not visible:
        raise Http404
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "reply":
            ops.record_reply(complaint, request.user, request.POST.get("note", ""))
            messages.success(request, L("Reply recorded.", "تم تسجيل الرد."))
        elif action == "close":
            ops.close_complaint(
                complaint,
                request.user,
                outcome=request.POST.get("outcome", ""),
                member_informed_at=_dt(request.POST.get("member_informed_at")),
            )
            messages.success(request, L("Complaint closed.", "تم إغلاق الشكوى."))
        return redirect("desk:complaint", pk=pk)
    return render(
        request,
        "desk/ops/complaint.html",
        {
            "c": complaint,
            "category": COMPLAINT_AR.get(complaint.category) if lang() == "ar" else complaint.get_category_display(),
            "now": timezone.localtime().strftime("%Y-%m-%dT%H:%M"),
        },
    )


# ---------------------------------------------------------------------------
# Cover & handover (FRM-11)
# ---------------------------------------------------------------------------
@desk()
def handovers(request):
    mine = Handover.objects.filter(incoming=request.user, status=Handover.Status.OPEN).select_related(
        "outgoing", "branch"
    )
    branch_list = None
    if can(request, "ops.manage"):
        branch_list = Handover.objects.filter(branch=request.branch).select_related("outgoing", "incoming")[:30]
    if not mine and branch_list is None:
        raise PermissionDenied
    return render(request, "desk/ops/handovers.html", {"mine": mine, "branch_list": branch_list})


@desk("ops.manage")
def handover_new(request):
    people = User.objects.filter(is_active=True, staff_profile__isnull=False).order_by("full_name")
    if request.method == "POST":
        outgoing = get_object_or_404(people, pk=request.POST.get("outgoing") or 0)
        incoming = get_object_or_404(people, pk=request.POST.get("incoming") or 0)
        handover = ops.name_cover(
            request.branch,
            request.user,
            outgoing=outgoing,
            incoming=incoming,
            cover_from=_date(request.POST.get("cover_from"), timezone.localdate()),
            cover_to=_date(request.POST.get("cover_to")),
            leaving=request.POST.get("leaving") == "1",
            last_day=_date(request.POST.get("last_day")),
            note=request.POST.get("note", ""),
        )
        messages.success(request, L("Cover named. The incoming person has been told.", "تم تعيين البديل وإبلاغه."))
        return redirect("desk:handover", pk=handover.pk)
    return render(request, "desk/ops/handover_new.html", {"people": people, "today": timezone.localdate()})


@desk()
def handover_detail(request, pk):
    handover = get_object_or_404(Handover.objects.select_related("outgoing", "incoming", "branch", "created_by"), pk=pk)
    if handover.incoming_id != request.user.pk and not has_perm(request.user, "ops.manage", handover.branch_id):
        raise Http404
    if request.method == "POST":
        ops.accept_handover_item(handover, request.user, request.POST.get("code", ""))
        return redirect("desk:handover", pk=pk)
    return render(request, "desk/ops/handover.html", {"h": handover})
