"""One-off fixture builder. Run with `python tests/fixtures/_make_pdf_with_js.py`."""

from pathlib import Path

import pikepdf

p = pikepdf.Pdf.new()
p.add_blank_page(page_size=(595, 842))
p.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS="app.alert('x')")
_js_action = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS="bad()")
p.Root.Names = pikepdf.Dictionary(
    JavaScript=pikepdf.Dictionary(Names=pikepdf.Array([pikepdf.String("evil"), _js_action]))
)
out = Path(__file__).parent / "pdf_with_js.pdf"
p.save(out)
print(f"wrote {out}")
