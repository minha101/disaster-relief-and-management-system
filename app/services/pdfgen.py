from io import BytesIO
from xml.sax.saxutils import escape
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(colors.grey)
    canvas.drawString(24, 14, 'Flood & Disaster Relief Coordination System - confidential working document')
    canvas.drawRightString(landscape(A4)[0] - 24, 14, f'Page {doc.page}')
    canvas.restoreState()


def build_pdf(title, sections, meta_lines=()):
    """sections: list of (heading, headers, rows). Returns bytes."""
    buf = BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(buf, pagesize=page, leftMargin=24, rightMargin=24, topMargin=28, bottomMargin=30, title=title)
    ss = getSampleStyleSheet()
    small = ParagraphStyle('small', parent=ss['BodyText'], fontSize=7.5, leading=9)
    head = ParagraphStyle('head', parent=small, textColor=colors.white)
    story = [Paragraph(escape(title), ss['Title'])]
    for m in meta_lines:
        story.append(Paragraph(escape(m), ss['BodyText']))
    width = page[0] - 48
    for heading, headers, rows in sections:
        story += [Spacer(1, 10), Paragraph(escape(heading), ss['Heading2'])]
        if not rows:
            story.append(Paragraph('No records.', ss['BodyText']))
            continue
        data = [[Paragraph('<b>%s</b>' % escape(str(h)), head) for h in headers]]
        data += [[Paragraph(escape('' if c is None else str(c)), small) for c in r] for r in rows]
        t = Table(data, colWidths=[width / len(headers)] * len(headers), repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1d4ed8')),
                               ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
                               ('GRID', (0, 0), (-1, -1), .25, colors.HexColor('#cbd5e1')),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story.append(t)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def meta(user, scope_label, composition_note=''):
    lines = [f'Generated: {datetime.now():%Y-%m-%d %H:%M} by {user.full_name}', f'Data scope: {scope_label}']
    if composition_note:
        lines.append(composition_note)
    lines.append('Records marked SAMPLE are fictional demonstration data. Figures are as entered in the system; '
                 'no live GPS, weather or river-level feeds are used.')
    return lines
