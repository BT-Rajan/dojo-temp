"""
Mindbody import, parallel run and cut-over (scope Section 6, decisions P3-8 to P3-10).

Every import runs twice: a dry run that does all the work inside a transaction and then rolls it back
(so the report shows exactly what would happen), and — once someone has read the report — the same run
applied for real. Records are matched by their Mindbody ID (ExternalRef), so an import can be repeated
safely: the final delta at cut-over uses the same files and the same screen.
"""

import datetime
import re
from collections import Counter, defaultdict
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify

from apps.audit.services import record_event
from apps.classes.models import Attendance, ClassSession
from apps.core.validators import day_range, normalize_kuwait_mobile
from apps.members.models import EmergencyContact, Guardian, GuardianLink, Member
from apps.organization.models import Branch, PricingOption
from apps.rbac.services import has_perm
from apps.sales.models import Membership, Payment, ReceiptCounter, Sale, SaleLine
from apps.shop.models import Product, ProductVariant

from . import readers as r
from .models import CutoverStep, ExternalRef, ImportBatch, OptionMap, ParallelRunCheck

ZERO = Decimal("0.000")
MAX_ISSUES = 500


def _need(user):
    if not has_perm(user, "data.import"):
        raise PermissionDenied("Only Systems & IT or the Operations Manager import data.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ref(kind, external_id):
    return (
        ExternalRef.objects.filter(kind=kind, external_id=str(external_id)[:120])
        .values_list("object_id", flat=True)
        .first()
    )


def set_ref(kind, external_id, obj):
    ExternalRef.objects.update_or_create(kind=kind, external_id=str(external_id)[:120], defaults={"object_id": obj.pk})


def branch_matcher():
    branches = list(Branch.objects.filter(is_active=True))
    keys = []
    for b in branches:
        words = {
            w.lower()
            for w in re.split(r"\W+", f"{b.name} {b.area}")
            if len(w) > 3 and w.lower() not in ("elite", "academy")
        }
        keys.append((b, words | {b.code.lower()}))

    def match(value, fallback=None):
        value = r.text(value).lower()
        if not value:
            return fallback
        for b, words in keys:
            if any(w in value for w in words):
                return b
        return fallback

    return match


class Result:
    def __init__(self):
        self.counts = Counter()
        self.issues = []
        self.maps = set()  # (Mindbody option name, branch id) still to be mapped — kept even after a dry run

    def issue(self, row, message, level="skip"):
        self.counts[f"issue_{level}"] += 1
        if len(self.issues) < MAX_ISSUES:
            self.issues.append({"row": row, "level": level, "message": message})


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
GENDER = {
    "m": "male",
    "male": "male",
    "ذكر": "male",
    "f": "female",
    "female": "female",
    "أنثى": "female",
    "انثى": "female",
}


def import_clients(rows, batch, user, res):
    match = branch_matcher()
    order = r.date_order([row.get("birth") for row in rows] + [row.get("created") for row in rows])
    seen = defaultdict(list)
    for row in rows:
        n = row["_row"]
        first, last = r.text(row.get("first_name")), r.text(row.get("last_name"))
        if not first and row.get("name"):
            first, last = r.split_name(row.get("name"))
        if not first:
            res.issue(n, "No name.")
            continue
        ext = r.text(row.get("id")) or f"name:{first}|{last}|{r.text(row.get('mobile'))}".lower()
        dob = r.date(row.get("birth"), order)
        gender = GENDER.get(r.text(row.get("gender")).lower())
        branch = match(row.get("location"), batch.branch)
        existing_id = ref("member", ext)
        member = Member.objects.filter(pk=existing_id).first() if existing_id else None
        if member is None:
            if dob is None:
                res.issue(n, f"{first} {last}: no birth date — add it in Mindbody (or register at the desk).")
                continue
            if gender is None:
                res.issue(n, f"{first} {last}: gender missing.")
                continue
            if branch is None:
                res.issue(n, f"{first} {last}: home location not recognised — choose the branch for this file.")
                continue
        mobile = ""
        if r.text(row.get("mobile")):
            try:
                mobile = normalize_kuwait_mobile(r.text(row.get("mobile")))
            except ValidationError:
                res.issue(
                    n,
                    f"{first} {last}: mobile '{r.text(row.get('mobile'))}' is not a Kuwait mobile; left blank.",
                    "warn",
                )
        key = (first.lower(), last.lower(), dob)
        seen[key].append(n)
        if len(seen[key]) == 2:
            res.issue(
                n,
                f"Possible duplicate: {first} {last} also on row {seen[key][0]} — merge in Mindbody or after import.",
                "warn",
            )
        if member is None:
            dup = Member.objects.filter(first_name__iexact=first, last_name__iexact=last, date_of_birth=dob).first()
            if dup is not None:
                res.issue(
                    n, f"{first} {last} looks like member #{dup.pk} already in the system — check and merge.", "warn"
                )
            member = Member(
                branch=branch,
                first_name=first[:80],
                last_name=(last or "-")[:80],
                date_of_birth=dob,
                gender=gender,
                mobile=mobile,
                email=r.text(row.get("email"))[:254],
                source=Member.Source.MINDBODY,
                joined_on=r.date(row.get("created"), order) or timezone.localdate(),
                created_by=user,
                updated_by=user,
            )
            member.save()
            set_ref("member", ext, member)
            res.counts["created"] += 1
        else:
            changed = False
            for field, value in (("mobile", mobile), ("email", r.text(row.get("email"))[:254]), ("date_of_birth", dob)):
                if value and getattr(member, field) != value:
                    setattr(member, field, value)
                    changed = True
            if changed:
                member.updated_by = user
                member.save()
                res.counts["updated"] += 1
            else:
                res.counts["unchanged"] += 1
        ename, ephone = r.text(row.get("emergency_name")), r.text(row.get("emergency_phone"))
        if ename and ephone and not member.emergency_contacts.exists():
            try:
                EmergencyContact.objects.create(
                    member=member,
                    name=ename[:150],
                    relationship=(r.text(row.get("emergency_relationship")) or "—")[:60],
                    mobile=normalize_kuwait_mobile(ephone),
                )
            except ValidationError:
                res.issue(n, f"{first} {last}: emergency contact phone not recognised.", "warn")


# ---------------------------------------------------------------------------
# Relationships → guardians
# ---------------------------------------------------------------------------
def import_relationships(rows, batch, user, res):
    for row in rows:
        n = row["_row"]
        a_id, b_id = ref("member", r.text(row.get("client_id"))), ref("member", r.text(row.get("related_id")))
        a, b = Member.objects.filter(pk=a_id).first(), Member.objects.filter(pk=b_id).first()
        if a is None or b is None:
            res.issue(n, "Both clients must be imported first (Clients file).")
            continue
        if a.is_minor == b.is_minor:
            res.counts["not_family"] += 1  # siblings or two adults: no guardian link needed
            continue
        child, parent = (a, b) if a.is_minor else (b, a)
        if not parent.mobile:
            res.issue(n, f"{parent}: no mobile, so can't be a guardian (messages go to the guardian).")
            continue
        text = r.text(row.get("relationship")).lower()
        relationship = (
            "father" if "father" in text or "أب" in text else "mother" if "mother" in text or "أم" in text else None
        )
        relationship = relationship or ("father" if parent.gender == "male" else "mother")
        guardian = Guardian.objects.filter(mobile=parent.mobile).first()
        if guardian is None:
            guardian = Guardian.objects.create(
                full_name=f"{parent.first_name} {parent.last_name}",
                mobile=parent.mobile,
                email=parent.email,
                created_by=user,
            )
            res.counts["guardians_created"] += 1
        link, created = GuardianLink.objects.get_or_create(
            member=child,
            guardian=guardian,
            defaults={
                "relationship": relationship,
                "is_primary": not child.guardian_links.filter(is_primary=True).exists(),
            },
        )
        res.counts["linked" if created else "unchanged"] += 1


# ---------------------------------------------------------------------------
# Memberships (Pricing Option Expirations)
# ---------------------------------------------------------------------------
def _member_by_name(value):
    first, last = r.split_name(value)
    qs = Member.objects.filter(first_name__iexact=first, last_name__iexact=last)
    return qs.first() if qs.count() == 1 else None


def import_memberships(rows, batch, user, res):
    match = branch_matcher()
    order = r.date_order([row.get("end") for row in rows] + [row.get("start") for row in rows])
    unmapped = set()
    for row in rows:
        n = row["_row"]
        option_name, branch = r.text(row.get("option")), match(row.get("location"), batch.branch)
        if branch is None:
            res.issue(n, "Location not recognised — choose the branch for this file.")
            continue
        mapping = OptionMap.objects.filter(mindbody_name=option_name[:200], branch=branch).first()
        if mapping is None:
            res.maps.add((option_name[:200], branch.pk))
            unmapped.add(f"{option_name} ({branch.code})")
            res.counts["waiting_for_mapping"] += 1
            continue
        if mapping.skip:
            res.counts["skipped_option"] += 1
            continue
        if mapping.pricing_option_id is None:
            unmapped.add(f"{option_name} ({branch.code})")
            res.counts["waiting_for_mapping"] += 1
            continue
        client_ext = r.text(row.get("client_id"))
        member = (
            Member.objects.filter(pk=ref("member", client_ext)).first()
            if client_ext
            else _member_by_name(row.get("client"))
        )
        if member is None:
            res.issue(n, f"Client {client_ext or r.text(row.get('client'))} not found — import the Clients file first.")
            continue
        option = mapping.pricing_option
        end = r.date(row.get("end"), order)
        if end is None:
            res.issue(n, f"{member}: no expiration date.")
            continue
        start = r.date(row.get("start"), order) or end - datetime.timedelta(days=(option.validity_days or 30) - 1)
        remaining = r.integer(row.get("remaining"))
        ext = f"{member.pk}|{option_name.lower()}|{start}"
        existing = Membership.objects.filter(pk=ref("membership", ext)).first()
        values = {
            "member": member,
            "branch": branch,
            "pricing_option": option,
            "start_date": start,
            "end_date": end,
            "sessions_total": option.total_sessions,
            "sessions_used": max((option.total_sessions or 0) - remaining, 0)
            if (remaining is not None and option.total_sessions)
            else 0,
        }
        if existing:
            changed = any(getattr(existing, k) != v for k, v in values.items())
            if changed:
                for k, v in values.items():
                    setattr(existing, k, v)
                existing.updated_by = user
                existing.save()
            res.counts["updated" if changed else "unchanged"] += 1
        else:
            m = Membership.objects.create(created_by=user, updated_by=user, **values)
            set_ref("membership", ext, m)
            res.counts["created"] += 1
    for name in sorted(unmapped):
        res.issue(0, f"Map the pricing option '{name}' (or mark it skipped), then run this file again.", "map")


# ---------------------------------------------------------------------------
# Visits
# ---------------------------------------------------------------------------
def _staff_by_name():
    from django.contrib.auth import get_user_model

    users = get_user_model().objects.filter(staff_profile__isnull=False)
    return {u.full_name.lower(): u for u in users}


def import_visits(rows, batch, user, res):
    match = branch_matcher()
    order = r.date_order([row.get("date") for row in rows])
    staff = _staff_by_name()
    for row in rows:
        n = row["_row"]
        client_ext = r.text(row.get("client_id"))
        member = (
            Member.objects.filter(pk=ref("member", client_ext)).first()
            if client_ext
            else _member_by_name(row.get("client"))
        )
        if member is None:
            res.issue(n, f"Client {client_ext or r.text(row.get('client'))} not found — import Clients first.")
            continue
        day, start = r.date(row.get("date"), order), r.time(row.get("time")) or r.time(row.get("date"))
        if day is None:
            res.issue(n, "No visit date.")
            continue
        start = start or datetime.time(0, 0)
        title = r.text(row.get("class")) or "Class"
        branch = match(row.get("location"), batch.branch or member.branch)
        session_key = f"{branch.pk}|{day}|{start:%H:%M}|{title.lower()}"
        session = ClassSession.objects.filter(pk=ref("session", session_key)).first()
        if session is None:
            end = (datetime.datetime.combine(day, start) + datetime.timedelta(hours=1)).time()
            session = ClassSession.objects.create(
                branch=branch,
                title_en=title[:120],
                date=day,
                start=start,
                end=end,
                capacity=40,
                note="Imported from Mindbody",
                created_by=user,
            )
            coach = staff.get(r.text(row.get("staff")).lower())
            if coach:
                session.instructors.add(coach)
            set_ref("session", session_key, session)
            res.counts["sessions_created"] += 1
        when = timezone.make_aware(datetime.datetime.combine(day, start))
        _, created = Attendance.objects.get_or_create(
            session=session,
            member=member,
            defaults={"method": Attendance.Method.IMPORT, "checked_in_at": when, "created_by": user},
        )
        res.counts["created" if created else "unchanged"] += 1


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------
METHODS = [
    ("knet", ["knet", "debit", "كي نت"]),
    ("card", ["visa", "master", "credit", "card", "amex"]),
    ("cash", ["cash", "نقد"]),
]


def _method(value):
    value = r.text(value).lower()
    for code, words in METHODS:
        if any(w in value for w in words):
            return code
    return None


def import_sales(rows, batch, user, res):
    match = branch_matcher()
    order = r.date_order([row.get("date") for row in rows])
    grouped = defaultdict(list)
    for row in rows:
        key = (
            r.text(row.get("sale_id"))
            or f"{r.text(row.get('date'))}|{r.text(row.get('client_id')) or r.text(row.get('client'))}"
        )
        grouped[key].append(row)
    products = {p.name_en.lower(): p for p in Product.objects.all()}
    for key, lines in sorted(
        grouped.items(), key=lambda kv: (r.date(kv[1][0].get("date"), order) or datetime.date.min, kv[0])
    ):
        n = lines[0]["_row"]
        if ref("sale", key):
            res.counts["unchanged"] += 1
            continue
        day = r.date(lines[0].get("date"), order)
        branch = match(lines[0].get("location"), batch.branch)
        if day is None or branch is None:
            res.issue(n, "Sale date or location missing — choose the branch for this file.")
            continue
        client_ext = r.text(lines[0].get("client_id"))
        member = Member.objects.filter(pk=ref("member", client_ext)).first() if client_ext else None
        items = []
        for ln in lines:
            amount = r.number(ln.get("amount"))
            if amount is None:
                res.issue(ln["_row"], "No amount.")
                continue
            items.append((ln, amount, r.integer(ln.get("quantity")) or 1))
        if not items:
            continue
        total = sum((a for _, a, _ in items), ZERO)
        counter, _ = ReceiptCounter.objects.select_for_update().get_or_create(branch=branch)
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
        when = timezone.make_aware(datetime.datetime.combine(day, r.time(lines[0].get("date")) or datetime.time(12)))
        sale = Sale.objects.create(
            branch=branch,
            number=counter.last_number,
            kind=Sale.Kind.REFUND if total < 0 else Sale.Kind.SALE,
            member=member,
            customer_name="" if member else r.text(lines[0].get("client"))[:150],
            subtotal=total,
            total=total,
            note=f"Imported from Mindbody (sale {key})"[:255],
        )
        Sale.objects.filter(pk=sale.pk).update(created_at=when, updated_at=when)
        for ln, amount, qty in items:
            name = r.text(ln.get("item"))[:200]
            mapping = (
                OptionMap.objects.filter(mindbody_name=name, branch=branch).select_related("pricing_option").first()
            )
            option = mapping.pricing_option if mapping and mapping.pricing_option_id else None
            if option is not None:
                if option.kind == PricingOption.Kind.MEMBERSHIP:
                    earlier = (
                        member is not None and Membership.objects.filter(member=member, start_date__lt=day).exists()
                    )
                    category = SaleLine.Category.RENEW if earlier else SaleLine.Category.NEW
                else:
                    category = {"trial": "trial", "day_pass": "day_pass"}.get(option.kind, "other")  # nosec B105 - a sale category, not a password
            elif name.lower() in products or any(p in name.lower() for p in products):
                category = SaleLine.Category.EQUIPMENT
            else:
                category = SaleLine.Category.OTHER
            SaleLine.objects.create(
                sale=sale,
                pricing_option=option,
                description=name or "Mindbody item",
                category=category,
                quantity=max(qty, 1),
                unit_price=(amount / max(qty, 1)).quantize(Decimal("0.001")),
                line_total=amount,
            )
        method = _method(lines[0].get("method"))
        if method is None:
            res.issue(
                n, f"Payment method '{r.text(lines[0].get('method'))}' not recognised — recorded as card.", "warn"
            )
            method = "card"
        Payment.objects.create(
            sale=sale, method=method, amount=total, reference=f"MB-{key}"[:60], received_by=user, received_at=when
        )
        set_ref("sale", key, sale)
        res.counts["created"] += 1


# ---------------------------------------------------------------------------
# Inventory on hand
# ---------------------------------------------------------------------------
CATEGORY_WORDS = [
    ("belt", "belts"),
    ("glove", "gloves"),
    ("uniform", "uniforms"),
    ("gi", "uniforms"),
    ("shin", "shin_guards"),
    ("head", "head_guards"),
    ("rash", "rash_guards"),
    ("shirt", "tshirts"),
    ("patch", "patches"),
    ("badge", "patches"),
    ("bag", "bags"),
    ("water", "drinks"),
    ("drink", "drinks"),
    ("guard", "protective"),
    ("supporter", "protective"),
    ("protect", "protective"),
]


def category_for(name):
    words = re.findall(r"[a-z]+", name.lower())
    for word, category in CATEGORY_WORDS:
        if any(w == word or w.startswith(word) for w in words):
            return category
    return "other"


def import_inventory(rows, batch, user, res):
    from apps.finance.models import Vendor
    from apps.inventory.services import set_opening

    match = branch_matcher()
    for row in rows:
        n = row["_row"]
        name = r.text(row.get("product"))
        if not name or name.lower().startswith("total"):
            continue
        if "test" in name.lower().split() or name.lower().endswith(" test"):
            res.counts["skipped_test"] += 1  # decision P3-9
            continue
        branch = match(row.get("location"), batch.branch)
        if branch is None:
            res.issue(n, f"{name}: location not recognised — choose the branch for this file.")
            continue
        size = r.text(row.get("size"))
        size = "" if size.lower() in ("none", "-") else size
        size = size or "One size"
        colour = r.text(row.get("colour"))
        colour = "" if colour.lower() in ("none", "-") else colour
        barcode = r.text(row.get("barcode"))
        variant = ProductVariant.objects.filter(pk=ref("variant", barcode)).first() if barcode else None
        product = variant.product if variant else Product.objects.filter(name_en__iexact=name).first()
        price, cost = r.number(row.get("price")), r.number(row.get("cost"))
        if product is None:
            category = category_for(name)
            base = slugify(name)[:40] or "item"
            slug, i = base, 2
            while Product.objects.filter(slug=slug).exists():
                slug, i = f"{base}-{i}", i + 1
            product = Product.objects.create(
                name_en=name[:100],
                slug=slug,
                category=category,
                price=price or ZERO,
                is_sample_price=False,
                sell_online=category != "belts",
            )
            res.counts["products_created"] += 1
        supplier = r.text(row.get("supplier"))
        if supplier and supplier.lower() not in ("none", "") and product.supplier_id is None:
            vendor, _ = Vendor.objects.get_or_create(name=supplier[:150], defaults={"created_by": user})
            Product.objects.filter(pk=product.pk).update(supplier=vendor)
        if variant is None:
            variant = ProductVariant.objects.filter(product=product, size=size[:20], colour=colour[:30]).first()
        if variant is None:
            variant = ProductVariant.objects.create(
                product=product, size=size[:20], colour=colour[:30], sort_order=product.variants.count()
            )
            res.counts["sizes_created"] += 1
        updates = {"barcode": barcode[:40] or variant.barcode}
        if cost is not None:
            updates["cost"] = cost
        if price is not None and price != product.price:
            updates["retail_price"] = price
        for field, key in (("reorder_level", "reorder"), ("max_level", "max")):
            value = r.integer(row.get(key))
            if value is not None and value >= 0:
                updates[field] = value
        ProductVariant.objects.filter(pk=variant.pk).update(**updates)
        if barcode:
            set_ref("variant", barcode, variant)
        quantity = r.integer(row.get("quantity")) or 0
        if quantity < 0:
            res.issue(
                n,
                f"{name} {size}: Mindbody shows {quantity} — imported as is; count it at the first monthly count.",
                "warn",
            )
        moved = set_opening(
            variant, branch, quantity, user, note=f"Mindbody on hand ({batch.original_name})"[:255], kind="import"
        )
        res.counts["stock_set" if moved else "unchanged"] += 1


IMPORTERS = {
    "clients": import_clients,
    "relationships": import_relationships,
    "memberships": import_memberships,
    "visits": import_visits,
    "sales": import_sales,
    "inventory": import_inventory,
}


# ---------------------------------------------------------------------------
# Running an import
# ---------------------------------------------------------------------------
def create_batch(user, kind, upload, branch=None) -> ImportBatch:
    _need(user)
    if kind not in IMPORTERS:
        raise ValidationError("Choose what the file contains.")
    if upload is None or upload.size == 0:
        raise ValidationError("Choose the Mindbody export file.")
    if upload.size > 25 * 1024 * 1024:
        raise ValidationError("The file must be under 25 MB.")
    batch = ImportBatch(kind=kind, branch=branch, original_name=upload.name[:200], created_by=user, updated_by=user)
    batch.file.save(upload.name, upload, save=False)
    batch.save()
    return run(batch, user, apply=False)


def run(batch: ImportBatch, user, apply=False) -> ImportBatch:
    _need(user)
    if apply and batch.status == ImportBatch.Status.APPLIED:
        raise ValidationError("This file has already been applied. Upload it again to re-run it (safe to repeat).")
    res = Result()
    try:
        with batch.file.open("rb") as fh:
            rows, mapping, unknown = r.table(fh.read(), batch.kind)
    except (ValueError, UnicodeDecodeError) as exc:
        batch.status, batch.issues, batch.summary = (
            ImportBatch.Status.FAILED,
            [{"row": 0, "level": "skip", "message": str(exc)}],
            {},
        )
        batch.save()
        return batch
    try:
        with transaction.atomic():
            IMPORTERS[batch.kind](rows, batch, user, res)
            if not apply:
                transaction.set_rollback(True)  # dry run: report, change nothing
    except Exception as exc:  # noqa: BLE001 - reported to the person importing, never swallowed silently
        res.issue(0, f"Stopped: {exc}")
        apply = False
    for name, branch_id in res.maps:
        OptionMap.objects.get_or_create(mindbody_name=name, branch_id=branch_id, defaults={"created_by": user})
    batch.rows = len(rows)
    batch.summary = {
        "counts": dict(res.counts),
        "columns": sorted(set(mapping.values())),
        "ignored_columns": unknown[:30],
    }
    batch.issues = res.issues
    if apply:
        batch.status, batch.applied_by, batch.applied_at = ImportBatch.Status.APPLIED, user, timezone.now()
        record_event(action="mindbody_import_applied", instance=batch, changes=dict(res.counts))
    else:
        batch.status = ImportBatch.Status.CHECKED
    batch.updated_by = user
    batch.save()
    return batch


def unmapped_options():
    return OptionMap.objects.filter(pricing_option__isnull=True, skip=False).select_related("branch")


@transaction.atomic
def map_option(mapping: OptionMap, user, pricing_option=None, skip=False) -> OptionMap:
    _need(user)
    if pricing_option is not None and pricing_option.branch_id != mapping.branch_id:
        raise ValidationError("Choose a pricing option of the same branch.")
    mapping.pricing_option, mapping.skip, mapping.updated_by = (None if skip else pricing_option), skip, user
    mapping.save()
    return mapping


# ---------------------------------------------------------------------------
# Parallel run: Mindbody's weekly figures next to the system's
# ---------------------------------------------------------------------------
def system_week(branch, week_start) -> dict:
    from apps.reports.services import active_memberships

    end = week_start + datetime.timedelta(days=6)
    s0, e1 = day_range(week_start)[0], day_range(end)[1]
    payments = Payment.objects.filter(sale__branch=branch, received_at__gte=s0, received_at__lt=e1)
    by = {m: payments.filter(method=m).aggregate(t=Sum("amount"))["t"] or ZERO for m in ("knet", "card", "cash")}
    active = active_memberships(end, branch).values_list("member_id", flat=True).distinct().count()
    return {"knet": str(by["knet"]), "card": str(by["card"]), "cash": str(by["cash"]), "active": active}


@transaction.atomic
def record_check(branch, week_start, user, *, knet, card, cash, active, explanation="") -> ParallelRunCheck:
    _need(user)
    system = system_week(branch, week_start)
    check, _ = ParallelRunCheck.objects.get_or_create(
        branch=branch, week_start=week_start, defaults={"created_by": user}
    )
    check.mb_knet, check.mb_card, check.mb_cash, check.mb_active_members = knet, card, cash, active
    check.system, check.explanation, check.updated_by = system, explanation.strip(), user
    diffs = differences(check)
    if any(diffs.values()) and not check.explanation:
        check.agreed = False
    else:
        check.agreed = True
    check.save()
    return check


def differences(check: ParallelRunCheck) -> dict:
    s = check.system or {}
    return {
        "knet": Decimal(s.get("knet", "0")) - check.mb_knet,
        "card": Decimal(s.get("card", "0")) - check.mb_card,
        "cash": Decimal(s.get("cash", "0")) - check.mb_cash,
        "active": int(s.get("active", 0)) - check.mb_active_members,
    }


CUTOVER = [
    (
        "Trial import into the test copy; team checks member counts, expiries and stock against Mindbody",
        "استيراد تجريبي ومراجعة الأعداد وتواريخ الانتهاء والمخزون مقابل مايندبودي",
    ),
    ("Every Mindbody pricing option mapped or skipped", "ربط كل خيارات الأسعار من مايندبودي أو استبعادها"),
    (
        "Parallel run: weekly sales and active members agree (or differences explained) at both branches",
        "التشغيل المتوازي: تطابق المبيعات والأعضاء النشطين أسبوعياً في الفرعين",
    ),
    ("Staff trained: 15-minute walkthrough per role", "تدريب الموظفين: جولة 15 دقيقة لكل دور"),
    ("Freeze Mindbody entries (no new sales or check-ins there)", "إيقاف الإدخال في مايندبودي"),
    ("Final import of the delta (same files, same screen)", "الاستيراد النهائي للفروقات"),
    ("Monthly count at both branches to confirm the stock baseline", "جرد شهري في الفرعين لتأكيد المخزون"),
    (
        "Front desks switched to the new desk; card terminals and receipts checked",
        "تحويل الاستقبال إلى النظام الجديد ومراجعة أجهزة الدفع والإيصالات",
    ),
    ("Website booking and schedule pointing at the system", "ربط الحجز والجدول في الموقع بالنظام"),
    (
        "Mindbody kept read-only for reference until the subscription ends",
        "إبقاء مايندبودي للقراءة فقط حتى انتهاء الاشتراك",
    ),
]


def ensure_cutover_steps():
    if CutoverStep.objects.exists():
        return
    CutoverStep.objects.bulk_create(
        [CutoverStep(order=i, title_en=en, title_ar=ar) for i, (en, ar) in enumerate(CUTOVER, start=1)]
    )


@transaction.atomic
def tick_step(step: CutoverStep, user, done=True, note="") -> CutoverStep:
    _need(user)
    step.done_by, step.done_at = (user, timezone.now()) if done else (None, None)
    step.note, step.updated_by = note.strip()[:255], user
    step.save()
    return step
