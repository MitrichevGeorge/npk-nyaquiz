import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import segno


class ExportService:
    def generate_qr_svg(self, url: str) -> bytes:
        qr = segno.make(url, error="m")
        buf = io.BytesIO()
        qr.save(buf, kind="svg", scale=6, border=2)
        return buf.getvalue()

    def generate_qr_png(self, url: str) -> bytes:
        qr = segno.make(url, error="m")
        buf = io.BytesIO()
        qr.save(buf, kind="png", scale=10, border=2)
        return buf.getvalue()

    def generate_handout_pdf(self, title: str, join_code: str, join_url: str) -> bytes:
        buf = io.BytesIO()
        pdf = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        pdf.setFont("Helvetica-Bold", 24)
        pdf.drawCentredString(width / 2, height - 100, "nyaquiz")
        pdf.setFont("Helvetica", 16)
        pdf.drawCentredString(width / 2, height - 140, title[:64])
        pdf.setFont("Helvetica-Bold", 32)
        pdf.drawCentredString(width / 2, height - 200, f"CODE: {join_code}")
        pdf.setFont("Helvetica", 12)
        pdf.drawCentredString(width / 2, height - 240, join_url)
        pdf.showPage()
        pdf.save()
        return buf.getvalue()
