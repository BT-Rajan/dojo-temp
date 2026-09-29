"""Members and families: search, register (with consent and signed rules), profile, timeline, card."""

import io

import qrcode
import qrcode.image.svg
from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from apps.audit.services import record_event
from apps.classes import services as classes
from apps.classes.models import Attendance, Booking, ClassSlot, Enrollment
from apps.core.validators import day_range, normalize_kuwait_mobile
from apps.members.models import EmergencyContact, Guardian, GuardianLink, MediaConsent, Member, RulesAgreement
from apps.rbac.services import has_perm
from apps.renewals.models import FollowUp
from apps.sales.models import AccountRequest, Membership, Sale
from apps.sales.services import member_status

from ..access import L, desk
from ..lookup import search_members, visible_members

MAX_PHOTO = 5 * 1024 * 1024


@desk("members.view")
def member_list(request):
    q = request.GET.get("q", "").strip()
    members = (
        search_members(request.user, q, limit=50)
        if q
        else (
            visible_members(request.user)
            .filter(branch=request.branch)
            .select_related("branch")
            .order_by("-joined_on")[:30]
        )
    )
    rows = [(m, member_status(m)) for m in members]
    return render(request, "desk/members/list.html", {"q": q, "rows": rows})


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            "first_name",
            "last_name",
            "first_name_ar",
            "last_name_ar",
            "date_of_birth",
            "gender",
            "nationality",
            "civil_id",
            "mobile",
            "email",
            "area",
            "source",
            "medical_notes",
            "allergies",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "medical_notes": forms.Textarea(attrs={"rows": 2}),
            "allergies": forms.Textarea(attrs={"rows": 2}),
            "civil_id": forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
        }


class RegisterForm(forms.Form):
    guardian_name = forms.CharField(max_length=150, required=False)
    guardian_mobile = forms.CharField(max_length=20, required=False)
    guardian_relationship = forms.ChoiceField(choices=GuardianLink.Relationship.choices, required=False)
    existing_guardian = forms.ModelChoiceField(queryset=Guardian.objects.none(), required=False)
    emergency_name = forms.CharField(max_length=150)
    emergency_relationship = forms.CharField(max_length=60)
    emergency_mobile = forms.CharField(max_length=20)
    consent_internal = forms.BooleanField(required=False)
    consent_social = forms.BooleanField(required=False)
    consent_website = forms.BooleanField(required=False)
    signed_by_name = forms.CharField(max_length=150)
    rules_accepted = forms.BooleanField()
    signature = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["existing_guardian"].queryset = Guardian.objects.all()

    def clean_emergency_mobile(self):
        return normalize_kuwait_mobile(self.cleaned_data["emergency_mobile"])

    def clean_signature(self):
        sig = self.cleaned_data.get("signature", "")
        if sig and (not sig.startswith("data:image/png;base64,") or len(sig) > 200_000):
            raise forms.ValidationError(
                L("The signature could not be read. Please sign again.", "تعذر قراءة التوقيع. يرجى التوقيع مرة أخرى.")
            )
        return sig


@desk("members.create")
def member_new(request):
    form = MemberForm(request.POST or None, prefix="m")
    extra = RegisterForm(request.POST or None, prefix="r")
    if request.method == "POST" and form.is_valid() and extra.is_valid():
        member = form.save(commit=False)
        d = extra.cleaned_data
        if member.is_minor and not (
            d.get("existing_guardian") or (d.get("guardian_name") and d.get("guardian_mobile"))
        ):
            messages.error(
                request,
                L("A child needs a parent or guardian with a mobile number.", "يحتاج الطفل إلى وليّ أمر مع رقم جوال."),
            )
        elif not d.get("signature"):
            messages.error(
                request,
                L("Please sign on the screen to accept the rules.", "يرجى التوقيع على الشاشة للموافقة على القواعد."),
            )
        else:
            member = _register(request, form, d)
            messages.success(request, L(f"{member} registered.", f"تم تسجيل {member}."))
            return redirect("desk:member", pk=member.pk)
    return render(request, "desk/members/new.html", {"form": form, "extra": extra})


