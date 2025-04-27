import os
import glob
import re
import shutil
import argparse
import sys

# Regex to find the content between the prompt and response markers
# Handles 'Model=' or 'model=', captures content non-greedily across multiple lines
prompt_block_regex = re.compile(
    r"=== LLM Prompt \([Mm]odel=[^)]+\) ===(.*?)=== LLM Response ===",
    re.DOTALL # Make '.' match newline characters
)

def count_prompts_in_file(filepath):
    """Counts distinct prompt blocks in a given log file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        matches = prompt_block_regex.findall(content)
        return len(matches)
    except FileNotFoundError:
        print(f"    - Log file not found: {filepath}", file=sys.stderr)
        return None
    except UnicodeDecodeError as e:
        print(f"    - Unicode error reading {filepath}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"    - Unexpected error reading {filepath}: {e}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Find run/task folders in the current directory with fewer than a "
                    "specified number of prompt blocks in executor_log.txt and move "
                    "them to a 'failed_tasks' subfolder."
    )
    # Only threshold argument remains
    parser.add_argument(
        "-t", "--threshold",
        type=int,
        default=5,
        help="Move folders with strictly *fewer* prompts than this threshold (default: 5)."
    )
    args = parser.parse_args()

    # Determine source and destination paths based on script location
    script_path = os.path.abspath(__file__)
    source_path = os.path.dirname(script_path)
    dest_path = os.path.join(source_path, "failed_tasks") # Destination is always 'failed_tasks' subdirectory

    print(f"Source directory (script location): {source_path}")
    print(f"Destination directory: {dest_path}")

    # --- Create Destination ---
    try:
        os.makedirs(dest_path, exist_ok=True)
        print(f"Ensured destination directory exists: {dest_path}")
    except OSError as e:
        print(f"Error: Could not create destination directory {dest_path}: {e}", file=sys.stderr)
        sys.exit(1)

    # --- Find Candidate Folders ---
    print(f"Scanning '{source_path}' for run_* and task_* folders...")
    run_pattern = os.path.join(source_path, "run_*")
    task_pattern = os.path.join(source_path, "task_*")

    candidate_folders = []
    for pattern in [run_pattern, task_pattern]:
        for item in glob.glob(pattern):
            # Ensure it's a directory AND it's not the destination directory itself
            if os.path.isdir(item) and os.path.abspath(item) != dest_path:
                candidate_folders.append(item)

    if not candidate_folders:
        print("No run_* or task_* folders found (excluding the destination folder).")
        sys.exit(0)

    print(f"Found {len(candidate_folders)} candidate folders. Checking prompt counts...")

    # --- Process Each Folder ---
    folders_to_move = []
    for folder_path in candidate_folders:
        folder_name = os.path.basename(folder_path)
        print(f"  Checking folder: {folder_name}")
        log_file = os.path.join(folder_path, "executor_log.txt")

        if not os.path.exists(log_file):
            print(f"    - executor_log.txt not found. Skipping.")
            continue

        prompt_count = count_prompts_in_file(log_file)

        if prompt_count is None:
            print(f"    - Could not count prompts. Skipping.")
            continue

        print(f"    - Prompt blocks found: {prompt_count}")
        if prompt_count < args.threshold:
            print(f"    - Count ({prompt_count}) is less than threshold ({args.threshold}). Marking for move.")
            folders_to_move.append(folder_path)
        else:
             print(f"    - Count ({prompt_count}) is not less than threshold ({args.threshold}).")


    # --- Move Folders ---
    print("-" * 30)
    if not folders_to_move:
        print("No folders met the criteria to be moved.")
    else:
        print(f"Moving {len(folders_to_move)} folders to '{dest_path}'...")
        moved_count = 0
        skipped_count = 0
        for folder_path in folders_to_move:
            folder_name = os.path.basename(folder_path) # Get just the folder name
            dest_folder_path = os.path.join(dest_path, folder_name)

            # Check if destination already exists
            if os.path.exists(dest_folder_path):
                print(f"  - WARNING: Destination '{dest_folder_path}' already exists. Skipping move for '{folder_name}'.")
                skipped_count += 1
                continue

            # Perform the move
            try:
                shutil.move(folder_path, dest_folder_path)
                print(f"  - Moved '{folder_name}' to '{dest_path}'")
                moved_count += 1
            except Exception as e:
                print(f"  - ERROR: Failed to move '{folder_name}': {e}", file=sys.stderr)
                skipped_count += 1

        print("-" * 30)
        print("Move Summary:")
        print(f"  Successfully moved: {moved_count}")
        print(f"  Skipped (dest exists or error): {skipped_count}")

    print("\nScript finished.")

if __name__ == "__main__":
    main()