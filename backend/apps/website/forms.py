"""Book-a-trial and contact forms embedded in CMS pages (POST to the page itself)."""

from django import forms
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.utils.translation import get_language

from apps.audit.services import record_event
from apps.core.middleware import client_ip
from apps.core.validators import normalize_kuwait_mobile
from apps.organization.models import Branch

MESSAGES = {
    "mobile": ("Please enter an 8-digit Kuwaiti number.", "يرجى إدخال رقم كويتي من 8 أرقام."),
    "name": ("Please tell us your name.", "يرجى كتابة اسمك."),
    "branch": ("Please choose a branch.", "يرجى اختيار الفرع."),
    "message": ("Please write your message.", "يرجى كتابة رسالتك."),
    "busy": (
        "Too many requests from this connection. Please try again in a few minutes or WhatsApp us.",
        "طلبات كثيرة من هذا الاتصال. حاول بعد دقائق أو راسلنا عبر واتساب.",
    ),
}


def msg(key, lang):
    en, ar = MESSAGES[key]
    return ar if lang == "ar" else en


class BaseWebForm(forms.Form):
    website = forms.CharField(required=False)  # honeypot: humans never fill this in

    def __init__(self, *args, lang="en", **kwargs):
        self.lang = lang
        super().__init__(*args, **kwargs)

    def clean_mobile(self):
        try:
            return normalize_kuwait_mobile(self.cleaned_data.get("mobile", ""))
        except ValidationError as exc:
            raise ValidationError(msg("mobile", self.lang)) from exc

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise ValidationError(msg("name", self.lang))
        return name

    @property
    def is_spam(self):
        return bool(self.data.get("website"))


class TrialForm(BaseWebForm):
    name = forms.CharField(max_length=120, required=False)
    mobile = forms.CharField(max_length=20, required=False)
    branch = forms.CharField(required=False)
    program = forms.CharField(required=False)
    source = forms.CharField(required=False, max_length=40)

    def clean_branch(self):
        code = self.cleaned_data.get("branch")
        branch = Branch.objects.filter(code=code, is_active=True).first()
        if branch is None:
            raise ValidationError(msg("branch", self.lang))
        return branch

    def clean_program(self):
        from .models import ProgramPage

        value = self.cleaned_data.get("program") or ""
        if value in ("", "unsure"):
            return None
        return ProgramPage.objects.live().filter(pk=value if value.isdigit() else 0).first()


class ContactForm(BaseWebForm):
    name = forms.CharField(max_length=120, required=False)
    mobile = forms.CharField(max_length=20, required=False)
    branch = forms.CharField(required=False)
    message = forms.CharField(max_length=2000, required=False)

    def clean_message(self):
        text = (self.cleaned_data.get("message") or "").strip()
        if not text:
            raise ValidationError(msg("message", self.lang))
        return text


class EventRegistrationForm(BaseWebForm):
    child_first_name = forms.CharField(max_length=60, required=False)
    age = forms.IntegerField(min_value=3, max_value=80, required=False)
    mobile = forms.CharField(max_length=20, required=False)

    def clean_child_first_name(self):
        name = (self.cleaned_data.get("child_first_name") or "").strip()
        if not name:
            raise ValidationError(msg("name", self.lang))
        return name


def _rate_limited(request, kind, limit=8, window=600):
    """Simple per-address limit so the public forms can't be flooded (ISO 27001 A.8.6)."""
    key = f"webform:{kind}:{client_ip(request)}"
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, window)
    return False


def handle_page_form(page, request):
    """Handles a POST to a content page that holds a trial or contact form. Returns a response or None."""
    from django.template.response import TemplateResponse

    from .models import ContactMessage, TrialRequest

    lang = "ar" if get_language() == "ar" else "en"
    kind = request.POST.get("form")
    if kind not in ("trial", "contact"):
        return None
    form_class = TrialForm if kind == "trial" else ContactForm
    form = form_class(request.POST, lang=lang)

    if _rate_limited(request, kind):
        form.is_valid()
        form.add_error(None, msg("busy", lang))
    elif form.is_valid():
        if form.is_spam:
            return HttpResponseRedirect(f"{page.url}?sent={kind}")
        data = form.cleaned_data
        if kind == "trial":
            item = TrialRequest.objects.create(
                name=data["name"],
                mobile=data["mobile"],
                branch=data["branch"],
                program=data["program"],
                not_sure=data["program"] is None,
                language=lang,
                source=data.get("source") or "website",
                source_path=request.path[:255],
            )
            record_event(action="trial_requested", instance=item, changes={"branch": data["branch"].code})
            # Shown on the confirmation screen only (first name, branch, program — no phone number).
            request.session["last_trial"] = {
                "name": data["name"].split()[0],
                "branch": data["branch"].code,
                "program": data["program"].pk if data["program"] else None,
            }
        else:
            branch = Branch.objects.filter(code=data.get("branch") or "").first()
            item = ContactMessage.objects.create(
                name=data["name"], mobile=data["mobile"], branch=branch, message=data["message"], language=lang
            )
            record_event(action="contact_message", instance=item)
        return HttpResponseRedirect(f"{page.url}?sent={kind}#{kind}")

    context = page.get_context(request)
    context[f"{kind}_form"] = form
    return TemplateResponse(request, page.get_template(request), context)


def handle_event_registration(page, request):
    """'Reserve a place' on an event page. Returns a response, or None to show the page."""
    from django.template.response import TemplateResponse

    from .models import EventRegistration

    lang = "ar" if get_language() == "ar" else "en"
    form = EventRegistrationForm(request.POST, lang=lang)
    if page.is_past or page.is_full or not page.accepts_registrations:
        return None
    if _rate_limited(request, "event"):
        form.is_valid()
        form.add_error(None, msg("busy", lang))
    elif form.is_valid():
        if not form.is_spam:
            data = form.cleaned_data
            item = EventRegistration.objects.create(
                event=page,
                child_first_name=data["child_first_name"],
                age=data.get("age"),
                mobile=data["mobile"],
                language=lang,
            )
            record_event(action="event_registration", instance=item, branch_id=page.branch_id)
        return HttpResponseRedirect(f"{page.url}?sent=event#reserve")
    context = page.get_context(request)
    context["event_form"] = form
    context["event_errors"] = {("form" if k == "__all__" else k): v[0] for k, v in form.errors.items()}
    return TemplateResponse(request, page.get_template(request), context)
