from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Permission(models.Model):
    code = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=200)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class Role(models.Model):
    code = models.SlugField(max_length=48, unique=True)
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=255, blank=True)
    # Privileged roles must use two-factor login when enforcement is on (ISO 27001 A.8.2, A.8.5).
    is_privileged = models.BooleanField(default=False)
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RoleAssignmentQuerySet(models.QuerySet):
    def current(self, on=None):
        on = on or timezone.localdate()
        return self.filter(starts_on__lte=on).filter(Q(ends_on__isnull=True) | Q(ends_on__gt=on))


class RoleAssignment(models.Model):
    """
    Gives a user a role, either for every branch (branch empty) or for one branch.
    Assignments have start and end dates so access is time-bound and history is kept.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="assignments")
    branch = models.ForeignKey(
        "organization.Branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="role_assignments",
        help_text="Leave empty for access to all branches.",
    )
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(null=True, blank=True, help_text="First day WITHOUT this access.")
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = RoleAssignmentQuerySet.as_manager()

    class Meta:
        ordering = ["user_id", "role_id"]
        indexes = [models.Index(fields=["user", "ends_on"])]

    def __str__(self):
        scope = self.branch.code if self.branch_id else "all branches"
        return f"{self.user} — {self.role} ({scope})"
