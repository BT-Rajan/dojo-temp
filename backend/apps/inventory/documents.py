"""Printable purchase order (EA-PO) in Arabic or English, like EA-PO-2026-001."""

from apps.reports.documents import _t


def purchase_order_doc(order, rows, lang="ar") -> dict:
    home = order.requests.first().branch if order.requests.exists() else None
    refs = ", ".join(
        f"{r.reference} – {r.branch.name_ar if lang == 'ar' else r.branch.name}" for r in order.requests.all()
    )
    lines = [
        (
            i,
            (row["line"].variant.product.name_ar or row["line"].variant.product.name_en)
            if lang == "ar" and row["line"].variant_id
            else (row["line"].variant.product.name_en if row["line"].variant_id else row["line"].item),
            row["line"].variant.label if row["line"].variant_id else row["line"].size,
            row["line"].quantity,
            row["line"].unit_price,
            row["line"].unit_price * row["line"].quantity,
        )
        for i, row in enumerate(rows, start=1)
    ]
    total_qty = sum(r["line"].quantity for r in rows)
    total_value = sum((r["line"].unit_price * r["line"].quantity for r in rows), 0)
    vendor = order.vendor
    unit_head = _t(lang, "Unit price", "سعر الوحدة") + f" ({order.currency})"
    total_head = _t(lang, "Total", "الإجمالي") + f" ({order.currency})"
    return {
        "title": _t(lang, "Purchase order", "أمر شراء") + f" · {order.reference}",
        "subtitle": _t(
            lang,
            "Elite Academy of Martial Arts · Kuwait · elitemaacademy.com",
            "أكاديمية إيليت للفنون القتالية · الكويت · elitemaacademy.com",
        ),
        "sheet": "PO",
        "blocks": [
            (
                "table",
                [
                    _t(lang, "Order date", "تاريخ الأمر"),
                    _t(lang, "Vendor", "المورد"),
                    _t(lang, "Contact", "التواصل"),
                    _t(lang, "Request reference", "مرجع الطلب"),
                ],
                [
                    (
                        (order.sent_at or order.created_at).date(),
                        vendor.name_ar if lang == "ar" and vendor.name_ar else vendor.name,
                        vendor.phone or vendor.contact,
                        refs,
                    )
                ],
            ),
            (
                "text",
                _t(
                    lang,
                    "Deliver to: Elite Academy – Promenade branch, Promenade Mall, Hawalli, Kuwait. "
                    "All items in this order are delivered to Promenade.",
                    "عنوان التسليم: أكاديمية إيليت – فرع البروميناد، مجمع البروميناد، حولي، الكويت. "
                    "يرجى تسليم جميع أصناف هذا الطلب إلى فرع البروميناد.",
                ),
            ),
            (
                "table",
                [
                    "#",
                    _t(lang, "Item", "الصنف"),
                    _t(lang, "Size", "المقاس"),
                    _t(lang, "Quantity", "الكمية"),
                    unit_head,
                    total_head,
                ],
                lines,
            ),
            (
                "table",
                [_t(lang, "Total quantity", "إجمالي الكمية"), _t(lang, "Order total", "إجمالي الأمر")],
                [(total_qty, total_value)],
            ),
            ("text", order.note or ""),
            ("text", _t(lang, "Branch requesting: ", "الفرع الطالب: ") + (home.name if home else "")),
        ],
    }
