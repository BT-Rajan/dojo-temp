from django.apps import AppConfig


class SalesConfig(AppConfig):
    name = "apps.sales"
    label = "sales"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import AccountRequest, CashUp, Discount, Membership, Payment, Sale, SaleLine

        for model in (Membership, Sale, SaleLine, Payment, Discount, AccountRequest, CashUp):
            track_changes(model)
