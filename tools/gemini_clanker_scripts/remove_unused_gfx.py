import os
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION ---
GFX_DIR = Path("gfx")

SCAN_DIRS = [
    Path("common"),
    Path("interface"),
    Path("events"),
    Path("history"),
    Path("localisation")
]

# Folders or patterns inside gfx/ that should NEVER be touched (like flags)
EXCLUDED_GFX_PATTERNS = ("gfx/flags",)

# Set to False so it deletes the files right away
DRY_RUN = False  
# ---------------------

# Regex to match any path starting with gfx/ inside quotes
GFX_PATH_REGEX = re.compile(r'["\']?(gfx/[^"\'()\s<>]+)["\']?', re.IGNORECASE)

def get_all_gfx_files(gfx_path):
    """Recursively collects all relative file paths inside the gfx directory."""
    print("Indexing gfx/ directory...")
    gfx_set = set()
    if not gfx_path.exists():
        print(f"Error: Directory '{gfx_path}' not found. Make sure you are running this from your mod root folder.")
        return gfx_set
    
    for file_path in gfx_path.rglob("*"):
        if file_path.is_file():
            rel_path = file_path.relative_to(Path("."))
            rel_path_str = str(rel_path).replace("\\", "/")
            
            # Skip flags and any other excluded patterns
            if any(exc in rel_path_str for exc in EXCLUDED_GFX_PATTERNS):
                continue
                
            gfx_set.add(rel_path_str)
            
    print(f"Found {len(gfx_set):,} eligible files in gfx/ (flags excluded).")
    return gfx_set

def scan_file_for_gfx(file_path):
    """Reads a single file and extracts all referenced gfx paths."""
    found = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            matches = GFX_PATH_REGEX.findall(content)
            for match in matches:
                found.add(match.replace("\\", "/").strip('"\''))
    except Exception as e:
        print(f"Could not read {file_path}: {e}")
    return found

def get_referenced_gfx():
    """Scans target directories concurrently using multiple threads."""
    print("Scanning mod script files for references...")
    text_files = []
    for scan_dir in SCAN_DIRS:
        if scan_dir.exists():
            text_files.extend([p for p in scan_dir.rglob("*") if p.is_file()])
        else:
            print(f"Notice: Directory '{scan_dir}' does not exist, skipping.")

    print(f"Found {len(text_files):,} script/definition files to scan.")
    
    referenced_set = set()
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(scan_file_for_gfx, fp): fp for fp in text_files}
        for future in as_completed(futures):
            referenced_set.update(future.result())
            
    print(f"Found {len(referenced_set):,} unique gfx references in files.")
    return referenced_set

def main():
    start_time = time.time()
    
    all_gfx = get_all_gfx_files(GFX_DIR)
    if not all_gfx:
        return

    referenced_gfx = get_referenced_gfx()

    # Case-insensitive mapping for robust matching
    all_gfx_lower_map = {path.lower(): path for path in all_gfx}
    referenced_gfx_lower = {path.lower() for path in referenced_gfx}

    unused_lower = all_gfx_lower_map.keys() - referenced_gfx_lower
    unused_files = [all_gfx_lower_map[k] for k in unused_lower]

    print(f"\n--- RESULTS ---")
    print(f"Total eligible GFX files: {len(all_gfx):,}")
    print(f"Unused GFX files found: {len(unused_files):,}")

    if not unused_files:
        print("No unused files found. Everything is clean!")
        return

    print("\nDeleting unused files...")
    deleted_count = 0
    for file_path_str in unused_files:
        file_path = Path(file_path_str)
        try:
            if file_path.exists():
                file_path.unlink()
                deleted_count += 1
        except Exception as e:
            print(f"Failed to delete {file_path}: {e}")
            
    print(f"Successfully deleted {deleted_count:,} unused files.")
    print(f"Completed in {time.time() - start_time:.2f} seconds.")

if __name__ == "__main__":
    main()