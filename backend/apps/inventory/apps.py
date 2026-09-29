from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = "apps.inventory"
    label = "inventory"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import PurchaseOrder, PurchaseRequest, Receipt, StockCount, Transfer, VendorQuote

        for model in (PurchaseRequest, PurchaseOrder, Receipt, Transfer, StockCount, VendorQuote):
            track_changes(model)
