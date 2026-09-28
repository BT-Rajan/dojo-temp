from django.apps import AppConfig


class ShopConfig(AppConfig):
    name = "apps.shop"
    label = "shop"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import Order, Product, ProductVariant

        for model in (Product, ProductVariant, Order):
            track_changes(model)
