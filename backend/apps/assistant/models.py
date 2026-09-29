"""
M16 — knowledge base and assistants (decisions P5-11 to P5-13).

- Article         one knowledge-base article in English and Arabic, public or staff-only, with an owner.
- ArticleVersion  every saved version, so an article can be compared or restored.
- Conversation    a SAQR chat (website) or a Staff Assistant session; hand-offs wait in the desk's queue.
- Message         one turn, with the engine that answered and the sources it used.
"""

import hashlib

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class Article(BaseModel):
    class Audience(models.TextChoices):
        PUBLIC = "public", "Public (SAQR and staff)"
        STAFF = "staff", "Staff only"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title_en = models.CharField(max_length=160)
    title_ar = models.CharField(max_length=160, blank=True)
    body_en = models.TextField()
    body_ar = models.TextField(blank=True)
    audience = models.CharField(max_length=6, choices=Audience.choices)
    topic = models.CharField(max_length=60, blank=True, help_text="e.g. Trials, Policies, How to: stock")
    keywords = models.CharField(max_length=255, blank=True, help_text="Extra words people use, comma separated.")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="kb_articles")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["topic", "title_en"]

    def __str__(self):
        return self.title_en

    def title(self, lang):
        return self.title_ar if lang == "ar" and self.title_ar else self.title_en

    def body(self, lang):
        return self.body_ar if lang == "ar" and self.body_ar else self.body_en


class ArticleVersion(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField()
    title_en = models.CharField(max_length=160)
    title_ar = models.CharField(max_length=160, blank=True)
    body_en = models.TextField()
    body_ar = models.TextField(blank=True)
    status = models.CharField(max_length=9)
    saved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    saved_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["article", "version"], name="one_row_per_article_version")]

    def __str__(self):
        return f"{self.article_id} v{self.version}"


def hash_key(value: str) -> str:
    """Browser session keys are stored hashed: the chat is linked to a visitor without keeping their cookie."""
    return hashlib.sha256((value or "").encode()).hexdigest()


class Conversation(models.Model):
    class Channel(models.TextChoices):
        SAQR = "saqr", "SAQR (website)"
        STAFF = "staff", "Staff Assistant"

    channel = models.CharField(max_length=5, choices=Channel.choices)
    session_hash = models.CharField(max_length=64, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assistant_chats"
    )
    branch = models.ForeignKey(
        "organization.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    language = models.CharField(max_length=2, default="en")
    started_at = models.DateTimeField(default=timezone.now)
    last_at = models.DateTimeField(default=timezone.now)
    misses = models.PositiveSmallIntegerField(default=0, help_text="Unresolved exchanges in a row.")
    visitor_name = models.CharField(max_length=120, blank=True)
    visitor_mobile = models.CharField(max_length=16, blank=True)
    handed_off_at = models.DateTimeField(null=True, blank=True)
    handoff_reason = models.CharField(max_length=120, blank=True)
    taken_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    taken_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_ok = models.BooleanField(null=True, blank=True)
    review_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-last_at"]
        indexes = [models.Index(fields=["channel", "handed_off_at"])]

    def __str__(self):
        return f"{self.get_channel_display()} · {self.started_at:%d/%m %H:%M}"

    @property
    def waiting(self):
        return self.handed_off_at is not None and self.taken_at is None


class Message(models.Model):
    class Role(models.TextChoices):
        VISITOR = "visitor", "Visitor / staff"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=9, choices=Role.choices)
    text = models.TextField()
    engine = models.CharField(max_length=10, blank=True, help_text="ai or rules")
    sources = models.JSONField(default=list, blank=True)
    at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["at", "id"]

    def __str__(self):
        return f"{self.role}: {self.text[:40]}"
