import json

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

def extract_headers(json_data):
    headers = []
    for block in json_data:
        for word in block.get('words', []):
            if word['text'].strip().lower() in ['security', 'holding', 'bid', 'total']:
                headers.append({
                    'text': word['text'],
                    'x0': word['x0'],
                    'x1': word['x1']
                })
    return headers

# ====== MAIN ======
if __name__ == "__main__":
    with open("./JSON_FTSE_ALL_SHARE_INDEX_EXTRACTED.json", "r") as file:  # Replace with your JSON filename
        data = json.load(file)

    # Step 1: Extract headers with coordinates
    headers = extract_headers(data)

    # Step 2: Ask for user input (x0 and x1)
    try:
        x0 = float(input("Enter x0 of the value: "))
        x1 = float(input("Enter x1 of the value: "))

        # Step 3: Find the best matching header
        matching_header = find_best_matching_header(headers, x0, x1)

        if matching_header:
            print(f" The value belongs to the column: {matching_header}")
        else:
            print("No matching header found.")
    except Exception as e:
        print("Invalid input. Please enter numeric x0 and x1 values.")
