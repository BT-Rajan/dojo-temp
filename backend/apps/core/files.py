"""Safe handling of uploaded documents (receipts, invoices, staff documents)."""

import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

MAX_UPLOAD = 5 * 1024 * 1024
IMAGE_TYPES = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")


def clean_document(upload, *, allow_pdf=True, max_side=1600) -> ContentFile:
    """
    Photos are re-encoded as JPEG (strips location data and anything hidden in the file);
    PDFs are accepted only when the file really starts as a PDF. Anything else is refused.
    """
    if upload is None:
        raise ValidationError("Choose a file.")
    if upload.size > MAX_UPLOAD:
        raise ValidationError("The file must be under 5 MB.")
    head = upload.read(5)
    upload.seek(0)
    if allow_pdf and head == b"%PDF-":
        return ContentFile(upload.read(), name="document.pdf")
    from PIL import Image, UnidentifiedImageError

    try:
        from pillow_heif import register_heif_opener  # iPhone photos

        register_heif_opener()
    except ImportError:  # pragma: no cover - optional
        pass
    try:
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("Upload a photo (JPG, PNG, HEIC) or a PDF." if allow_pdf else "Upload a photo.") from exc
    image.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "JPEG", quality=85)
    return ContentFile(buf.getvalue(), name="document.jpg")


def content_type_for(name: str) -> str:
    return "application/pdf" if name.lower().endswith(".pdf") else "image/jpeg"
