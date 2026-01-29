import fitz
import os

PDF_PATH = "__ Hair Report __ABHISHEK__DASGAVKAR.pdf"
OUT_DIR = "manual_pages"
os.makedirs(OUT_DIR, exist_ok=True)

doc = fitz.open(PDF_PATH)

for page_no in [7, 11]:  
    pix = doc.load_page(page_no).get_pixmap(dpi=300)
    pix.save(f"{OUT_DIR}/page_{page_no+1}.png")

print("Pages extracted")
