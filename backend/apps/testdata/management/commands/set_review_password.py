"""
Gives every fictional test account (…@test.elite.local) the password in REVIEW_PASSWORD, so the published trial
password never works on a server reachable from the internet. Refuses to run in production.
"""

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError

TEST_DOMAIN = "test.elite.local"


class Command(BaseCommand):
    help = "Set the shared password of the fictional test accounts on the review server."

    def handle(self, *args, **opts):
        if getattr(settings, "ENVIRONMENT", "") == "production":
            raise CommandError("Not on the live system.")
        password = os.environ.get("REVIEW_PASSWORD", "")
        if not password:
            raise CommandError("Set REVIEW_PASSWORD first.")
        validate_password(password)
        users = get_user_model().objects.filter(email__endswith=TEST_DOMAIN)
        for user in users:
            user.set_password(password)
            user.must_change_password = False
            user.save(update_fields=["password", "must_change_password"])
        self.stdout.write(f"Review password set for {users.count()} test accounts.")
