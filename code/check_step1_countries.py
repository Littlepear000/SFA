from pathlib import Path
import re


folder1 = Path(r"C:\Users\xli7\OneDrive - International Monetary Fund (PRD)\Shelley_My Projects\SFA\staff_reports\pdf staff reports\2021-2026 staff reports")
folder2 = Path(r"Q:\DATA\FP\Staff Working Files\ASolovyeva\SFA\staff_reports\pdf staff reports 2021-2026 FINAL")


pattern = re.compile(
    r"^(.+?_\d{4}-\d{2}-\d{2})",
    re.IGNORECASE
)

folder1_keys = set()
folder2_keys = set()

for file in folder1.iterdir():
    if file.is_file() and file.suffix.lower() == ".pdf":
        match = pattern.match(file.stem)
        if match:
            folder1_keys.add(match.group(1))

for file in folder2.iterdir():
    if file.is_file():
        match = pattern.match(file.stem)
        if match:
            folder2_keys.add(match.group(1))

missing = folder1_keys - folder2_keys
matched = folder1_keys & folder2_keys

print(f"Folder 1 total: {len(folder1_keys)}")
print(f"Matched: {len(matched)}")
print(f"Missing: {len(missing)}")

if missing:
    print("\nMissing:")
    for key in sorted(missing):
        print(key)