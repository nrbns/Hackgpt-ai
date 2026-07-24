"""Lightweight Office exports (DOCX / XLSX) without heavyweight dependencies.

Uses Office Open XML (zip + XML) so Community installs stay lean.
"""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any
from xml.sax.saxutils import escape


def _xlsx_sheet_xml(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(ref: str, value: Any) -> str:
        text = "" if value is None else str(value)
        return f'<c r="{ref}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'

    def col_letter(n: int) -> str:
        s = ""
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    lines.append(
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    )
    all_rows = [headers] + rows
    for r_idx, row in enumerate(all_rows, start=1):
        cells = "".join(cell(f"{col_letter(c_idx)}{r_idx}", val) for c_idx, val in enumerate(row, start=1))
        lines.append(f'<row r="{r_idx}">{cells}</row>')
    lines.append("</sheetData></worksheet>")
    return "".join(lines)


def build_xlsx(headers: list[str], rows: list[list[Any]], sheet_name: str = "Sheet1") -> bytes:
    sheet = _xlsx_sheet_xml(headers, rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        z.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        z.writestr(
            "xl/workbook.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="{escape(sheet_name)[:31]}" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def build_docx_from_paragraphs(title: str, paragraphs: list[str]) -> bytes:
    body_parts = [
        f"<w:p><w:r><w:rPr><w:b/></w:rPr><w:t>{escape(title)}</w:t></w:r></w:p>",
        "<w:p/>",
    ]
    for p in paragraphs:
        if not p:
            body_parts.append("<w:p/>")
            continue
        # split long lines
        text = escape(p)
        body_parts.append(f"<w:p><w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>")
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {''.join(body_parts)}
    <w:sectPr/>
  </w:body>
</w:document>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
        )
        z.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        )
        z.writestr("word/document.xml", document)
    return buf.getvalue()


def markdown_to_docx(md: str, title: str = "SecuraIQ Report") -> bytes:
    paras: list[str] = []
    for raw in (md or "").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            paras.append(line.lstrip("# ").strip())
            paras.append("")
        elif line.startswith("|") or line.startswith("-"):
            paras.append(line)
        else:
            paras.append(line)
    return build_docx_from_paragraphs(title, paras)


def csv_bytes(headers: list[str], rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")
