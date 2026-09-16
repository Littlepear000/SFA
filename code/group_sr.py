from pathlib import Path
import re
import shutil

folder = Path(r"staff_reports/pdf staff reports")

pattern = re.compile(r"_(\d{4})-\d{2}-\d{2}", re.IGNORECASE)


def get_batch(year):
    if 2021 <= year <= 2026:
        return "2021-2026"
    elif 2016 <= year <= 2020:
        return "2016-2020"
    elif 2011 <= year <= 2015:
        return "2011-2015"
    elif 2006 <= year <= 2010:
        return "2006-2010"
    elif 2001 <= year <= 2005:
        return "2001-2005"
    elif 1996 <= year <= 2000:
        return "1996-2000"
    else:
        return "Other"


for file in folder.glob("*.pdf"):
    match = pattern.search(file.name)

    if not match:
        print(f"Skipped: {file.name}")
        continue

    year = int(match.group(1))
    batch = get_batch(year)

    target_folder = folder / batch
    target_folder.mkdir(exist_ok=True)

    target = target_folder / file.name
    shutil.move(str(file), str(target))

    print(f"{file.name} -> {batch}")



### Compare two 2021-2016 folders
from pathlib import Path

folder1 = Path(r"staff_reports/pdf staff reports/2021-2026")
folder2 = Path(r"staff_reports/pdf staff reports/2021-2026 staff reports")

files1 = {f.name for f in folder1.iterdir() if f.is_file()}
files2 = {f.name for f in folder2.iterdir() if f.is_file()}

only_in_folder1 = files1 - files2
only_in_folder2 = files2 - files1

print("only in zip file:")
for file in sorted(only_in_folder1):
    print(file)

print("\nonly in old 2021-2026 staff reports:")
for file in sorted(only_in_folder2):
    print(file)