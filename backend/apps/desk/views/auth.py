"""Desk sign-in (email + password, then the authenticator code when the user has one)."""

import io

import qrcode
import qrcode.image.svg
from django import forms
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, password_validation, update_session_auth_hash
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.audit.services import record_event

from ..access import SESSION_BRANCH, L, allowed_branches, desk


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    otp_token = forms.CharField(required=False, max_length=8)


def _safe_next(request, fallback="desk:home"):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return redirect(fallback).url


def login_view(request):
    form = LoginForm(request.POST or None)
    need_code = False
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower()
        user = authenticate(request, username=email, password=form.cleaned_data["password"])
        if getattr(request, "axes_locked_out", False):
            record_event(action="login_locked_out", object_type="User", object_id=email)
            messages.error(
                request,
                L(
                    "Too many failed attempts. Try again in 15 minutes or contact Systems & IT.",
                    "محاولات كثيرة. حاول بعد 15 دقيقة أو تواصل مع قسم الأنظمة.",
                ),
            )
        elif user is None:
            record_event(action="login_failed", object_type="User", object_id=email)
            messages.error(request, L("Email or password is not correct.", "البريد أو كلمة المرور غير صحيحة."))
        else:
            device = TOTPDevice.objects.devices_for_user(user, confirmed=True).first()
            token = form.cleaned_data.get("otp_token") or ""
            if device is not None and not token:
                need_code = True
            elif device is not None and not device.verify_token(token):
                need_code = True
                record_event(action="login_failed_otp", object_type="User", object_id=str(user.pk), actor=user)
                messages.error(request, L("The code is not correct.", "الرمز غير صحيح."))
            else:
                login(request, user)
                if device is not None:
                    otp_login(request, device)
                record_event(action="login", object_type="User", object_id=str(user.pk), actor=user)
                return redirect(_safe_next(request))
    return render(
        request, "desk/login.html", {"form": form, "need_code": need_code, "next": request.GET.get("next", "")}
    )


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        record_event(action="logout", object_type="User", object_id=str(request.user.pk))
    logout(request)
    return redirect("desk:login")


@desk()
def mfa_setup(request):
    """Authenticator enrolment: scan the QR code, type the 6-digit code to confirm."""
    user = request.user
    if request.method == "POST":
        device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if device is not None and device.verify_token(request.POST.get("otp_token", "")):
            TOTPDevice.objects.filter(user=user, confirmed=True).delete()
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            otp_login(request, device)
            record_event(action="mfa_enabled", object_type="User", object_id=str(user.pk))
            messages.success(request, L("Two-factor sign-in is on.", "تم تفعيل التحقق بخطوتين."))
            return redirect("desk:home")
        messages.error(request, L("The code is not correct. Try the newest code.", "الرمز غير صحيح. جرّب أحدث رمز."))
    device = TOTPDevice.objects.filter(user=user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(user=user, name="Authenticator app", confirmed=False)
    buf = io.BytesIO()
    qrcode.make(device.config_url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8).save(buf)
    svg = mark_safe(buf.getvalue().decode())  # noqa: S308  # nosec B308 B703 - SVG drawn by the qrcode library
    return render(request, "desk/mfa_setup.html", {"qr": svg})


class PasswordForm(forms.Form):
    current = forms.CharField(widget=forms.PasswordInput)
    new = forms.CharField(widget=forms.PasswordInput)
    confirm = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        if not self.user.check_password(data.get("current", "")):
            raise forms.ValidationError(L("Your current password is not correct.", "كلمة المرور الحالية غير صحيحة."))
        if data.get("new") != data.get("confirm"):
            raise forms.ValidationError(L("The new passwords don't match.", "كلمتا المرور الجديدتان غير متطابقتين."))
        password_validation.validate_password(data.get("new", ""), self.user)
        return data


@desk()
def change_password(request):
    form = PasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = request.user
        user.set_password(form.cleaned_data["new"])
        user.must_change_password = False
        user.save()
        update_session_auth_hash(request, user)
        record_event(action="password_changed", object_type="User", object_id=str(user.pk))
        messages.success(request, L("Password changed.", "تم تغيير كلمة المرور."))
        return redirect("desk:home")
    return render(request, "desk/password.html", {"form": form})


@require_POST
@desk()
def switch_branch(request):
    wanted = int(request.POST.get("branch") or 0)
    if allowed_branches(request.user).filter(pk=wanted).exists():
        request.session[SESSION_BRANCH] = wanted
    return redirect(_safe_next(request))
