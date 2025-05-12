import json
from collections import defaultdict

# Load the JSON
with open("./extracted_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Config
tolerance = 2
char_width = 4  # Approx. width of one character in coordinate space

# Helper: group words by vertical 'top' (line detection)
def group_words_by_line(words, tolerance):
    lines = defaultdict(list)
    for word in words:
        top = word['top']
        matched = False
        for key in lines:
            if abs(top - key) <= tolerance:
                lines[key].append(word)
                matched = True
                break
        if not matched:
            lines[top].append(word)
    return lines

# Build text layout with spacing based on x0
output_lines = []
for page in data:
    word_lines = group_words_by_line(page['words'], tolerance)
    for top in sorted(word_lines.keys()):
        words = sorted(word_lines[top], key=lambda w: w['x0'])
        
        # Estimate line width
        max_x = int(max(w['x1'] for w in words) / char_width) + 10
        line = [" "] * max_x

        
        for word in words:
            x_index = int(word['x0'] / char_width)
            text = word['text']
            # Place text in line, respecting positions
            for i, char in enumerate(text):
                if x_index + i < len(line):
                    line[x_index + i] = char

        output_lines.append("".join(line).rstrip())
    output_lines.append("\n")

# Write to text file
with open("text_file_json_to_text_01.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))

print("Grid-style text saved to reconstructed_grid_text.txt")
