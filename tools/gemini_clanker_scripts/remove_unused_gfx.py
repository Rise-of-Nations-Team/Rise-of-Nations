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
    Path("localisation"),
    Path("portraits"),
    Path("common/portraits")
]

# Folders or patterns inside gfx/ that should NEVER be touched
EXCLUDED_GFX_PATTERNS = (
    "gfx/flags",
    "gfx/entities",
    "gfx/fonts",
    "gfx/models"
)

# Deletes files right away
DRY_RUN = False  
# ---------------------

# Regex to match any path starting with gfx/ inside quotes
GFX_PATH_REGEX = re.compile(r'["\']?(gfx/[^"\'()\s<>]+)["\']?', re.IGNORECASE)

def get_safe_path(path_str):
    """Adds the Windows long-path prefix to bypass the 260 character limit."""
    abs_path = os.path.abspath(path_str)
    if os.name == 'nt' and not abs_path.startswith('\\\\?\\'):
        if abs_path.startswith('\\\\'):
            return '\\\\?\\UNC\\' + abs_path[2:]
        return '\\\\?\\' + abs_path
    return abs_path

def get_all_gfx_files(gfx_path):
    """Recursively collects all relative file paths inside the gfx directory."""
    print("Indexing gfx/ directory...")
    gfx_set = set()
    if not gfx_path.exists():
        print(f"Error: Directory '{gfx_path}' not found. Make sure you are running this from your mod root folder.")
        return gfx_set
    
    for file_path in gfx_path.rglob("*"):
        try:
            if file_path.is_file():
                rel_path = file_path.relative_to(Path("."))
                rel_path_str = str(rel_path).replace("\\", "/")
                
                # Skip excluded patterns
                if any(exc in rel_path_str for exc in EXCLUDED_GFX_PATTERNS):
                    continue
                    
                gfx_set.add(rel_path_str)
        except Exception:
            continue
            
    print(f"Found {len(gfx_set):,} eligible files in gfx/ (protected folders excluded).")
    return gfx_set

def scan_file_for_gfx(file_path):
    """Reads a single file and extracts all referenced gfx paths."""
    found = set()
    try:
        safe_fp = get_safe_path(file_path)
        with open(safe_fp, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            matches = GFX_PATH_REGEX.findall(content)
            for match in matches:
                found.add(match.replace("\\", "/").strip('"\''))
    except Exception:
        pass
    return found

def get_referenced_gfx():
    """Scans target directories concurrently using multiple threads."""
    print("Scanning mod script and portrait files for references...")
    text_files = []
    for scan_dir in SCAN_DIRS:
        if scan_dir.exists():
            for p in scan_dir.rglob("*"):
                try:
                    if p.is_file():
                        text_files.append(p)
                except Exception:
                    continue
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
        try:
            safe_file_path = get_safe_path(file_path_str)
            if os.path.exists(safe_file_path):
                os.remove(safe_file_path)
                deleted_count += 1
        except Exception as e:
            print(f"Failed to delete {file_path_str}: {e}")
            
    print(f"Successfully deleted {deleted_count:,} unused files.")
    print(f"Completed in {time.time() - start_time:.2f} seconds.")

if __name__ == "__main__":
    main()