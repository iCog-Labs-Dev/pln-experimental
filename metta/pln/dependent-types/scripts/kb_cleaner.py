import sys

if len(sys.argv) != 3:
    print("Usage: python remove_removed.py <input_file> <output_file>")
    sys.exit(1)

input_file = sys.argv[1]
output_file = sys.argv[2]

with open(input_file, "r", encoding="utf-8") as fin, \
     open(output_file, "w", encoding="utf-8") as fout:
    for line in fin:
        if "; REMOVED" not in line:
            fout.write(line)

print(f"Done! Cleaned file saved as '{output_file}'.")
