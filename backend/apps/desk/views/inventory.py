"""Inventory, purchasing and stock counts (M8) and online-order fulfilment (M19)."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import F, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.files import content_type_for
from apps.finance.models import Vendor
from apps.inventory import services as inv
from apps.inventory.documents import purchase_order_doc
from apps.inventory.models import (
    Discrepancy,
    PurchaseOrder,
    PurchaseRequest,
    Receipt,
    StockCount,
    StockMovement,
    Transfer,
    VendorQuote,
)
from apps.organization.models import Branch, Program
from apps.rbac.services import has_perm, users_with_perm
from apps.shop.models import (
    CATEGORY_AR,
    BranchStock,
    Category,
    Order,
    Product,
    ProductVariant,
    fulfil_order,
    mark_ready,
)

from ..access import L, can, desk, lang
from .finance import export_doc
from .ops import _date
from .sales import _money

LINES = 8
KIND_AR = {
    "opening": "رصيد افتتاحي",
    "import": "مستورد من مايندبودي",
    "sale": "بيع",
    "free_issue": "صرف مجاني",
    "refund": "مرتجع",
    "receipt": "استلام من مورد",
    "transfer_out": "تحويل صادر",
    "transfer_in": "تحويل وارد",
    "count": "تصحيح الجرد",
    "online": "طلب إلكتروني",
    "adjust": "تصحيح آخر",
}


def _categories():
    return [(v, CATEGORY_AR.get(v, label) if lang() == "ar" else label) for v, label in Category.choices]


def _variants():
    return (
        ProductVariant.objects.filter(is_active=True, product__is_active=True)
        .select_related("product")
        .order_by("product__name_en", "sort_order")
    )


# ---------------------------------------------------------------------------
# Stock on hand and the ledger
# ---------------------------------------------------------------------------
@desk("inventory.view")
def stock(request):
    branch = request.branch
    qs = BranchStock.objects.filter(branch=branch).select_related("variant__product")
    q, category = request.GET.get("q", "").strip(), request.GET.get("category", "")
    if q:
        qs = qs.filter(
            Q(variant__product__name_en__icontains=q)
            | Q(variant__product__name_ar__icontains=q)
            | Q(variant__barcode=q)
        )
    if category:
        qs = qs.filter(variant__product__category=category)
    if request.GET.get("low"):
        qs = qs.filter(variant__reorder_level__gt=0, quantity__lte=F("variant__reorder_level") + F("reserved"))
    if request.GET.get("old"):
        qs = qs.filter(variant__product__old_stock=True)
    rows = list(qs.order_by("variant__product__name_en", "variant__sort_order"))
    return render(
        request,
        "desk/inventory/stock.html",
        {
            "rows": rows,
            "value": inv.stock_value(branch),
            "units": sum(r.quantity for r in rows),
            "categories": _categories(),
            "q": q,
            "category": category,
        },
    )


@desk("inventory.view")
def item(request, pk):
    variant = get_object_or_404(ProductVariant.objects.select_related("product__supplier"), pk=pk)
    branch = request.branch
    if request.method == "POST":
        inv.adjust(
            variant,
            branch,
            int(request.POST.get("quantity") or 0),
            request.user,
            request.POST.get("reason", ""),
            request.POST.get("note", ""),
        )
        messages.success(request, L("Stock corrected.", "تم تصحيح المخزون."))
        return redirect("desk:stock_item", pk=pk)
    return render(
        request,
        "desk/inventory/item.html",
        {
            "v": variant,
            "stocks": BranchStock.objects.filter(variant=variant).select_related("branch"),
            "movements": StockMovement.objects.filter(variant=variant).select_related("branch", "user")[:100],
            "kinds": KIND_AR if lang() == "ar" else dict(StockMovement.Kind.choices),
            "reasons": StockCount.REASONS,
            "can_adjust": can(request, "inventory.approve"),
        },
    )


# ---------------------------------------------------------------------------
# Catalogue (the OM sets products, costs and prices — decision P3-4)
# ---------------------------------------------------------------------------
@desk("inventory.view")
def catalogue(request):
    products = (
        Product.objects.prefetch_related("variants")
        .select_related("supplier", "program")
        .order_by("category", "name_en")
    )
    return render(
        request, "desk/inventory/catalogue.html", {"products": products, "can_edit": can(request, "inventory.approve")}
    )


@desk("inventory.approve")
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    if request.method == "POST":
        p = request.POST
        action = p.get("action", "product")
        if action == "product":
            from django.utils.text import slugify

            name = p.get("name_en", "").strip()
            if not name:
                messages.error(request, L("Enter the product name.", "أدخل اسم المنتج."))
                return redirect(request.get_full_path())
            if product is None:
                base = slugify(name)[:40] or "item"
                slug, i = base, 2
                while Product.objects.filter(slug=slug).exists():
                    slug, i = f"{base}-{i}", i + 1
                product = Product(slug=slug)
            product.name_en, product.name_ar = name[:100], p.get("name_ar", "").strip()[:100]
            product.category = p.get("category") if p.get("category") in Category.values else "other"
            product.price = _money(p.get("price"))
            product.is_sample_price = False
            product.supplier = Vendor.objects.filter(pk=p.get("supplier") or 0).first()
            product.program = Program.objects.filter(pk=p.get("program") or 0).first()
            product.old_stock = p.get("old_stock") == "1"
            product.sell_online = p.get("sell_online") == "1" and product.category != "belts"
            product.is_active = p.get("is_active") == "1"
            product.save()
            for v in product.variants.all():
                inv.refresh_online(v.pk)
            messages.success(request, L("Product saved.", "تم حفظ المنتج."))
        elif action == "variant" and product is not None:
            variant = ProductVariant.objects.filter(
                pk=p.get("variant") or 0, product=product
            ).first() or ProductVariant(product=product, sort_order=product.variants.count())
            variant.size = p.get("size", "").strip()[:20] or "One size"
            variant.colour = p.get("colour", "").strip()[:30]
            variant.barcode = p.get("barcode", "").strip()[:40]
            variant.cost = _money(p.get("cost"))
            variant.retail_price = _money(p.get("retail_price")) if p.get("retail_price") else None
            variant.reorder_level = int(p.get("reorder_level") or 0)
            variant.max_level = int(p.get("max_level") or 0)
            variant.is_active = p.get("is_active") == "1"
            variant.save()
            inv.refresh_online(variant.pk)
            messages.success(request, L("Size saved.", "تم حفظ المقاس."))
        return redirect("desk:product_edit", pk=product.pk)
    return render(
        request,
        "desk/inventory/product.html",
        {
            "product": product,
            "variants": product.variants.all() if product else [],
            "categories": _categories(),
            "vendors": Vendor.objects.filter(is_active=True),
            "programs": Program.objects.filter(is_active=True).select_related("branch"),
        },
    )


# ---------------------------------------------------------------------------
# Purchase requests (FRM-05)
# ---------------------------------------------------------------------------
PURCHASING = ["inventory.manage", "inventory.purchase", "inventory.approve"]


@desk(any_of=PURCHASING)
def requests(request):
    qs = PurchaseRequest.objects.select_related("branch", "created_by", "decided_by").prefetch_related("lines")
    if not (can(request, "inventory.approve") or can(request, "inventory.purchase")):
        qs = qs.filter(branch=request.branch)
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    return render(request, "desk/inventory/requests.html", {"requests": qs[:100], "status": status})


def _lines_from_post(p):
    out = []
    for i in range(LINES):
        qty = int(p.get(f"qty_{i}") or 0)
        if not qty:
            continue
        variant = ProductVariant.objects.filter(pk=p.get(f"variant_{i}") or 0).first()
        out.append(
            {
                "variant": variant,
                "item": p.get(f"item_{i}", ""),
                "size": p.get(f"size_{i}", ""),
                "quantity": qty,
                "reason": p.get(f"reason_{i}", ""),
            }
        )
    return out


@desk("inventory.manage")
def request_new(request):
    if request.method == "POST":
        req = inv.submit_request(
            request.branch,
            request.user,
            vendor_type=request.POST.get("vendor_type", "local"),
            vendor=Vendor.objects.filter(pk=request.POST.get("vendor") or 0).first(),
            lines=_lines_from_post(request.POST),
            note=request.POST.get("note", ""),
        )
        messages.success(request, L(f"{req.reference} sent to the OM.", f"أُرسل {req.reference} إلى مدير العمليات."))
        return redirect("desk:purchase_request", pk=req.pk)
    prefill = []
    if request.GET.get("suggest"):
        prefill = [
            {"variant": s["variant"], "qty": s["suggest"], "reason": L("Low stock", "مخزون منخفض")}
            for s in inv.reorder_suggestions(request.branch)
        ][:LINES]
    rows = prefill + [{} for _ in range(LINES - len(prefill))]
    return render(
        request,
        "desk/inventory/request_new.html",
        {"rows": rows, "variants": _variants(), "vendors": Vendor.objects.filter(is_active=True)},
    )


@desk(any_of=PURCHASING)
def request_detail(request, pk):
    req = get_object_or_404(
        PurchaseRequest.objects.select_related("branch", "created_by", "decided_by", "vendor"), pk=pk
    )
    if not any(has_perm(request.user, p, req.branch_id) for p in PURCHASING):
        raise Http404
    if request.method == "POST":
        amended = {ln.pk: request.POST.get(f"approve_{ln.pk}", ln.quantity) for ln in req.lines.all()}
        inv.decide_request(req, request.user, request.POST.get("decision", ""), request.POST.get("note", ""), amended)
        messages.success(request, L("Decision saved; the branch has been told.", "تم حفظ القرار وإبلاغ الفرع."))
        return redirect("desk:purchase_request", pk=pk)
    return render(
        request,
        "desk/inventory/request.html",
        {
            "r": req,
            "lines": req.lines.select_related("variant__product"),
            "can_decide": can(request, "inventory.approve"),
        },
    )


@desk("inventory.manage")
def reorder(request):
    return render(request, "desk/inventory/reorder.html", {"rows": inv.reorder_suggestions(request.branch)})


# ---------------------------------------------------------------------------
# Purchase orders, landed cost, receiving
# ---------------------------------------------------------------------------
@desk(any_of=["inventory.purchase", "inventory.approve"])
def orders(request):
    if request.method == "POST":
        if not can(request, "inventory.purchase"):
            raise PermissionDenied
        vendor = get_object_or_404(Vendor, pk=request.POST.get("vendor") or 0)
        reqs = PurchaseRequest.objects.filter(pk__in=request.POST.getlist("requests"))
        order = inv.create_order(
            request.user,
            vendor,
            reqs,
            currency=request.POST.get("currency") or vendor.currency,
            exchange_rate=request.POST.get("exchange_rate") or 1,
            language=request.POST.get("language", "ar"),
        )
        messages.success(
            request,
            L(
                f"{order.reference} created. Enter the vendor's prices, then send it.",
                f"تم إنشاء {order.reference}. أدخل أسعار المورد ثم أرسله.",
            ),
        )
        return redirect("desk:purchase_order", pk=order.pk)
    return render(
        request,
        "desk/inventory/orders.html",
        {
            "orders": PurchaseOrder.objects.select_related("vendor").prefetch_related("requests")[:60],
            "ready": PurchaseRequest.objects.filter(status__in=PurchaseRequest.OPEN_FOR_ORDER).select_related("branch"),
            "vendors": Vendor.objects.filter(is_active=True),
        },
    )


@desk(any_of=["inventory.purchase", "inventory.approve"])
def order_detail(request, pk):
    order = get_object_or_404(PurchaseOrder.objects.select_related("vendor"), pk=pk)
    rows = inv.landed_costs(order)
    if request.GET.get("format"):
        doc_lang = request.GET.get("lang") or order.language
        from apps.reports.export import render as render_doc

        from .finance import download

        content, ctype, ext = render_doc(purchase_order_doc(order, rows, doc_lang), request.GET["format"], doc_lang)
        return download(content, ctype, f"{order.reference}-{doc_lang}.{ext}")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save":
            prices = {ln.pk: _money(request.POST.get(f"price_{ln.pk}") or 0) for ln in order.lines.all()}
            inv.update_order(
                order,
                request.user,
                prices=prices,
                currency=request.POST.get("currency"),
                exchange_rate=request.POST.get("exchange_rate"),
                freight_kwd=request.POST.get("freight_kwd"),
                customs_percent=request.POST.get("customs_percent"),
                target_margin=request.POST.get("target_margin"),
                language=request.POST.get("language"),
                note=request.POST.get("note"),
            )
            messages.success(request, L("Saved. Landed costs recalculated.", "تم الحفظ وإعادة حساب التكلفة."))
        elif action == "send":
            inv.send_order(order, request.user)
            messages.success(
                request,
                L("Marked as sent. Download the order for the vendor.", "تم تسجيل الإرسال. نزّل أمر الشراء للمورد."),
            )
        return redirect("desk:purchase_order", pk=pk)
    return render(
        request,
        "desk/inventory/order.html",
        {
            "o": order,
            "rows": rows,
            "totals": inv.order_totals(order),
            "editable": order.status == "draft" and can(request, "inventory.purchase"),
            "receipts": order.receipts.all(),
        },
    )


@desk("inventory.purchase")
def receive(request):
    order = PurchaseOrder.objects.filter(pk=request.GET.get("order") or request.POST.get("order") or 0).first()
    if request.method == "POST":
        p = request.POST
        lines = []
        if order is not None:
            for ln in order.lines.select_related("variant"):
                if ln.variant_id:
                    lines.append(
                        {
                            "variant": ln.variant,
                            "order_line": ln,
                            "invoiced": int(p.get(f"inv_{ln.pk}") or 0),
                            "received": int(p.get(f"rec_{ln.pk}") or 0),
                            "note": p.get(f"note_{ln.pk}", ""),
                        }
                    )
        for i in range(LINES):
            v = ProductVariant.objects.filter(pk=p.get(f"variant_{i}") or 0).first()
            if v is not None:
                lines.append(
                    {"variant": v, "invoiced": int(p.get(f"inv_x{i}") or 0), "received": int(p.get(f"rec_x{i}") or 0)}
                )
        vendor = order.vendor if order else get_object_or_404(Vendor, pk=p.get("vendor") or 0)
        receipt = inv.receive(
            request.user,
            vendor=vendor,
            invoice_number=p.get("invoice_number", ""),
            lines=lines,
            order=order,
            invoice_file=request.FILES.get("invoice"),
            received_on=_date(p.get("received_on"), timezone.localdate()),
            note=p.get("note", ""),
        )
        messages.success(
            request,
            L(
                f"{receipt.reference} recorded; stock added at Promenade.",
                f"تم تسجيل {receipt.reference} وإضافة المخزون في البروميناد.",
            ),
        )
        return redirect("desk:receipt", pk=receipt.pk)
    return render(
        request,
        "desk/inventory/receive.html",
        {
            "order": order,
            "order_lines": order.lines.select_related("variant__product") if order else [],
            "open_orders": PurchaseOrder.objects.filter(status__in=["sent", "partial"]).select_related("vendor"),
            "vendors": Vendor.objects.filter(is_active=True),
            "variants": _variants(),
            "extra": range(3 if order else LINES),
            "today": timezone.localdate(),
        },
    )


@desk(any_of=["inventory.purchase", "inventory.approve", "inventory.manage"])
def receipts(request):
    return render(
        request,
        "desk/inventory/receipts.html",
        {
            "receipts": Receipt.objects.select_related("vendor", "order", "received_by").prefetch_related("lines")[:60],
            "discrepancies": Discrepancy.objects.filter(status="open").select_related("receipt__vendor"),
        },
    )


@desk(any_of=["inventory.purchase", "inventory.approve", "inventory.manage"])
def receipt_detail(request, pk):
    receipt = get_object_or_404(Receipt.objects.select_related("vendor", "order", "received_by"), pk=pk)
    disc = getattr(receipt, "discrepancy", None)
    if request.method == "POST" and disc is not None:
        inv.update_discrepancy(
            disc,
            request.user,
            vendor_notified_on=_date(request.POST.get("vendor_notified_on")),
            resolution=request.POST.get("resolution", ""),
            resolve=request.POST.get("resolve") == "1",
        )
        return redirect("desk:receipt", pk=pk)
    return render(
        request,
        "desk/inventory/receipt.html",
        {
            "r": receipt,
            "lines": receipt.lines.select_related("variant__product"),
            "disc": disc,
            "transfers": receipt.transfers.all(),
        },
    )


@desk(any_of=["inventory.purchase", "inventory.approve", "inventory.manage"])
def receipt_invoice(request, pk):
    receipt = get_object_or_404(Receipt, pk=pk)
    if not receipt.invoice:
        raise Http404
    return FileResponse(receipt.invoice.open("rb"), content_type=content_type_for(receipt.invoice.name))


# ---------------------------------------------------------------------------
# Transfers (FRM-03)
# ---------------------------------------------------------------------------
@desk(any_of=["inventory.manage", "inventory.purchase"])
def transfers(request):
    branch = request.branch
    qs = Transfer.objects.filter(Q(from_branch=branch) | Q(to_branch=branch)).select_related(
        "from_branch", "to_branch", "sent_by", "accepted_by"
    )
    return render(request, "desk/inventory/transfers.html", {"transfers": qs[:60]})


@desk(any_of=["inventory.manage", "inventory.purchase"])
def transfer_new(request):
    branch = request.branch
    if request.method == "POST":
        lines = []
        for i in range(LINES):
            v = ProductVariant.objects.filter(pk=request.POST.get(f"variant_{i}") or 0).first()
            if v is not None:
                lines.append((v, request.POST.get(f"qty_{i}") or 0))
        to = get_object_or_404(Branch, pk=request.POST.get("to_branch") or 0)
        receipt = Receipt.objects.filter(pk=request.POST.get("receipt") or 0).first()
        t = inv.send_transfer(branch, to, request.user, lines, receipt=receipt, note=request.POST.get("note", ""))
        messages.success(
            request,
            L(
                f"{t.reference} sent. It moves when the other branch accepts it.",
                f"أُرسل {t.reference}. ينتقل المخزون عند استلام الفرع الآخر.",
            ),
        )
        return redirect("desk:transfer", pk=t.pk)
    return render(
        request,
        "desk/inventory/transfer_new.html",
        {
            "stock": BranchStock.objects.filter(branch=branch, quantity__gt=F("reserved"))
            .select_related("variant__product")
            .order_by("variant__product__name_en"),
            "branches": Branch.objects.filter(is_active=True).exclude(pk=branch.pk),
            "receipts": Receipt.objects.filter(branch=branch).order_by("-received_on")[:10],
            "rows": range(LINES),
        },
    )


@desk(any_of=["inventory.manage", "inventory.purchase"])
def transfer_detail(request, pk):
    t = get_object_or_404(Transfer.objects.select_related("from_branch", "to_branch", "sent_by", "accepted_by"), pk=pk)
    if not any(
        has_perm(request.user, p, b)
        for p in ("inventory.manage", "inventory.purchase")
        for b in (t.from_branch_id, t.to_branch_id)
    ):
        raise Http404
    if request.method == "POST":
        if request.POST.get("action") == "cancel":
            inv.cancel_transfer(t, request.user)
        else:
            received = {ln.pk: request.POST.get(f"rec_{ln.pk}", ln.quantity) for ln in t.lines.all()}
            inv.accept_transfer(
                t,
                request.user,
                received,
                called_sender_and_om=request.POST.get("called") == "1",
                note=request.POST.get("note", ""),
            )
            messages.success(request, L("Accepted. The stock is now yours.", "تم الاستلام وأصبح المخزون لديكم."))
        return redirect("desk:transfer", pk=pk)
    return render(
        request,
        "desk/inventory/transfer.html",
        {
            "t": t,
            "lines": t.lines.select_related("variant__product"),
            "can_accept": t.status == "sent"
            and has_perm(request.user, "inventory.manage", t.to_branch_id)
            and t.sent_by_id != request.user.pk,
        },
    )


# ---------------------------------------------------------------------------
# Monthly count (FRM-08)
# ---------------------------------------------------------------------------
@desk(any_of=["inventory.manage", "inventory.approve"])
def counts(request):
    if request.method == "POST":
        if not can(request, "inventory.approve"):
            raise PermissionDenied
        count = inv.create_count(request.branch, timezone.localdate(), request.user)
        return redirect("desk:stock_count", pk=count.pk)
    return render(
        request,
        "desk/inventory/counts.html",
        {
            "counts": StockCount.objects.filter(branch=request.branch).select_related(
                "counted_by", "recorded_by", "approved_by"
            )[:24],
            "can_start": can(request, "inventory.approve"),
        },
    )


@desk(any_of=["inventory.manage", "inventory.approve"])
def count_detail(request, pk):
    count = get_object_or_404(
        StockCount.objects.select_related("branch", "counted_by", "recorded_by", "approved_by"), pk=pk
    )
    if not any(has_perm(request.user, p, count.branch_id) for p in ("inventory.manage", "inventory.approve")):
        raise Http404
    if request.GET.get("format"):
        rows = [
            (
                ln.variant.product.name_en,
                ln.variant.label,
                ln.system_quantity,
                ln.counted_quantity,
                ln.difference,
                ln.recount_quantity,
                ln.final_quantity,
                ln.reason,
                ln.note,
            )
            for ln in count.lines.select_related("variant__product")
        ]
        doc = {
            "title": f"EA-OPS-FRM-08 — Monthly Count & Variance Sheet · {count.reference}",
            "subtitle": f"{count.branch.name} · {count.month:%B %Y} · due {count.due_date:%d/%m/%Y}",
            "sheet": "FRM-08",
            "blocks": [
                (
                    "table",
                    [
                        "Item",
                        "Size",
                        "System qty",
                        "Physical count",
                        "Difference",
                        "Recount (final)",
                        "Final",
                        "Reason",
                        "Note",
                    ],
                    rows,
                ),
                (
                    "text",
                    "Reason codes: US = Unrecorded sale · UT = Unrecorded transfer · D = Damaged · "
                    "FI = Free issue not entered · EE = Entry error · U = Unknown",
                ),
            ],
        }
        return export_doc(request, doc, f"{count.reference}")
    if request.method == "POST":
        action = request.POST.get("action")
        if action in ("save", "submit"):
            entries = {}
            for ln in count.lines.all():
                entries[ln.pk] = {
                    "counted": request.POST.get(f"c_{ln.pk}", ""),
                    "recount": request.POST.get(f"r_{ln.pk}", ""),
                    "reason": request.POST.get(f"reason_{ln.pk}", ""),
                    "note": request.POST.get(f"n_{ln.pk}", ""),
                }
            inv.save_count(count, request.user, entries)
            if action == "submit":
                from django.contrib.auth import get_user_model

                counter = (
                    get_user_model().objects.filter(pk=request.POST.get("counted_by") or 0, is_active=True).first()
                )
                inv.submit_count(count, request.user, counter)
                messages.success(request, L("Sent to the OM for approval.", "أُرسل لمدير العمليات للاعتماد."))
            else:
                messages.success(request, L("Saved.", "تم الحفظ."))
        elif action == "approve":
            inv.approve_count(count, request.user)
            messages.success(request, L("Approved. Stock corrected.", "تم الاعتماد وتصحيح المخزون."))
        elif action == "return":
            inv.return_count(count, request.user, request.POST.get("note", ""))
        return redirect("desk:stock_count", pk=pk)
    return render(
        request,
        "desk/inventory/count.html",
        {
            "c": count,
            "lines": count.lines.select_related("variant__product"),
            "reasons": StockCount.REASONS,
            "editable": count.status in ("counting", "returned") and can(request, "inventory.manage"),
            "can_approve": count.status == "submitted"
            and can(request, "inventory.approve")
            and request.user.pk not in (count.counted_by_id, count.recorded_by_id),
            "people": users_with_perm("classes.view", count.branch_id)
            .exclude(pk=request.user.pk)
            .order_by("full_name"),
        },
    )


# ---------------------------------------------------------------------------
# Vendors and quotations
# ---------------------------------------------------------------------------
@desk(any_of=["inventory.purchase", "inventory.approve", "finance.manage"])
def vendors(request):
    if request.method == "POST":
        p = request.POST
        if p.get("action") == "quote":
            vendor = get_object_or_404(Vendor, pk=p.get("vendor") or 0)
            quote = VendorQuote(
                vendor=vendor,
                date=_date(p.get("date"), timezone.localdate()),
                description=p.get("description", "")[:255],
                amount=_money(p.get("amount")) if p.get("amount") else None,
                currency=(p.get("currency") or vendor.currency)[:3].upper(),
                valid_until=_date(p.get("valid_until")),
                created_by=request.user,
            )
            if request.FILES.get("document"):
                from apps.core.files import clean_document

                quote.document.save("quote", clean_document(request.FILES["document"]), save=False)
            quote.save()
        else:
            vendor = Vendor.objects.filter(pk=p.get("vendor") or 0).first() or Vendor(created_by=request.user)
            vendor.name = p.get("name", "").strip()[:150] or vendor.name
            vendor.name_ar = p.get("name_ar", "").strip()[:150]
            vendor.vendor_type = p.get("vendor_type", "local")
            vendor.country = p.get("country", "Kuwait")[:60] or "Kuwait"
            vendor.contact = p.get("contact", "")[:200]
            vendor.phone = p.get("phone", "")[:30]
            vendor.email = p.get("email", "")[:254]
            vendor.currency = (p.get("currency") or "KWD")[:3].upper()
            if not vendor.name:
                messages.error(request, L("Enter the vendor's name.", "أدخل اسم المورد."))
                return redirect("desk:vendors")
            vendor.updated_by = request.user
            vendor.save()
        return redirect("desk:vendors")
    return render(
        request,
        "desk/inventory/vendors.html",
        {
            "vendors": Vendor.objects.prefetch_related("quotes", "purchase_orders").order_by("name"),
            "today": timezone.localdate(),
        },
    )


@desk(any_of=["inventory.purchase", "inventory.approve", "finance.manage"])
def quote_document(request, pk):
    quote = get_object_or_404(VendorQuote, pk=pk)
    if not quote.document:
        raise Http404
    return FileResponse(quote.document.open("rb"), content_type=content_type_for(quote.document.name))


# ---------------------------------------------------------------------------
# Online orders to hand over (M19 provision)
# ---------------------------------------------------------------------------
@desk(any_of=["inventory.manage", "sales.sell"])
def online_orders(request):
    branch = request.branch
    qs = (
        Order.objects.filter(status__in=["paid", "ready"])
        .filter(Q(pickup_branch=branch) | Q(items__branch=branch))
        .distinct()
        .prefetch_related("items__branch")
    )
    return render(
        request,
        "desk/inventory/online.html",
        {"orders": qs[:60], "done": Order.objects.filter(status="completed", items__branch=branch).distinct()[:20]},
    )


@require_POST
@desk(any_of=["inventory.manage", "sales.sell"])
def online_fulfil(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if not order.items.filter(branch=request.branch).exists() and order.pickup_branch_id != request.branch.pk:
        raise Http404
    try:
        if request.POST.get("action") == "ready":
            mark_ready(order, request.user)
            messages.success(request, L("Marked ready; the customer has been told.", "جاهز للاستلام وتم إبلاغ العميل."))
        else:
            fulfil_order(order, request.user)
            messages.success(request, L("Handed over. Stock taken off the shelf.", "تم التسليم وخصم المخزون."))
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("desk:online_orders")
