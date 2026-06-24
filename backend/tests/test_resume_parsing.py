"""Bug 1 regression: PDF text extraction must preserve word boundaries.

Some resume PDFs lay words out with small inter-word gaps that pdfplumber's
default x_tolerance (3) merges into one token ("Webscrapedmostfavored..."). The
parser uses x_tolerance=1 to recover those boundaries. This builds a PDF that
reproduces the small-gap layout and asserts spacing survives.
"""
import pdfplumber

from app.utils.resume_parser import _extract_text


def _positioned_pdf(words, gap=2.0, path="/tmp/jobora_spacing_test.pdf"):
    """Draw each word as a separate Tj advancing by ~word-width + a small gap, so
    the inter-word geometric gap is tiny (the layout that breaks default extraction)."""
    parts = ["BT /F1 11 Tf 50 740 Td"]
    for w in words:
        parts.append(f"({w}) Tj")
        parts.append(f"{len(w) * 6.1 + gap:.1f} 0 Td")
    stream = " ".join(parts) + " ET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = "%PDF-1.4\n"
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(pdf))
        pdf += f"{i} 0 obj\n{o}\nendobj\n"
    x = len(pdf)
    pdf += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n"
    for o in offs:
        pdf += f"{o:010d} 00000 n \n"
    pdf += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF"
    with open(path, "wb") as f:
        f.write(pdf.encode("latin-1"))
    return path


PHRASE = "Web scraped most favored food items from Zomato and Swiggy"


def test_extract_text_preserves_word_spacing():
    path = _positioned_pdf(PHRASE.split())
    text = _extract_text(path)
    # The fix (x_tolerance=1) recovers the inter-word boundaries.
    assert "most favored food items from Zomato" in text
    # No long run-together alphabetic token should survive in the bullet body.
    runs = [w for w in text.split() if len(w) > 18 and w.isalpha()]
    assert not runs, f"unexpected run-together tokens: {runs}"


def test_fix_actually_changes_default_behavior():
    """Guards the fix: the stdlib default WOULD merge these words, proving the
    x_tolerance change is what preserves spacing (not the PDF being trivially fine)."""
    path = _positioned_pdf(PHRASE.split())
    with pdfplumber.open(path) as pdf:
        default = (pdf.pages[0].extract_text() or "")
    assert "most favored food items" not in default      # default loses the spaces
    assert "most favored food items" in _extract_text(path)  # the fix restores them
