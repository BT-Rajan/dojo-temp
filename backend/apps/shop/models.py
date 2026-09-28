"""
Online shop (EA-SYS-SCOPE-01 M19): equipment sold from the same stock as the front desk.

Stock is reserved when an order is placed (row-locked, so two parents can't buy the last
pair of gloves at the same moment) and released again if the payment fails.
Belts are never sold online — they are issued at promotion (M7).
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting
from wagtail.models import Orderable
from wagtail.snippets.models import register_snippet

from apps.core.validators import validate_kuwait_mobile


class Category(models.TextChoices):
    GLOVES = "gloves", "Gloves"
    UNIFORMS = "uniforms", "Uniforms"
    SHIN_GUARDS = "shin_guards", "Shin guards"
    HEAD_GUARDS = "head_guards", "Head guards"
    RASH_GUARDS = "rash_guards", "Rash guards"
    TSHIRTS = "tshirts", "T-shirts"


CATEGORY_AR = {
    "gloves": "قفازات",
    "uniforms": "أزياء التدريب",
    "shin_guards": "واقي الساق",
    "head_guards": "واقي الرأس",
    "rash_guards": "راش جارد",
    "tshirts": "تيشيرتات",
}


@register_snippet
class Product(ClusterableModel):
    name_en = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=12, choices=Category.choices)
    price = models.DecimalField(max_digits=8, decimal_places=3, validators=[MinValueValidator(Decimal("0"))])
    is_sample_price = models.BooleanField(default=True, help_text="Untick once the real price is set.")
    description_en = models.TextField(blank=True)
    description_ar = models.TextField(blank=True)
    image = models.ForeignKey("wagtailimages.Image", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    is_active = models.BooleanField(default=True)

    panels = [
        FieldPanel("name_en"),
        FieldPanel("name_ar"),
        FieldPanel("slug"),
        FieldPanel("category"),
        FieldPanel("price"),
        FieldPanel("is_sample_price"),
        FieldPanel("description_en"),
        FieldPanel("description_ar"),
        FieldPanel("image"),
        FieldPanel("is_active"),
        InlinePanel("variants", label="Sizes and stock"),
    ]

    class Meta:
        ordering = ["category", "name_en"]

    def __str__(self):
        return self.name_en

    @property
    def category_ar(self):
        return CATEGORY_AR.get(self.category, "")

    @property
    def total_stock(self):
        return sum(v.stock for v in self.variants.all())

    @property
    def sold_out(self):
        return self.total_stock == 0

    @property
    def few_left(self):
        variants = list(self.variants.all())
        return not self.sold_out and any(v.stock == 0 for v in variants)


class ProductVariant(Orderable):
    product = ParentalKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.CharField(max_length=20, help_text="Gloves in oz (10 oz), uniforms in cm (140 cm), guards XS–XL.")
    stock = models.PositiveIntegerField(default=0)

    panels = [FieldPanel("size"), FieldPanel("stock")]

    class Meta(Orderable.Meta):
        unique_together = [("product", "size")]

    def __str__(self):
        return f"{self.product.name_en} · {self.size}"


@register_snippet
class SizeGuide(ClusterableModel):
    category = models.CharField(max_length=12, choices=Category.choices, unique=True)
    note_en = models.CharField(max_length=160, blank=True, default="Sample guide. Replace with the supplier's chart.")
    note_ar = models.CharField(max_length=160, blank=True, default="دليل توضيحي. يُستبدل بجدول المورّد.")

    panels = [FieldPanel("category"), FieldPanel("note_en"), FieldPanel("note_ar"), InlinePanel("rows", label="Rows")]

    def __str__(self):
        return f"Size guide · {self.get_category_display()}"


class SizeGuideRow(Orderable):
    guide = ParentalKey(SizeGuide, on_delete=models.CASCADE, related_name="rows")
    size = models.CharField(max_length=20)
    measure = models.CharField(max_length=40, help_text="e.g. 30–45 kg or 135–145 cm")
    fits_en = models.CharField(max_length=60)
    fits_ar = models.CharField(max_length=60, blank=True)


@register_setting(icon="tag")
class ShopSettings(BaseGenericSetting):
    delivery_enabled = models.BooleanField(default=True)
    delivery_fee = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("2.000"))
    delivery_days_en = models.CharField(max_length=40, default="1–2 days")
    delivery_days_ar = models.CharField(max_length=40, default="يوم إلى يومين")

    class Meta:
        verbose_name = "Shop settings"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for payment"
        PAID = "paid", "Paid"
        FAILED = "failed", "Payment failed"
        READY = "ready", "Ready for pick-up / out for delivery"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Fulfilment(models.TextChoices):
        PICKUP = "pickup", "Pick up at branch"
        DELIVERY = "delivery", "Delivery"

    class Method(models.TextChoices):
        KNET = "knet", "KNET"
        CARD = "card", "Visa / Mastercard"

    reference = models.CharField(max_length=24, unique=True, editable=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    customer_name = models.CharField(max_length=120)
    mobile = models.CharField(max_length=16, validators=[validate_kuwait_mobile])
    email = models.EmailField(blank=True)
    fulfilment = models.CharField(max_length=8, choices=Fulfilment.choices)
    pickup_branch = models.ForeignKey(
        "organization.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="shop_orders"
    )
    delivery_area = models.CharField(max_length=80, blank=True)
    delivery_address = models.TextField(blank=True)
    payment_method = models.CharField(max_length=4, choices=Method.choices)
    payment_reference = models.CharField(max_length=80, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=3)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=3, default=Decimal("0"))
    total = models.DecimalField(max_digits=10, decimal_places=3)
    language = models.CharField(max_length=2, default="en")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="shop_orders"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = "EA-ORD-" + timezone.now().strftime("%Y%m%d") + "-" + _random_suffix()
        super().save(*args, **kwargs)

    @transaction.atomic
    def mark_paid(self, payment_reference: str):
        order = Order.objects.select_for_update().get(pk=self.pk)
        if order.status != Order.Status.PENDING:
            return order
        order.status = Order.Status.PAID
        order.payment_reference = payment_reference
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "payment_reference", "paid_at"])
        return order

    @transaction.atomic
    def mark_failed(self):
        """Payment failed: release the reserved stock. Safe to call twice."""
        order = Order.objects.select_for_update().get(pk=self.pk)
        if order.status != Order.Status.PENDING:
            return order
        for item in order.items.select_related("variant"):
            if item.variant_id:
                ProductVariant.objects.filter(pk=item.variant_id).update(stock=models.F("stock") + item.quantity)
        order.status = Order.Status.FAILED
        order.save(update_fields=["status"])
        return order


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, null=True, on_delete=models.SET_NULL, related_name="+")
    product_name = models.CharField(max_length=100)
    product_name_ar = models.CharField(max_length=100, blank=True)
    size = models.CharField(max_length=20)
    quantity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=8, decimal_places=3)

    def __str__(self):
        return f"{self.product_name} · {self.size} × {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity


def _random_suffix():
    import secrets

    return secrets.token_hex(3).upper()


class OutOfStock(Exception):
    def __init__(self, variant):
        super().__init__(f"{variant} is out of stock")
        self.variant = variant


@transaction.atomic
def place_order(*, cart_lines, customer, fulfilment, payment_method, delivery_fee, language, user=None):
    """
    Creates the order and reserves stock atomically. `cart_lines` = [(variant_id, qty), …].
    Variants are locked in a fixed order so simultaneous checkouts can't deadlock or oversell.
    """
    variant_ids = sorted({vid for vid, _ in cart_lines})
    variants = {
        v.pk: v
        for v in ProductVariant.objects.select_for_update()
        .filter(pk__in=variant_ids)
        .select_related("product")
        .order_by("pk")
    }
    subtotal = Decimal("0")
    lines = []
    for vid, qty in cart_lines:
        variant = variants.get(vid)
        if variant is None or not variant.product.is_active or variant.stock < qty:
            raise OutOfStock(variant or vid)
        variant.stock -= qty
        variant.save(update_fields=["stock"])
        subtotal += variant.product.price * qty
        lines.append((variant, qty))
    fee = delivery_fee if fulfilment == Order.Fulfilment.DELIVERY else Decimal("0")
    order = Order.objects.create(
        subtotal=subtotal,
        delivery_fee=fee,
        total=subtotal + fee,
        fulfilment=fulfilment,
        payment_method=payment_method,
        language=language,
        user=user,
        **customer,
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                variant=v,
                product_name=v.product.name_en,
                product_name_ar=v.product.name_ar,
                size=v.size,
                quantity=q,
                unit_price=v.product.price,
            )
            for v, q in lines
        ]
    )
    return order
