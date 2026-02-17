import streamlit as st
import pdfplumber
import fitz
import os
import re
import csv
import shutil
import pandas as pd
import tempfile
import cv2
import numpy as np
import json


PAGES_TO_EXTRACT = [7, 11]

page_to_layout = {
    "8": "page7",
    "12": "page11"
}

ATTRIBUTES_PAGE_8 = [
    {"label": "Dry / Oily", "left": "Dry", "right": "Oily"},
    {"label": "Coarse / Soft", "left": "Coarse", "right": "Soft"},
    {"label": "Dull / Lustrous", "left": "Dull", "right": "Lustrous"},
    {"label": "Sparse / Dense", "left": "Sparse", "right": "Dense"},
    {"label": "Thin / Broad", "left": "Thin", "right": "Broad"},
    {"label": "Curly / Straight / Wavy", "left": "Curly", "right": "Wavy"}
]

ATTRIBUTES_PAGE_12 = ["Prithvi", "Aap", "Tej", "Vayu", "Akash"]

DEFAULT_LAYOUT_CONFIG = {
    "page7": {
        "bar": [100, 200, 2000, 1500]
    },
    "page11": {
        "bar": [100, 200, 2000, 1500]
    }
}


def extract_text(pdf_path):
    pages_text = {}
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            pages_text[i+1] = page.extract_text() or ""
    return pages_text


def extract_images(pdf_path, out_dir, page_number):
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]

    page = doc[page_number - 1]  
    for img_idx, img in enumerate(page.get_images(full=True)):
        xref = img[0]
        img_data = doc.extract_image(xref)
        img_bytes = img_data["image"]
        ext = img_data["ext"]

        fname = f"{pdf_name}_{img_idx + 1}.{ext}"
        with open(os.path.join(out_dir, fname), "wb") as f:
            f.write(img_bytes)


