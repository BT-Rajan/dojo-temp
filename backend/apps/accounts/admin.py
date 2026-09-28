from django.contrib import admin

from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["email", "full_name", "mobile", "is_active", "is_staff", "date_joined"]
    search_fields = ["email", "full_name", "mobile"]
    list_filter = ["is_active", "is_staff"]
    readonly_fields = ["password", "last_login", "password_changed_at", "deactivated_at", "date_joined"]
    exclude = ["security_stamp", "groups", "user_permissions"]