@transaction.atomic
def _register(request, form, d):
    user = request.user
    member = form.save(commit=False)
    member.branch = request.branch
    member.created_by = member.updated_by = user
    member.full_clean()
    member.save()
    guardian = d.get("existing_guardian")
    if guardian is None and d.get("guardian_name"):
        guardian = Guardian(full_name=d["guardian_name"], mobile=d["guardian_mobile"], created_by=user, updated_by=user)
        guardian.full_clean()
        guardian.save()
    if guardian is not None:
        GuardianLink.objects.create(
            guardian=guardian, member=member, relationship=d.get("guardian_relationship") or "guardian", is_primary=True
        )
    EmergencyContact.objects.create(
        member=member, name=d["emergency_name"], relationship=d["emergency_relationship"], mobile=d["emergency_mobile"]
    )
    MediaConsent.objects.create(
        member=member,
        internal_records=d["consent_internal"],
        social_media=d["consent_social"],
        website_marketing=d["consent_website"],
        signed_by_name=d["signed_by_name"],
        recorded_by=user,
    )
    RulesAgreement.objects.create(
        member=member, signed_by_name=d["signed_by_name"], signature=d["signature"], recorded_by=user
    )
    record_event(action="member_registered", instance=member, branch_id=member.branch_id)
    return member


def timeline(member, user, limit=60):
    """Membership history, visits, payments, requests and follow-ups on one line (scope M2)."""
    items = []
    for m in Membership.objects.filter(member=member).select_related("pricing_option"):
        items.append((day_range(m.start_date)[0], "membership", m))
    for a in Attendance.objects.filter(member=member).select_related("session")[:limit]:
        items.append((a.checked_in_at, "visit", a))
    if has_perm(user, "sales.view", member.branch_id):
        for s in Sale.objects.filter(member=member).select_related("branch")[:limit]:
            items.append((s.created_at, "sale", s))
    for r in AccountRequest.objects.filter(membership__member=member):
        items.append((r.created_at, "request", r))
    for f in FollowUp.objects.filter(member=member).select_related("contacted_by"):
        items.append((f.created_at, "follow_up", f))
    for c in member.media_consents.all():
        items.append((c.signed_at, "consent", c))
    for r in member.rules_agreements.all():
        items.append((r.signed_at, "rules", r))
    return sorted(items, key=lambda x: x[0], reverse=True)[:limit]


@desk("members.view")
def member_detail(request, pk):
    member = get_object_or_404(visible_members(request.user).select_related("branch"), pk=pk)
    today = timezone.localdate()
    show_medical = has_perm(request.user, "members.view_medical", member.branch_id)
    ctx = {
        "member": member,
        "status": member_status(member),
        "show_medical": show_medical,
        "show_sensitive": has_perm(request.user, "members.view_sensitive", member.branch_id),
        "memberships": Membership.objects.filter(member=member)
        .select_related("pricing_option", "branch")
        .prefetch_related("freezes", "requests"),
        "enrollments": Enrollment.objects.filter(member=member).select_related("slot", "slot__branch"),
        "bookings": Booking.objects.filter(member=member, session__date__gte=today)
        .exclude(status="cancelled")
        .select_related("session"),
        "guardians": member.guardian_links.select_related("guardian"),
        "emergency": member.emergency_contacts.all(),
        "consent": member.media_consents.first(),
        "rules": member.rules_agreements.first(),
        "timeline": timeline(member, request.user),
        "slots": ClassSlot.objects.filter(branch=request.branch, is_active=True).order_by("weekday", "start")
        if request.branch
        else [],
        "can_edit": has_perm(request.user, "members.update", member.branch_id),
    }
    return render(request, "desk/members/detail.html", ctx)


@desk("members.update")
def member_edit(request, pk):
    member = get_object_or_404(visible_members(request.user), pk=pk)
    if not has_perm(request.user, "members.update", member.branch_id):
        raise PermissionDenied
    form = MemberForm(request.POST or None, instance=member, prefix="m")
    if not has_perm(request.user, "members.view_medical", member.branch_id):
        for f in ("medical_notes", "allergies"):
            form.fields.pop(f)
    if not has_perm(request.user, "members.view_sensitive", member.branch_id):
        form.fields.pop("civil_id")
    if request.method == "POST" and form.is_valid():
        m = form.save(commit=False)
        m.updated_by = request.user
        m.version += 1
        m.save()
        messages.success(request, L("Saved.", "تم الحفظ."))
        return redirect("desk:member", pk=member.pk)
    return render(request, "desk/members/edit.html", {"form": form, "member": member})