def clean(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_line_of_treatment(pdf_path):
    PAGE_INDEX = 12 
    
    treatment_data = {
        "internal_treatment": "",
        "external_treatment": "",
        "therapies": "",
        "other_therapies": "",
        "panchakarma": "",
        "personalized_notes": ""
    }
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[PAGE_INDEX]

            table = page.extract_table({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "intersection_tolerance": 5,
            })

            internal = []
            external = []

            if table:
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
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        therapies_lines.append(parts[1].strip())
                    continue

                elif low.startswith("other therapies"):
                    current = "other_therapies"
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        other_therapies_lines.append(parts[1].strip())
                    continue

                elif low.startswith("panchakarma"):
                    current = None
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        panchakarma = clean(parts[1])
                    continue

                elif low.startswith("personalized treatment notes") or low.startswith("personalized treatment"):
                    current = None
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        personalized_notes = clean(parts[1])
                    continue

                if current == "therapies":
                    therapies_lines.append(line)

                elif current == "other_therapies":
                    other_therapies_lines.append(line)

            treatment_data["internal_treatment"] = " | ".join(internal)
            treatment_data["external_treatment"] = " | ".join(external)
            treatment_data["therapies"] = clean(" ".join(therapies_lines))
            treatment_data["other_therapies"] = clean(" ".join(other_therapies_lines))
            treatment_data["panchakarma"] = panchakarma
            treatment_data["personalized_notes"] = personalized_notes

    except Exception as e:
        st.warning(f"Could not extract line of treatment: {str(e)}")
    
    return treatment_data


def parse_features(pages):
    data = {}

    # -------- TEXT NORMALIZATION --------
    full_text = " ".join(pages.values()).lower()
    full_text = full_text.replace("ﬀ", "ff")
    full_text = re.sub(r"\s+", " ", full_text)

    # -------- AGE --------
    age = re.search(r'(\d{1,2})\s*yrs?', full_text)
    data["age"] = int(age.group(1)) if age else None

    # -------- GENDER --------
    data["gender"] = "male" if "/m" in full_text else "female"

    # -------- SCALP --------
    data["scalp_oily"] = "scalp is oily" in full_text

    # -------- HAIR DENSITY --------
    if re.search(r'hair density.*poor', full_text):
        data["hair_density"] = "poor"
    elif re.search(r'hair density.*medium', full_text):
        data["hair_density"] = "medium"
    elif re.search(r'hair density.*good', full_text):
        data["hair_density"] = "good"
    else:
        data["hair_density"] = None

    # -------- ALOPECIA --------
    if re.search(r'patch of alopecia.*not seen', full_text):
        data["alopecia_patch"] = False
    elif re.search(r'patch of alopecia.*seen', full_text):
        data["alopecia_patch"] = True
    else:
        data["alopecia_patch"] = None

    # -------- DANDRUFF --------
    if re.search(r'dandruff.*(large|high|severe)', full_text):
        data["dandruff_severity"] = "large"
    elif re.search(r'dandruff.*(moderate|medium)', full_text):
        data["dandruff_severity"] = "moderate"
    elif re.search(r'dandruff.*(low|small|mild)', full_text):
        data["dandruff_severity"] = "low"
    elif re.search(r'dandruff.*not seen', full_text):
        data["dandruff_severity"] = "none"
    else:
        data["dandruff_severity"] = None

    # -------- GRAYING --------
        # -------- GRAYING --------
    data["graying_percentage"] = None

    # Extract sentence containing graying
    graying_sentence = None
    sentences = re.split(r'[.\n]', full_text)

    for sentence in sentences:
        if "graying" in sentence:
            graying_sentence = sentence.strip()
            break

    if graying_sentence:
        if "not seen" in graying_sentence:
            data["graying_percentage"] = "0%"
        else:
            graying_match = re.search(
                r'(\d+)\.?[\s][-–]?[\s](\d+)?\.?[\s]*%?',
                graying_sentence
            )

            if graying_match:
                if graying_match.group(2):
                    data["graying_percentage"] = f"{graying_match.group(1)}-{graying_match.group(2)}%"
                else:
                    data["graying_percentage"] = f"{graying_match.group(1)}%"




    # -------- HAIR PER FOLLICLE --------
    follicle = re.search(r'no\.\s*of hair per follicle.*?([\d-]+)', full_text)
    data["hair_per_follicle"] = follicle.group(1) if follicle else None

    # -------- PHASE --------
    data["anagen_present"] = "anagen phase" in full_text
    data["telogen_present"] = "telogen phase" in full_text

    # -------- DIAMETERS --------
    root = re.search(r'hair root\s*[:=]?\s*([\d.]+)\s*μm', full_text)
    shaft = re.search(r'hair shaft\s*[:=]?\s*([\d.]+)\s*μm', full_text)
    tip = re.search(r'hair tip\s*[:=]?\s*([\d.]+)\s*μm', full_text)

    data["hair_root_um"] = float(root.group(1)) if root else None
    data["hair_shaft_um"] = float(shaft.group(1)) if shaft else None
    data["hair_tip_um"] = float(tip.group(1)) if tip else None

    # -------- MEDULLA --------
    medulla = re.search(r'medulla pattern\s*:\s*(\w+)', full_text)
    data["medulla_pattern"] = medulla.group(1) if medulla else None

    # -------- FLOATING TEST --------
    data["floating_test"] = "hair floating test is positive" in full_text
    data["porosity"] = "High" if data["floating_test"] else "Low"

    # -------- SAPTADHATU --------
    page9_text = pages.get(9, "").lower()
    saptadhatu_values = {}

    saptadhatu_patterns = [
        (r'rasa\s+(vridhi|dushti|kshaya)', 'rasa'),
        (r'rakta\s+(vridhi|dushti|kshaya)', 'rakta'),
        (r'mamsa\s+(vridhi|dushti|kshaya)', 'mamsa'),
        (r'meda\s+(vridhi|dushti|kshaya)', 'meda'),
        (r'asthi\s+(vridhi|dushti|kshaya)', 'asthi'),
        (r'majja\s+(vridhi|dushti|kshaya)', 'majja'),
        (r'shukra\s+(vridhi|dushti|kshaya)', 'shukra')
    ]

    for pattern, key in saptadhatu_patterns:
        match = re.search(pattern, page9_text)
        saptadhatu_values[key] = match.group(1) if match else ""

    data["kesh_saptadhatu_parikshan"] = str(saptadhatu_values)

    # -------- SAAMATA --------
    page10_text = pages.get(10, "")
    analysis_match = re.search(r'analysis\s*[:\-]?\s*(\w+)', page10_text, re.IGNORECASE)
    data["kesh_saamata_parikshan"] = analysis_match.group(1) if analysis_match else ""

    # -------- PRAKRUTI --------
    page11_text = pages.get(11, "")
    prakruti_match = re.search(r'note\s*[:\-]?\s*(.*?)(?:\n|$)', page11_text, re.IGNORECASE)
    data["kesh_prakruti_parikshan"] = prakruti_match.group(1) if prakruti_match else ""

    return data



def extract_pages_from_pdf(pdf_path, pages, output_dir):
    doc = fitz.open(pdf_path)
    img_paths = []
    for pg_num in pages:
        page = doc[pg_num]
        pix = page.get_pixmap(dpi=300)
        out_path = os.path.join(output_dir, f"page_{pg_num+1}.png")
        pix.save(out_path)
        img_paths.append(out_path)
    doc.close()
    return img_paths


def crop_page(img_path, layout):
    img = cv2.imread(img_path)
    if img is None: 
        return None, None
    bx1, by1, bx2, by2 = layout["bar"]
    bar_img = img[by1:by2, bx1:bx2]
    return bar_img, img.shape[1]


# ---------------- BAR VALUE LOGIC ---------------- #

def get_value_logic(rel_pos, page_num, row_index):

    # ---------- PAGE 8 ----------
    if str(page_num) == "8":
        attr = ATTRIBUTES_PAGE_8[row_index]

        # Special case: Curly / Straight / Wavy
        if attr["label"] == "Curly / Straight / Wavy":
            if rel_pos < 0.2:
                return "High Curly"
            elif rel_pos < 0.4:
                return "Medium Curly"
            elif rel_pos < 0.6:
                return "Straight"
            elif rel_pos < 0.8:
                return "Medium Wavy"
            else:
                return "High Wavy"

        # Normal 5-zone logic
        if rel_pos < 0.20:
            return f"High {attr['left']}"
        elif rel_pos < 0.40:
            return f"Medium {attr['left']}"
        elif rel_pos < 0.60:
            return "Low / Balanced"
        elif rel_pos < 0.80:
            return f"Medium {attr['right']}"
        else:
            return f"High {attr['right']}"

    # ---------- PAGE 12 ----------
    elif str(page_num) == "12":

        label = ATTRIBUTES_PAGE_12[row_index]

        # 🔥 Special handling ONLY for Tej
        if label == "Tej":
            if rel_pos < 0.28:
                return "+"
            elif rel_pos < 0.60:
                return "++"
            else:
                return "+++"

        # Normal logic for others
        else:
            if rel_pos < 0.33:
                return "+"
            elif rel_pos < 0.66:
                return "++"
            else:
                return "+++"

    return "N/A"


# ---------------- BAR ANALYSIS ---------------- #

def analyze_bars(img, page_num):

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower_cyan = np.array([85, 100, 100])
    upper_cyan = np.array([115, 255, 255])

    mask = cv2.inRange(hsv, lower_cyan, upper_cyan)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    centers = []
    for cnt in contours:
        if cv2.contourArea(cnt) > 20:
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                centers.append((int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])))

    centers = sorted(centers, key=lambda x: x[1])

    page_results = {}
    manual_labels = ATTRIBUTES_PAGE_8 if str(page_num) == "8" else ATTRIBUTES_PAGE_12

    img_width = img.shape[1]

    for i, (cX, cY) in enumerate(centers):
        if i >= len(manual_labels):
            break

        rel_pos = cX / img_width
        label = manual_labels[i]["label"] if isinstance(manual_labels[i], dict) else manual_labels[i]
        page_results[label] = get_value_logic(rel_pos, page_num, i)

    return page_results


