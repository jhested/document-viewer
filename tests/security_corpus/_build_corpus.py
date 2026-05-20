"""Build the corpus. Run once; outputs are committed."""
from __future__ import annotations

import binascii
import struct
from pathlib import Path

import pikepdf

ROOT = Path(__file__).parent

(ROOT / "pdfs").mkdir(exist_ok=True)
(ROOT / "images").mkdir(exist_ok=True)

# 1. PDF with /JavaScript and /OpenAction
p = pikepdf.Pdf.new()
p.add_blank_page(page_size=(595, 842))
p.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.JavaScript, JS="bad()")
p.save(ROOT / "pdfs" / "with_js.pdf")

# 2. PDF with /Launch action
p = pikepdf.Pdf.new()
p.add_blank_page(page_size=(595, 842))
p.Root.OpenAction = pikepdf.Dictionary(S=pikepdf.Name.Launch, F="/bin/sh")
p.save(ROOT / "pdfs" / "with_launch.pdf")

# 3. Truncated PDF -- cut to 100 bytes (past header, before xref);
#    pikepdf cannot recover and must raise.
data = (ROOT.parent / "fixtures" / "simple.pdf").read_bytes()
(ROOT / "pdfs" / "truncated.pdf").write_bytes(data[:100])


# 4. Decompression bomb PNG (huge declared dimensions, tiny IDAT)
def _png_bomb() -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">II BBBBB", 60000, 60000, 8, 2, 0, 0, 0)
    crc = binascii.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF
    return (
        sig
        + struct.pack(">I", 13)
        + b"IHDR"
        + ihdr
        + struct.pack(">I", crc)
        + b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


(ROOT / "images" / "decompression_bomb.png").write_bytes(_png_bomb())

# 5. PE labeled .pdf (magic must reject before parsing)
(ROOT / "pdfs" / "pe_labelled_pdf.pdf").write_bytes(b"MZ\x90\x00" + b"\x00" * 1024)

print("corpus built")
