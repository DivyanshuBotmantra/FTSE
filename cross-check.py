import sys
import pdfplumber
import json
import re
import traceback
from collections import defaultdict, Counter

pdf_path = "./FTSE All-Share Index Fund.pdf"
output_json_path = "./final_output_pdf_to_json.json"

# Group words into lines
def group_words_by_line(words, tolerance=1.5):
    lines = defaultdict(list)
    for word in words:
        top_key = round(word["top"] / tolerance) * tolerance
        lines[top_key].append(word)
    return lines

# Detect font style based on fontname
def detect_font_style_from_chars(chars):
    styles = []
    for c in chars:
        font_name = c.get("fontname", "").lower()
        try:
            font_number = int(re.search(r'-(\d+)', font_name).group(1))
        except (AttributeError, ValueError):
            font_number = None

        is_bold = (font_number is not None and font_number > 45) or "bold" in font_name or "bd" in font_name
        is_italic = "italic" in font_name or "oblique" in font_name or "it" in font_name

        if is_bold and is_italic:
            styles.append("Bold Italic")
        elif is_bold:
            styles.append("Bold")
        elif is_italic:
            styles.append("Italic")
        else:
            styles.append("Regular")

    if styles:
        return Counter(styles).most_common(1)[0][0]
    else:
        return "Unknown"

# Get font info for a single word
def get_word_font_info(word, chars):
    matched_chars = [
        c for c in chars
        if c['x0'] >= word['x0'] and c['x1'] <= word['x1'] and
           c['top'] >= word['top'] and c['bottom'] <= word['bottom']
    ]
    if not matched_chars:
        return {"fontname": "", "size": None, "style": "Unknown"}

    fontname = matched_chars[0].get("fontname", "")
    size = matched_chars[0].get("size", None)
    style = detect_font_style_from_chars(matched_chars)

    return {
        "fontname": fontname,
        "size": size,
        "style": style
    }

# Extract structured PDF data
def extract_pdf_to_json(pdf_path):
    formatted_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(
                keep_blank_chars=True,
                x_tolerance=1,
                y_tolerance=1,
                use_text_flow=True
            )
            grouped_lines = group_words_by_line(words)
            chars = page.chars

            for top_key in sorted(grouped_lines):
                line_words = sorted(grouped_lines[top_key], key=lambda w: w['x0'])
                line_text = " ".join([w['text'] for w in line_words])

                x0 = min(w['x0'] for w in line_words)
                x1 = max(w['x1'] for w in line_words)
                top = min(w['top'] for w in line_words)
                bottom = max(w['bottom'] for w in line_words)

                line_chars = [
                    c for c in chars
                    if c['x0'] >= x0 and c['x1'] <= x1 and c['top'] >= top and c['bottom'] <= bottom
                ]

                if line_chars:
                    fontname = line_chars[0].get("fontname", "")
                    size = line_chars[0].get("size", None)
                    font_style = detect_font_style_from_chars(line_chars)
                else:
                    fontname = ""
                    size = None
                    font_style = "Unknown"

                line_block = {
                    "page": page_num,
                    "line_text": line_text,
                    "line_spacing": 20.0,
                    "top": top,
                    "bottom": bottom,
                    "bounding_box": {
                        "x0": x0,
                        "x1": x1,
                        "top": top,
                        "bottom": bottom,
                        "width": x1 - x0,
                        "height": bottom - top
                    },
                    "font": {
                        "fontname": fontname,
                        "size": size,
                        "style": font_style
                    },
                    "words": [
                        {
                            "text": w["text"],
                            "x0": w["x0"],
                            "x1": w["x1"],
                            "top": w["top"],
                            "bottom": w["bottom"],
                            "font": get_word_font_info(w, chars)
                        }
                        for w in line_words
                    ]
                }

                formatted_data.append(line_block)

    return formatted_data

# Run and Save
try:
    final_data = extract_pdf_to_json(pdf_path)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2)
    print(f"✅ Structured data with per-word font info saved to: {output_json_path}")
except Exception as e:
    print("❌ Error occurred while processing PDF:")
    traceback.print_exc()
