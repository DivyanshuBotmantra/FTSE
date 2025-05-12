import pdfplumber
import json
from collections import defaultdict

pdf_path = "./FTSE All-Share Index Fund.pdf"
output_json_path = "./extracted_data.json"


formatted_data = []

def group_words_by_line(words, tolerance=1.5):
    lines = defaultdict(list)
    for word in words:
        top_key = round(word["top"] / tolerance) * tolerance
        lines[top_key].append(word)
    return lines

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages, start=1):
        words = page.extract_words(
            keep_blank_chars=True,
            x_tolerance=1,
            y_tolerance=1,
            use_text_flow=True
        )

        grouped_lines = group_words_by_line(words)

        for top_key in sorted(grouped_lines):
            line_words = sorted(grouped_lines[top_key], key=lambda w: w['x0'])
            line_text = " ".join([w['text'] for w in line_words])
            line_block = {
                "page": page_num,
                "line_text": line_text,
                "line_spacing": 20.0,
                "top": line_words[0]['top'],
                "bottom": line_words[0]['bottom'],
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

# Save to JSON
with open(output_json_path, "w", encoding="utf-8") as f:
    json.dump(formatted_data, f, indent=2)

print(f"Formatted PDF data saved to {output_json_path}")
