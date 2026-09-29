from django.apps import AppConfig


class ClassesConfig(AppConfig):
    name = "apps.classes"
    label = "classes"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import Attendance, Booking, ClassChange, ClassSession, ClassSlot, Enrollment

        for model in (ClassSlot, ClassSession, Enrollment, Booking, Attendance, ClassChange):
            track_changes(model)
