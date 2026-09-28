from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["id", "occurred_at", "actor_label", "action", "object_type", "object_id", "ip_address"]
    list_filter = ["action", "object_type"]
    search_fields = ["actor_label", "object_id", "request_id"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
