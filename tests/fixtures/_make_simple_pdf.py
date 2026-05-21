"""Generate a 3-page Letter-sized PDF for renderer tests."""

from pathlib import Path

import pikepdf

p = pikepdf.Pdf.new()
for _ in range(3):
    p.add_blank_page(page_size=(612, 792))  # US Letter in PDF points
out = Path(__file__).parent / "simple.pdf"
p.save(out)
print(f"wrote {out}")
