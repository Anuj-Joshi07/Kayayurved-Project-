import pdfplumber
import fitz
import os
import re
import csv

def extract_text(pdf_path):
    pages_text = {}
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            pages_text[i+1] = page.extract_text() or ""
    return pages_text

def extract_images(pdf_path, out_dir, page_number):
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)

    page = doc[page_number - 1]  # zero-based index
    for img_idx, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        img_data = doc.extract_image(xref)
        img_bytes = img_data["image"]
        ext = img_data["ext"]

        fname = f"page{page_number}_img{img_idx}.{ext}"
        with open(os.path.join(out_dir, fname), "wb") as f:
            f.write(img_bytes)

def parse_features(pages):
    data = {}

    full_text = " ".join(pages.values()).lower()
    age = re.search(r'(\d{2})\s*yrs', full_text)
    data["age"] = int(age.group(1)) if age else None
    data["gender"] = "male" if "/m" in full_text else "female"

    data["scalp_oily"] = "scalp is oily" in full_text
    data["hair_density"] = "medium" if "hair density is medium" in full_text else None
    data["alopecia_patch"] = "patch of alopecia" in full_text
    data["dandruff_severity"] = "large quantity" if "dandruff seen in large" in full_text else "low"


    data["anagen_present"] = "anagen phase" in full_text
    data["telogen_present"] = "telogen phase" in full_text


    root = re.search(r'hair root\s*:\s*([\d.]+)', full_text)
    shaft = re.search(r'hair shaft\s*:\s*([\d.]+)', full_text)
    tip = re.search(r'hair tip\s*:\s*([\d.]+)', full_text)
    data["hair_root_um"] = float(root.group(1)) if root else None
    data["hair_shaft_um"] = float(shaft.group(1)) if shaft else None
    data["hair_tip_um"] = float(tip.group(1)) if tip else None


    therapies = []
    if "prp therapy" in full_text:
        therapies.append("PRP")
    if "meso" in full_text:
        therapies.append("Meso")
    if "dandruff removal therapy" in full_text:
        therapies.append("Dandruff")
    data["therapies"] = ", ".join(therapies)


    page9_text = pages.get(9, "")
    saptadhatu_values = {}
    saptadhatu_keys = ["rasa dushti", "rakta dushti", "asthi kshaya", "shukra kshaya", "mamsa", "meda", "majja"]
    for key in saptadhatu_keys:
        match = re.search(rf"{key}\s*[:\-]?\s*(\w+)", page9_text, re.IGNORECASE)
        saptadhatu_values[key] = match.group(1).strip() if match else ""
    data["kesh_saptadhatu_parikshan"] = saptadhatu_values


    page10_text = pages.get(10, "")
    analysis_match = re.search(r'analysis\s*[:\-]?\s*(.*)', page10_text, re.IGNORECASE | re.DOTALL)
    data["kesh_saamata_parikshan"] = analysis_match.group(1).strip() if analysis_match else page10_text.strip()

    page11_text = pages.get(11, "")
    notes_match = re.search(r'note\s*[:\-]?\s*(.*)', page11_text, re.IGNORECASE | re.DOTALL)
    data["kesh_prakruti_parikshan"] = notes_match.group(1).strip() if notes_match else page11_text.strip()

    return data


def save_to_csv(data, csv_file):
    os.makedirs(os.path.dirname(csv_file), exist_ok=True)
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=data.keys())
        writer.writeheader()
        writer.writerow(data)


pdf = "__ Hair Report __ABHISHEK__DASGAVKAR.pdf"


pages = extract_text(pdf)


features = parse_features(pages)


extract_images(pdf, "images/15471", page_number=2)


save_to_csv(features, "output/hair_report_features.csv")

print("Extraction complete! Data saved to CSV and images saved from page 2.")
