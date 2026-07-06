"""Shared helpers exposed to Jinja (print formats)."""

import io
import base64


def qr_data_uri(value, box_size=3, border=2):
    """Return a base64 PNG data URI QR code for `value`, usable directly in an
    <img src="...">. Degrades to empty string if qrcode/Pillow unavailable so
    print rendering never breaks."""
    if not value:
        return ""
    try:
        import qrcode
        img = qrcode.make(str(value), box_size=box_size, border=border)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""
