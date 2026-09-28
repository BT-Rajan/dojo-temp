from rest_framework.authentication import SessionAuthentication


class CsrfEnforcedSessionAuthentication(SessionAuthentication):
    """
    Server-side sessions (revocable at any time) with CSRF protection on every
    state-changing request. Chosen over long-lived tokens for staff and portal users.
    """
