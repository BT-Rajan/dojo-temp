"""Arabic labels for lead sources, stages and lost reasons (the models hold the English)."""

SOURCE_AR = {
    "walk_in": "زيارة مباشرة",
    "phone": "هاتف",
    "website": "نموذج التجربة على الموقع",
    "saqr": "محادثة صقر",
    "whatsapp": "واتساب",
    "referral": "ترشيح من عضو",
    "group": "مبيعات جماعية",
    "event": "فعالية",
    "other": "أخرى",
}
STAGE_AR = {
    "new": "جديد",
    "contacted": "تم التواصل",
    "trial_booked": "تجربة محجوزة",
    "trial_done": "حضر التجربة",
    "joined": "انضم",
    "lost": "لم يُكمل",
}
LOST_AR = {
    "price": "السعر",
    "timing": "مواعيد الحصص غير مناسبة",
    "location": "الموقع",
    "no_answer": "لا رد بعد عدة محاولات",
    "not_interested": "لم يعد مهتماً",
    "chose_other": "اختار أكاديمية أخرى",
    "age": "العمر / لا توجد حصة مناسبة",
    "other": "أخرى",
}


def label(kind: str, code: str, lang: str) -> str:
    from .models import Lead

    english = {
        "source": dict(Lead.Source.choices),
        "stage": dict(Lead.Stage.choices),
        "lost": dict(Lead.LostReason.choices),
    }[kind]
    arabic = {"source": SOURCE_AR, "stage": STAGE_AR, "lost": LOST_AR}[kind]
    if lang == "ar":
        return arabic.get(code, english.get(code, code or "—"))
    return english.get(code, code or "—")
