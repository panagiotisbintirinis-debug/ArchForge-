"""Minimal .xlsx writer (no dependency): priced material lists whose totals Excel computes.

Each sheet is a list of rows ``(description, unit, quantity)``.  The sheet
gets a «Τιμή μονάδας €» column left empty for the user (yellow input cells)
and «Σύνολο €» = quantity × price as a formula, with a SUM at the bottom, so
the totals come out as soon as prices are typed — in Excel, LibreOffice Calc
or any spreadsheet that reads Office Open XML.  A row with quantity None is
an item whose quantity comes from another study (left for the user too).
"""
from __future__ import annotations

import zipfile
from xml.sax.saxutils import escape

HEADER = ("Είδος", "Μονάδα", "Ποσότητα", "Τιμή μονάδας €", "Σύνολο €")


def _col(i):
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(ref, value, style=0, formula=None):
    st = f' s="{style}"' if style else ""
    if formula is not None:
        return f'<c r="{ref}"{st}><f>{escape(formula)}</f></c>'
    if value is None or value == "":
        return f'<c r="{ref}"{st}/>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"{st}><v>{value}</v></c>'
    return f'<c r="{ref}"{st} t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'


def _sheet(title, rows, notes=()):
    """Sheet XML: title row, header, priced rows, total; returns (xml, first_row, last_row)."""
    out = [f'<row r="1">{_cell("A1", title, 1)}</row>',
           '<row r="3">' + "".join(_cell(f"{_col(i)}3", h, 1) for i, h in enumerate(HEADER)) + "</row>"]
    r = 4
    first = r
    for desc, unit, qty in rows:
        out.append(f'<row r="{r}">' + _cell(f"A{r}", desc) + _cell(f"B{r}", unit)
                   + _cell(f"C{r}", qty if qty is None else round(float(qty), 3), 3 if qty is None else 0)
                   + _cell(f"D{r}", None, 2) + _cell(f"E{r}", None, 4, formula=f"IF(OR(C{r}=\"\",D{r}=\"\"),0,C{r}*D{r})")
                   + "</row>")
        r += 1
    last = r - 1
    out.append(f'<row r="{r}">' + _cell(f"A{r}", "Σύνολο", 1) + _cell(f"E{r}", None, 5,
                                                                      formula=f"SUM(E{first}:E{last})" if last >= first else "0") + "</row>")
    r += 2
    for n in notes:
        out.append(f'<row r="{r}">{_cell(f"A{r}", n)}</row>')
        r += 1
    cols = '<cols><col min="1" max="1" width="60" customWidth="1"/><col min="2" max="2" width="10" customWidth="1"/>' \
           '<col min="3" max="5" width="16" customWidth="1"/></cols>'
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           f'{cols}<sheetData>{"".join(out)}</sheetData></worksheet>')
    return xml, first, last


_STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
           '<numFmts count="1"><numFmt numFmtId="164" formatCode="#,##0.00 &quot;€&quot;"/></numFmts>'
           '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
           '<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
           '<fill><patternFill patternType="solid"><fgColor rgb="FFFFF2B3"/></patternFill></fill>'
           '<fill><patternFill patternType="solid"><fgColor rgb="FFE8E8E8"/></patternFill></fill></fills>'
           '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
           '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
           '<cellXfs count="6">'
           '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
           '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'                     # 1 bold
           '<xf numFmtId="164" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1" applyNumberFormat="1"/>'  # 2 price input
           '<xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1"/>'                     # 3 quantity to fill
           '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'            # 4 money
           '<xf numFmtId="164" fontId="1" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1" applyNumberFormat="1"/>'  # 5 total
           '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')


def write_priced_workbook(path, sheets):
    """``sheets``: ``[(name, title, rows, notes)]`` → .xlsx at ``path`` (prices empty, totals as formulas)."""
    names = []
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for i, (name, title, rows, notes) in enumerate(sheets, 1):
            xml, _f, _l = _sheet(title, rows, notes)
            z.writestr(f"xl/worksheets/sheet{i}.xml", xml)
            names.append(name[:31])
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                   '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                   + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
                             'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                             for i in range(1, len(names) + 1)) + "</Types>")
        z.writestr("_rels/.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                   'Target="xl/workbook.xml"/></Relationships>')
        z.writestr("xl/workbook.xml",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1))
                   + '</sheets><calcPr fullCalcOnLoad="1"/></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",
                   '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                             f'Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(names) + 1))
                   + f'<Relationship Id="rId{len(names) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
                   'Target="styles.xml"/></Relationships>')
        z.writestr("xl/styles.xml", _STYLES)
    return path