@require_POST
@desk("members.update")
def member_photo(request, pk):
    member = get_object_or_404(visible_members(request.user), pk=pk)
    upload = request.FILES.get("photo")
    if (
        upload is None
        or upload.size > MAX_PHOTO
        or upload.content_type not in ("image/jpeg", "image/png", "image/webp")
    ):
        messages.error(
            request, L("Choose a JPG, PNG or WebP photo under 5 MB.", "اختر صورة JPG أو PNG أو WebP أقل من 5 ميغابايت.")
        )
        return redirect("desk:member", pk=pk)
    from PIL import Image

    image = Image.open(upload)
    image.thumbnail((600, 600))
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "JPEG", quality=85)  # re-encoded: strips location data and anything hidden
    from django.core.files.base import ContentFile

    if member.photo:
        member.photo.delete(save=False)
    member.photo.save("photo.jpg", ContentFile(buf.getvalue()), save=False)
    member.updated_by = request.user
    member.save(update_fields=["photo", "updated_by", "updated_at"])
    record_event(action="member_photo_updated", instance=member, branch_id=member.branch_id)
    messages.success(request, L("Photo saved.", "تم حفظ الصورة."))
    return redirect("desk:member", pk=pk)


@desk(any_of=["members.view", "classes.checkin"])
def member_photo_file(request, pk):
    """Photos are served only through this view, to staff who may see the member."""
    member = Member.objects.filter(pk=pk).first()
    if member is None or not member.photo:
        raise Http404
    if not (
        has_perm(request.user, "members.view", member.branch_id)
        or has_perm(request.user, "classes.checkin", member.branch_id)
    ):
        raise PermissionDenied
    response = FileResponse(member.photo.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=300"
    return response


@desk("members.view")
def member_card(request, pk):
    member = get_object_or_404(visible_members(request.user), pk=pk)
    buf = io.BytesIO()
    qrcode.make(member.qr_token, image_factory=qrcode.image.svg.SvgPathImage, box_size=10).save(buf)
    svg = mark_safe(buf.getvalue().decode())  # noqa: S308  # nosec B308 B703 - SVG drawn by the qrcode library
    return render(request, "desk/members/card.html", {"member": member, "qr": svg})


@require_POST
@desk("members.manage_consent")
def member_consent(request, pk):
    member = get_object_or_404(visible_members(request.user), pk=pk)
    MediaConsent.objects.create(
        member=member,
        internal_records=bool(request.POST.get("internal")),
        social_media=bool(request.POST.get("social")),
        website_marketing=bool(request.POST.get("website")),
        signed_by_name=request.POST.get("signed_by_name", "").strip() or str(member),
        recorded_by=request.user,
        notes=request.POST.get("notes", "")[:255],
    )
    record_event(action="consent_updated", instance=member, branch_id=member.branch_id)
    messages.success(
        request,
        L(
            "Consent updated. Photos follow the new choice at once.",
            "تم تحديث الموافقة. تتبع الصور الاختيار الجديد فوراً.",
        ),
    )
    return redirect("desk:member", pk=pk)


@require_POST
@desk("classes.book")
def member_enroll(request, pk):
    member = get_object_or_404(visible_members(request.user), pk=pk)
    slot = get_object_or_404(ClassSlot, pk=request.POST.get("slot"))
    classes.enroll(member, slot, request.user)
    classes.generate_sessions(slots=ClassSlot.objects.filter(pk=slot.pk))
    messages.success(
        request,
        L(
            f"{member} is now a regular in {slot.title_en}.",
            f"أصبح {member} منتظماً في {slot.title_ar or slot.title_en}.",
        ),
    )
    return redirect("desk:member", pk=pk)


@require_POST
@desk("classes.book")
def member_unenroll(request, pk, enrollment_id):
    enrollment = get_object_or_404(Enrollment, pk=enrollment_id, member_id=pk)
    classes.end_enrollment(enrollment, request.user)
    messages.success(request, L("Regular place ended.", "تم إنهاء المكان المنتظم."))
    return redirect("desk:member", pk=pk)


@require_POST
@desk("members.deactivate")
def member_deactivate(request, pk):
    member = get_object_or_404(visible_members(request.user), pk=pk)
    member.is_active = not member.is_active
    member.updated_by = request.user
    member.save(update_fields=["is_active", "updated_by", "updated_at"])
    record_event(
        action="member_reactivated" if member.is_active else "member_deactivated",
        instance=member,
        branch_id=member.branch_id,
    )
    return redirect("desk:member", pk=pk)
