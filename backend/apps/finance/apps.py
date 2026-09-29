from django.apps import AppConfig


class FinanceConfig(AppConfig):
    name = "apps.finance"
    label = "finance"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import Expense, IncomeStatement, Vendor, VendorInvoice

        for model in (Expense, Vendor, VendorInvoice, IncomeStatement):
            track_changes(model)
