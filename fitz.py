import fitz  # PyMuPDF
import json
from collections import defaultdict

pdf_path = "./FTSE All-Share Index Fund.pdf"
output_json_path = "./may_12_output_final.json"

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

def extract_pdf_to_json(pdf_path, y_tolerance=1.0):
    formatted_data = []

    with fitz.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf, start=1):
            words_raw = page.get_text("words")  # list of (x0, y0, x1, y1, word, block_no, line_no, word_no)
            words = [
                {
                    "text": w[4],
                    "x0": w[0],
                    "top": w[1],
                    "x1": w[2],
                    "bottom": w[3],
                    "block_no": w[5],
                    "line_no": w[6],
                }
                for w in words_raw if w[4].strip()
            ]

            # Group words by visual line (within y_tolerance)
            lines_grouped = defaultdict(list)
            for word in words:
                key_found = False
                for key in lines_grouped:
                    if abs(key - word["top"]) <= y_tolerance:
                        lines_grouped[key].append(word)
                        key_found = True
                        break
                if not key_found:
                    lines_grouped[word["top"]].append(word)

            for top in sorted(lines_grouped.keys()):
                line_words = sorted(lines_grouped[top], key=lambda w: w["x0"])
                line_text = " ".join(w["text"] for w in line_words)

                x0 = min(w["x0"] for w in line_words)
                x1 = max(w["x1"] for w in line_words)
                top_val = min(w["top"] for w in line_words)
                bottom = max(w["bottom"] for w in line_words)

                # Get the first char in bounding box for font info
                spans = page.get_text("dict")["blocks"]
                fontname = ""
                size = None
                style = "Unknown"

                # Find matching spans to get font
                for block in spans:
                    if block["type"] != 0:
                        continue
                    for line in block["lines"]:
                        for span in line["spans"]:
                            if span["bbox"][1] >= top_val - 1 and span["bbox"][3] <= bottom + 1:
                                fontname = span.get("font", "")
                                size = span.get("size", None)
                                style = infer_style_from_span(span)
                                break
                        if fontname:
                            break
                    if fontname:
                        break

                line_block = {
                    "page": page_num,
                    "line_text": line_text,
                    "top": top_val,
                    "bottom": bottom,
                    "bounding_box": {
                        "x0": x0,
                        "x1": x1,
                        "top": top_val,
                        "bottom": bottom,
                        "width": x1 - x0,
                        "height": bottom - top_val
                    },
                    "font": {
                        "fontname": fontname,
                        "size": size,
                        "style": style
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

# Run & save
final_data = extract_pdf_to_json(pdf_path)
with open(output_json_path, "w", encoding="utf-8") as f:
    json.dump(final_data, f, indent=2)

print(f"✅ Grouped & styled data saved to: {output_json_path}")
