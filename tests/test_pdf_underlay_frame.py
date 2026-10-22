"""Owner 22/10, the villa drawings (NEW VILLA PLAN …, 1:50): CAD exports crop a 1200 × 600 mm sheet (CropBox ≠ MediaBox)
and one is turned (/Rotate 270).  The lines must be read in the frame of the page as shown — the one the underlay
picture is drawn in — or the walls found from them come out shifted; only the dark pens are walls."""
import pytest

from archforge.project import underlay as U


def _pdf(path, ops, media=(0, 0, 1000, 600), crop=None, rotate=0):
    """A one-page PDF whose content stream is ``ops`` (PDF operators, user space: y up from the MediaBox corner)."""
    stream = ops.encode()
    extra = (f"/CropBox [{' '.join(map(str, crop))}] " if crop else "") + (f"/Rotate {rotate} " if rotate else "")
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            f"<< /Type /Page /Parent 2 0 R /MediaBox [{' '.join(map(str, media))}] {extra}/Contents 4 0 R >>",
            None]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        if body is None:
            out += f"{i} 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream\nendobj\n"
        else:
            out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return str(path)


def test_lines_are_read_in_the_visible_area_and_outside_ones_dropped(tmp_path):
    # A black line at y = 300 from x = 300 to 500; another far outside the visible area.
    pdf = _pdf(tmp_path / 'crop.pdf', "0 0 0 RG 300 300 m 500 300 l S 900 50 m 950 50 l S",
               crop=(200, 100, 700, 500))
    segs = U.pdf_vector_segments(pdf)
    assert segs == [pytest.approx((100.0, 200.0, 300.0, 200.0))]     # from the CropBox corner, not the MediaBox


def test_turned_page_is_read_as_shown(tmp_path):
    # MediaBox 1000 × 600 turned 270° (shown 600 wide × 1000 high): a horizontal line in user space is vertical as shown.
    pdf = _pdf(tmp_path / 'turned.pdf', "0 0 0 RG 100 200 m 400 200 l S", rotate=270)
    (x1, y1, x2, y2), = U.pdf_vector_segments(pdf)
    assert x1 == pytest.approx(x2) and abs(y2 - y1) == pytest.approx(300.0)
    assert 0 <= x1 <= 600 and 0 <= min(y1, y2) and max(y1, y2) <= 1000


def test_only_the_dark_pens_for_walls(tmp_path):
    ops = ("0 0 0 RG 0 0 100 50 re S "                      # black outline
           "0.73 0.16 0.16 RG 10 10 m 90 10 l S "           # red mark-up
           "0.8 g 20 20 30 10 re f "                        # light grey fill (hatch / furniture)
           "0 g 60 20 10 10 re f "                          # black poché
           "0 0 0 1 K 0 45 m 100 45 l S")                   # CMYK black
    pdf = _pdf(tmp_path / 'pens.pdf', ops)
    every, dark = U.pdf_vector_segments(pdf), U.pdf_vector_segments(pdf, dark_only=True)
    assert len(every) == 4 + 1 + 4 + 4 + 1 and len(dark) == 4 + 4 + 1
    assert not any(abs(s[1] - 10) < 1e-6 and abs(s[3] - 10) < 1e-6 for s in dark)   # the red line is out
