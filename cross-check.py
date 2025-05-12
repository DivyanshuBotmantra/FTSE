import sys
import pdfplumber
import json
import re
import pandas as pd
import traceback
from collections import defaultdict

pdf_path = "./FTSE All-Share Index Fund.pdf"
output_json_path = "./final_output_pdf_to_json.json"

# Group words into lines
def group_words_by_line(words, tolerance=1.5):
    lines = defaultdict(list)
    for word in words:
        top_key = round(word["top"] / tolerance) * tolerance
        lines[top_key].append(word)
    return lines

# Font style detection based on font name's number
def detect_font_style(font_name):
    font_lower = font_name.lower()

    # Extract the number after the '-' in the font name (e.g., UniversCom-55Oblique)
    try:
        font_number = int(re.search(r'-(\d+)', font_name).group(1))  # Extracts number after '-'
    except AttributeError:
        font_number = None  # If no number is found, set it to None

    # Determine if the font is bold based on the extracted number
    if font_number is not None and font_number > 45:
        is_bold = True
    else:
        is_bold = "bold" in font_lower or "bd" in font_lower  # Fallback to text-based detection

    # Determine if the font is italic
    is_italic = "italic" in font_lower or "oblique" in font_lower or "it" in font_lower

    # Return the appropriate font style
    if is_bold and is_italic:
        return "Bold Italic"
    elif is_bold:
        return "Bold"
    elif is_italic:
        return "Italic"
    else:
        return "Regular"
    


# Extract structured info
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

                # Bounding box
                x0 = min(w['x0'] for w in line_words)
                x1 = max(w['x1'] for w in line_words)
                top = min(w['top'] for w in line_words)
                bottom = max(w['bottom'] for w in line_words)

                # Get all chars in this line range (bounding box match)
                line_chars = [
                    c for c in chars
                    if c['x0'] >= x0 and c['x1'] <= x1 and c['top'] >= top and c['bottom'] <= bottom
                ]

                if line_chars:
                    fontname = line_chars[0].get("fontname", "")
                    size = line_chars[0].get("size", None)
                    font_style = detect_font_style(fontname)
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
                            "bottom": w["bottom"]
                        }
                        for w in line_words
                    ]
                }

                formatted_data.append(line_block)

    return formatted_data


# Run & Save Output
final_data = extract_pdf_to_json(pdf_path)
with open(output_json_path, "w", encoding="utf-8") as f:
    json.dump(final_data, f, indent=2)

print(f"✅ Structured data with accurate font styles saved to: {output_json_path}")
