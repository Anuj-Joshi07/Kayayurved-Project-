import pdfplumber
import csv
import re

PDF_PATH = "__ Hair Report __ARUSHI__PALEKAR.pdf"
OUTPUT_CSV = "line_of_treatment.csv"

PAGE_INDEX = 12  


def clean(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


with pdfplumber.open(PDF_PATH) as pdf:
    page = pdf.pages[PAGE_INDEX]

    
    table = page.extract_table({
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "intersection_tolerance": 5,
    })

    internal = []
    external = []

    for row in table:
        if len(row) < 4:
            continue

        internal_text = clean(row[1])
        external_text = clean(row[3])

        if internal_text.lower() == "internal":
            continue
        if external_text.lower() == "external":
            continue

        if internal_text:
            internal.append(internal_text)
        if external_text:
            external.append(external_text)

    text = page.extract_text()
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    therapies_lines = []
    other_therapies_lines = []
    panchakarma = ""
    personalized_notes = ""

    current = None

    for line in lines:
        low = line.lower()

        if low.startswith("therapies"):
            current = "therapies"
            therapies_lines.append(line.split(":", 1)[1].strip())
            continue

        elif low.startswith("other therapies"):
            current = "other_therapies"
            other_therapies_lines.append(line.split(":", 1)[1].strip())
            continue

        elif low.startswith("panchakarma"):
            current = None
            panchakarma = clean(line.split(":", 1)[1])
            continue

        elif low.startswith("personalized treatment notes"):
            current = None
            personalized_notes = clean(line.split(":", 1)[1])
            continue

        
        if current == "therapies":
            therapies_lines.append(line)

        elif current == "other_therapies":
            other_therapies_lines.append(line)

    therapies = clean(" ".join(therapies_lines))
    other_therapies = clean(" ".join(other_therapies_lines))

   
    row = {
        "internal_treatment": " | ".join(internal),
        "external_treatment": " | ".join(external),
        "therapies": therapies,
        "other_therapies": other_therapies,
        "panchakarma": panchakarma,
        "personalized_notes": personalized_notes,
    }

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        writer.writeheader()
        writer.writerow(row)

print("✅ Extraction fixed and stored correctly")