st.set_page_config(page_title="Hair Report Processor", layout="centered")

st.title("🧑‍⚕️ Hair Report PDF Processor")
st.markdown("Upload a hair analysis PDF to extract and organize data automatically.")

uploaded_pdf = st.file_uploader("Upload Hair Report PDF", type=["pdf"])

col1, col2 = st.columns(2)
with col1:
    base_dir = st.text_input("Base directory", value="processed_reports")
with col2:
    folder_num = st.selectbox("Folder (1–12)", list(range(1, 13)))

st.markdown("---")
with st.expander("⚙️ Advanced Settings (Optional)"):
    uploaded_config = st.file_uploader("Upload layout_config.json (optional)", type=["json"])
    st.markdown("If not provided, default configuration will be used")

if uploaded_pdf and st.button("🚀 Process PDF", type="primary"):
    with st.spinner("Processing PDF..."):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, uploaded_pdf.name)
            with open(pdf_path, "wb") as f:
                f.write(uploaded_pdf.read())

            try:
                if uploaded_config:
                    cfg = json.load(uploaded_config)
                else:
                    cfg = DEFAULT_LAYOUT_CONFIG
                    st.info("Using default layout configuration")

                st.write("📄 Extracting text from PDF...")
                pages = extract_text(pdf_path)
                features = parse_features(pages)

                gender = features.get("gender", "").capitalize()
                if gender not in ["Male", "Female"]:
                    st.error("❌ Gender could not be detected from PDF")
                    st.stop()

                st.write("💊 Extracting line of treatment...")
                treatment_data = extract_line_of_treatment(pdf_path)
                
                features.update(treatment_data)

                dest_dir = os.path.join(base_dir, gender, str(folder_num))
                os.makedirs(dest_dir, exist_ok=True)

                final_pdf_path = os.path.join(dest_dir, uploaded_pdf.name)
                shutil.copy2(pdf_path, final_pdf_path)

                st.write("🖼️ Extracting images...")
                extract_images(final_pdf_path, os.path.join(dest_dir, "images"), page_number=2)

                st.write("📊 Analyzing trichology data...")
                OUTPUT_DIR = os.path.join(dest_dir, "manual_pages")
                os.makedirs(OUTPUT_DIR, exist_ok=True)

                image_paths = extract_pages_from_pdf(final_pdf_path, PAGES_TO_EXTRACT, OUTPUT_DIR)

                for img_path in image_paths:
                    pg_num = os.path.basename(img_path).split("_")[1].split(".")[0]
                    layout_key = page_to_layout.get(pg_num)

                    if layout_key in cfg:
                        bar_img, original_width = crop_page(img_path, cfg[layout_key])
                        if bar_img is not None:
                            results = analyze_bars(bar_img, pg_num)
                            features.update(results)

                st.write("💾 Saving to CSV...")
                csv_path = os.path.join(base_dir, "output", "hair_report_features.csv")
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)

                features["name"] = os.path.splitext(uploaded_pdf.name)[0]

                if os.path.exists(csv_path):
                    df = pd.read_csv(csv_path)
                    if "name" not in df.columns or features["name"] not in df["name"].values:
                        df = pd.concat([df, pd.DataFrame([features])], ignore_index=True)
                        df.to_csv(csv_path, index=False)
                else:
                    pd.DataFrame([features]).to_csv(csv_path, index=False)

                st.success(f"""
                ✅ *Processing Complete!*
                
                📂 *Stored in:* {dest_dir}  
                👤 *Gender:* {gender}  
                📁 *Folder:* {folder_num}  
                📄 *CSV Updated*  
                🖼️ *Images Extracted*  
                📊 *Trichology Analyzed*
                💊 *Line of Treatment Extracted*
                """)
                
                with st.expander("📋 View Extracted Features"):
                    st.json(features)

            except Exception as e:
                st.error(f"❌ *Error:* {str(e)}")
                st.exception(e)

st.markdown("---")
st.markdown("Developed for automated hair report analysis")
