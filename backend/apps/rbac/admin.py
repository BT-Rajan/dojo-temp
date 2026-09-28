from django.contrib import admin

from .models import Permission, Role, RoleAssignment


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["code", "description"]
    search_fields = ["code"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_privileged"]
    filter_horizontal = ["permissions"]


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ["user", "role", "branch", "starts_on", "ends_on", "granted_by"]
    list_filter = ["role", "branch"]
    search_fields = ["user__email", "user__full_name"]
