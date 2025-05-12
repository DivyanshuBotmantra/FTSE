import sys
import pdfplumber
import json
import re
import pandas as pd
import traceback
from collections import  *

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

# Extract lines based on regex patterns
def extract_by_line_text(data, start_pattern, end_pattern, inclusive=True):
    start_idx = end_idx = None
    for i, block in enumerate(data):
        if re.search(start_pattern, block.get("line_text", "")):
            start_idx = i
            break
    if start_idx is not None:
        for j in range(start_idx + 1, len(data)):
            if re.search(end_pattern, data[j].get("line_text", "")):
                end_idx = j
                break
    if start_idx is not None and end_idx is not None:
        result = data[start_idx:end_idx + 1] if inclusive else data[start_idx + 1:end_idx]
        
        # Don't save to JSON, just return the result
        return result
    return []

def find_best_matching_header(headers, x0, x1):
    best_match = None
    best_score = float('inf')
    input_mid = (x0 + x1) / 2

    for header in headers:
        h_start = header['x0']
        h_end = header['x1']
        h_mid = (h_start + h_end) / 2

        score = min(abs(h_start - x0), abs(h_end - x1), abs(h_mid - input_mid))

        if score < best_score:
            best_score = score
            best_match = header['text']

    return best_match

def extract_by_header_coords(header_lines, data):
    results = []
    headers = header_lines
    # If num_fields is provided, use it, otherwise use the count of headers
    header_texts = [f'H{i+1}' for i in range(len(headers))]
    # Create a mapping of original header names to dynamic labels (H1, H2, etc.)
    header_mapping = {headers[i]['text']: header_texts[i] for i in range(len(headers))}
    for block in data:
        row_data = {header: None for header in header_texts}  # Initialize row data with H1, H2, H3, ...
        page_num = block['page']  # Get the page number from the block
        row_data['page_number'] = page_num  # Add the page number to the row data
        # Iterate over words in the block and assign them to corresponding headers
        for word in block.get('words', []):
            header_text = find_best_matching_header(headers, word['x0'], word['x1'])
            if header_text:
                # Map the header text (e.g., 'Security') to its corresponding dynamic label (e.g., 'H1')
                if header_text in header_mapping:
                    dynamic_header = header_mapping[header_text]
                    row_data[dynamic_header] = word['text']  # Assign the word text to the corresponding dynamic header
        results.append(row_data)

    return results

def process_page_headers(results, header_each_page="yes", header_row=(11, 14)):
    from collections import defaultdict

    rows_to_skip = header_row[1]
    start_page = results[0]['page_number']
    filtered_results = []

    # Step 1: Separate all rows by page
    page_rows = defaultdict(list)
    for row in results:
        page_rows[row['page_number']].append(row)

    if header_each_page.lower() == "yes":
        # Merge rows on start page only
        start_page_data = page_rows[start_page]
        merged_header_rows = start_page_data[header_row[0] - 1:header_row[1]]
        merged_row = {}

        for key in start_page_data[0].keys():
            if key == 'page_number':
                merged_row[key] = start_page
            else:
                values = [row.get(key) for row in merged_header_rows if row.get(key)]
                merged_row[key] = " ".join(values) if values else None

        # Reconstruct page 1 with merged header
        filtered_start_page = (
            start_page_data[:header_row[0] - 1] +
            [merged_row] +
            start_page_data[header_row[1]:]
        )
        filtered_results.extend(filtered_start_page)

        # Process other pages by skipping first N rows
        for page_number, rows in page_rows.items():
            if page_number == start_page:
                continue
            filtered_results.extend(rows[rows_to_skip:])

    else:
        # If no repeated header, just skip rows in pages after first page
        for page_number, rows in page_rows.items():
            if page_number == start_page:
                filtered_results.extend(rows)  # Keep all
            else:
                filtered_results.extend(rows[rows_to_skip:])  # Skip 1–8

    return filtered_results


def save_results_to_excel(results, excel_path):
    df = pd.DataFrame(results)
    df.to_excel(excel_path, index=False)
    print(f"Saved successfully to {excel_path} ✅")


def find_valid_header_lines(data):
    for i, block in enumerate(data):
        word_count = len(block.get("words", []))  # Corrected: words should be a list
        if word_count == len(data[0].get("words", [])):
            fields = [
                {
                    "text": w["text"],
                    "x0": w["x0"],
                    "x1": w["x1"],
                    "top": w["top"],
                    "bottom": w["bottom"]
                } for w in block["words"]
            ]
            print(f"Found matching header at line {i}. Breaking out of the loop.")  # Debugging message
            return fields  # Directly returning the fields list
        else:
            print(f"Skipping line {i} as word count {word_count} doesn't match header count.")
    return []  # Return empty list if no matching header is found

def main():
    if len(sys.argv) != 5:
        print("\nUsage:\npython script.py <pdf_input_path> <excel_output_path> <request_model> <request_model_json>\n")
        sys.exit(1)

    pdf_input_path = sys.argv[1]
    excel_output_path = sys.argv[2]
    request_model_name = sys.argv[3]  # This is the request model name
    request_model_path = sys.argv[4]

    try:
        # Load the request model JSON
        with open(request_model_path, "r") as f:
            request_models = json.load(f)

        # Find the request model from the JSON by name
        request_model = next((model for model in request_models if model["request_model"] == request_model_name), None)
        if not request_model:
            print(f"Error: Request model '{request_model_name}' not found.")
            sys.exit(1)

        # Extract headers and regex patterns from the request model
        start_regex = request_model["start_regex"]
        end_regex = request_model["end_regex"]
        header_lines = request_model["headers"]

        full_data = extract_pdf_to_json(pdf_input_path)
        extracted = extract_by_line_text(full_data, start_regex, end_regex)

        if header_lines:
            results = extract_by_header_coords(header_lines, extracted)
            final_results = process_page_headers(results, header_each_page="no", header_row=(3, 6))
            save_results_to_excel(final_results, excel_output_path)
        else:
            print("⚠️ No header lines found or provided. Nothing to extract.")

    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
