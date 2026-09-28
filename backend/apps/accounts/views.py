import logging

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit.services import record_event
from apps.rbac.services import effective_access, is_mfa_verified, is_privileged

from .serializers import ChangePasswordSerializer, LoginSerializer, MfaConfirmSerializer, UserSummarySerializer

security_log = logging.getLogger("elite.security")


def mfa_required(user) -> bool:
    return bool(settings.ENFORCE_PRIVILEGED_MFA and is_privileged(user))


def confirmed_device(user):
    return TOTPDevice.objects.devices_for_user(user, confirmed=True).first()


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Gives the browser its CSRF cookie before the first login."""

    public = True
    authentication_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")  # login is protected against CSRF too
class LoginView(APIView):
    public = True
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email = data.validated_data["email"].lower()

        user = authenticate(request, username=email, password=data.validated_data["password"])
        if getattr(request, "axes_locked_out", False):
            record_event(action="login_locked_out", object_type="User", object_id=email)
            return Response(
                {"detail": "Too many failed attempts. Try again in 15 minutes or contact Systems & IT."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if user is None:
            record_event(action="login_failed", object_type="User", object_id=email)
            return Response({"detail": "Email or password is not correct."}, status=status.HTTP_401_UNAUTHORIZED)

        device = confirmed_device(user)
        if device is not None:
            token = data.validated_data.get("otp_token") or ""
            if not token:
                return Response(
                    {"detail": "Enter the 6-digit code from your authenticator app.", "otp_required": True},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if not device.verify_token(token):
                record_event(action="login_failed_otp", object_type="User", object_id=str(user.pk), actor=user)
                return Response(
                    {"detail": "The code is not correct.", "otp_required": True}, status=status.HTTP_401_UNAUTHORIZED
                )

        login(request, user)
        if device is not None:
            otp_login(request, device)
        record_event(action="login", object_type="User", object_id=str(user.pk), actor=user)
        return Response(self._me(request), status=status.HTTP_200_OK)

    @staticmethod
    def _me(request):
        return MeView.payload(request)


class LogoutView(APIView):
    allow_without_mfa = True
    allow_any_authenticated = True

    def post(self, request):
        record_event(action="logout", object_type="User", object_id=str(request.user.pk))
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """Who am I, what may I do, and in which branches — the front end builds its menus from this."""

    allow_without_mfa = True
    allow_any_authenticated = True

    @staticmethod
    def payload(request):
        user = request.user
        access = effective_access(user)
        needs_mfa_setup = mfa_required(user) and not is_mfa_verified(user)
        return {
            "user": UserSummarySerializer(user).data,
            "roles": access.role_summaries,
            "permissions": sorted(access.permissions),
            "mfa_enabled": confirmed_device(user) is not None,
            "mfa_setup_required": needs_mfa_setup,
        }

    def get(self, request):
        return Response(self.payload(request))


class ChangePasswordView(APIView):
    allow_without_mfa = True
    allow_any_authenticated = True

    def post(self, request):
        data = ChangePasswordSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        user = request.user
        user.set_password(data.validated_data["new_password"])
        user.must_change_password = False
        user.save()
        update_session_auth_hash(request, user)  # keep this session, end all others
        record_event(action="password_changed", object_type="User", object_id=str(user.pk))
        return Response(status=status.HTTP_204_NO_CONTENT)


class MfaSetupView(APIView):
    """Starts authenticator-app enrolment; returns the otpauth:// link to show as a QR code."""

    allow_without_mfa = True
    allow_any_authenticated = True

    def post(self, request):
        user = request.user
        TOTPDevice.objects.filter(user=user, confirmed=False).delete()
        device = TOTPDevice.objects.create(user=user, name="Authenticator app", confirmed=False)
        return Response({"otpauth_url": device.config_url})


class MfaConfirmView(APIView):
    allow_without_mfa = True
    allow_any_authenticated = True

    def post(self, request):
        data = MfaConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
        if device is None or not device.verify_token(data.validated_data["otp_token"]):
            return Response({"detail": "The code is not correct."}, status=status.HTTP_400_BAD_REQUEST)
        TOTPDevice.objects.filter(user=request.user, confirmed=True).delete()
        device.confirmed = True
        device.save(update_fields=["confirmed"])
        otp_login(request, device)
        record_event(action="mfa_enabled", object_type="User", object_id=str(request.user.pk))
        return Response(status=status.HTTP_204_NO_CONTENT)
