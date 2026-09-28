"""
Website security middleware (ISO 27001 A.5.15, A.8.5, A.8.26).

- /cms/ (Wagtail) is open only to people whose role grants cms.edit, and privileged users
  must have completed two-factor sign-in when MFA is enforced. The Wagtail editor/moderator
  groups follow the RBAC roles on every visit, so ending a role ends CMS access at once.
- Public pages get a Content-Security-Policy: our own scripts, styles, fonts and images only.
"""

from django.conf import settings
from django.contrib.auth.models import Group
from django.http import HttpResponseForbidden
from django.middleware.locale import LocaleMiddleware
from django.shortcuts import redirect

from apps.rbac.services import has_perm, is_mfa_verified, is_privileged

CMS_PREFIX = "/cms/"
PUBLIC_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; frame-src https://www.google.com https://maps.google.com; "
    "form-action 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'"
)
EDITORS, MODERATORS = "Editors", "Moderators"


def sync_cms_groups(user):
    """Wagtail reads Django groups; keep them in step with the user's current RBAC roles."""
    wanted = set()
    if has_perm(user, "cms.edit"):
        wanted.add(EDITORS)
    if has_perm(user, "cms.publish"):
        wanted.add(MODERATORS)
    if wanted and Group.objects.filter(name__in=wanted).count() < len(wanted):
        from .cms_groups import ensure_cms_groups

        ensure_cms_groups()
    current = set(user.groups.filter(name__in=(EDITORS, MODERATORS)).values_list("name", flat=True))
    if current != wanted:
        user.groups.remove(*Group.objects.filter(name__in=current - wanted))
        user.groups.add(*Group.objects.filter(name__in=wanted - current))


class CmsAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(CMS_PREFIX):
            denied = self._check_cms(request)
            if denied is not None:
                return denied
        response = self.get_response(request)
        if not request.path.startswith((CMS_PREFIX, "/api/", "/" + settings.ADMIN_URL.lstrip("/"))):
            response.setdefault("Content-Security-Policy", PUBLIC_CSP)
        return response

    @staticmethod
    def _check_cms(request):
        user = request.user
        if not user.is_authenticated:
            # Wagtail's own login page stays reachable; everything else needs a session.
            if request.path.startswith(CMS_PREFIX + "login/"):
                return None
            return redirect(f"{CMS_PREFIX}login/?next={request.path}")
        if user.is_superuser:
            return None
        if not has_perm(user, "cms.edit"):
            _record_denied(request, "cms.edit")
            return HttpResponseForbidden("Your role does not include website editing.")
        if settings.ENFORCE_PRIVILEGED_MFA and is_privileged(user) and not is_mfa_verified(user):
            _record_denied(request, "mfa")
            return HttpResponseForbidden("Two-factor sign-in is required for the CMS.")
        sync_cms_groups(user)
        return None


def _record_denied(request, reason):
    request._security_events = getattr(request, "_security_events", []) + [
        {"action": "access_denied", "object_type": "cms", "object_id": request.path[:64], "changes": {"reason": reason}}
    ]


class SiteLocaleMiddleware(LocaleMiddleware):
    """
    Django's LocaleMiddleware, except that a 404 outside the website (API, CMS, admin, payment
    return) stays a 404. The CMS catch-all under /en/ would otherwise turn every unknown path,
    such as a member the user may not see, into a redirect.
    """

    NON_SITE = ("/api/", CMS_PREFIX, "/documents/", "/pay/", "/healthz", "/static/", "/media/")

    def process_response(self, request, response):
        admin = "/" + settings.ADMIN_URL.lstrip("/")
        if request.path.startswith(self.NON_SITE + (admin,)):
            return response
        return super().process_response(request, response)
