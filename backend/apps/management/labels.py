"""Arabic labels for the management choices (the models hold the English)."""

AR = {
    "handoff.kind": {
        "stories": "قصص التقدم ومعرفة البرامج (التدريب ← التسويق)",
        "message": "التحقق من دقة رسالة تسويقية (التسويق ← التدريب)",
        "leads": "عملاء محتملون من الحملات (التسويق ← العمليات)",
        "results": "نتائج التحويل وصور الحصص (العمليات ← التسويق)",
        "attendance": "الحضور والتقدم والملاحظات (التدريب ← العمليات)",
        "bookings": "الحجوزات وإجراءات الأعضاء (العمليات ← التدريب)",
        "it_request": "طلب إلى الأنظمة وتقنية المعلومات",
        "it_notice": "إشعار بتغيير في النظام (التقنية ← القائد المعني)",
        "update": "تحديث أو مسألة للرئيس التنفيذي بين التقارير الشهرية",
        "other": "أخرى",
    },
    "handoff.status": {"sent": "بانتظار التأكيد", "confirmed": "مؤكد", "done": "منجز", "declined": "مرفوض"},
    "handoff.urgency": {"low": "يمكن أن ينتظر", "normal": "عادي", "high": "قريباً", "urgent": "عاجل"},
    "meeting.status": {"draft": "مسودة المحضر", "published": "أُرسل المحضر"},
    "action.status": {"open": "مفتوح", "done": "منجز", "dropped": "أُلغي"},
    "report.function": {
        "training": "التدريب",
        "operations": "العمليات",
        "marketing": "التسويق",
        "it": "الأنظمة والتقنية",
    },
    "report.status": {"draft": "مسودة", "submitted": "أُرسل للرئيس التنفيذي", "acknowledged": "تم الاطلاع"},
    "escalation.kind": {"safety": "سلامة", "conduct": "سلوك", "other": "مسألة عاجلة أخرى"},
    "escalation.status": {"open": "مفتوحة", "closed": "مغلقة"},
    "procedure.kind": {"procedure": "إجراء", "form": "نموذج", "policy": "سياسة", "reference": "مرجع"},
    "version.status": {"draft": "بانتظار الاعتماد", "approved": "معتمد", "returned": "أُعيد"},
    "qbr.status": {
        "draft": "مسودة",
        "submitted": "بانتظار الرئيس التنفيذي",
        "returned": "أُعيد للتعديل",
        "approved": "معتمد",
    },
}
