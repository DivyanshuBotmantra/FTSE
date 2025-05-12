import pdfplumber
import json
from collections import defaultdict
import re 
pdf_path = "./FTSE All-Share Index Fund.pdf"
output_json_path = "./may_12_output_1.json"

# Group words into lines
def group_words_by_line(words, tolerance=1.5):
    lines = defaultdict(list)
    for word in words:
        top_key = round(word["top"] / tolerance) * tolerance
        lines[top_key].append(word)
    return lines

def infer_style_from_span(span):
    fontname = span.get("font", "").lower()
    flags = span.get("flags", 0)

    is_bold = "bold" in fontname or (flags & 2)
    is_italic = "italic" in fontname or "oblique" in fontname or (flags & 1)

    if is_bold and is_italic:
        return "Bold Italic"
    elif is_bold:
        return "Bold"
    elif is_italic:
        return "Italic"
    else:
        return "Regular"
    
def get_dominant_style(spans):
    style_counts = {"Bold Italic": 0, "Bold": 0, "Italic": 0, "Regular": 0}
    for span in spans:
        style = infer_style_from_span(span)
        style_counts[style] += 1

    return max(style_counts, key=style_counts.get)

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

print(f"Merged structured data with font styles saved to {output_json_path}")
