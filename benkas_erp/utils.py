"""Shared helpers exposed to Jinja (print formats)."""

import io
import base64


def qr_data_uri(value, box_size=6, border=4):
    """Return a base64 PNG data URI QR code for `value`, usable directly in an
    <img src="...">. Uses error-correction level M and a 4-module quiet zone so
    the printed code scans reliably at ~3 cm. Degrades to empty string if
    qrcode/Pillow is unavailable so print rendering never breaks."""
    if not value:
        return ""
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border,
        )
        qr.add_data(str(value))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


# Standardised scan-key helper, also exposed to Jinja so print formats and the
# scan station agree on exactly what each QR encodes.
def qr_key(doctype, name):
    from benkas_erp.scan import qr_key as _k
    return _k(doctype, name)
