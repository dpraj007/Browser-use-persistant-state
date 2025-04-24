import re
import base64
import os
import argparse
from datetime import datetime
import sys # For exit

# Function to save image and return reference (modified for post-processing context)
def save_log_image(matched_string, images_dir, image_index):
    """
    Decodes base64 image data (from data URI), saves it, and returns a reference path.
    Args:
        matched_string: The full string matched by the regex (e.g., 'data:image/png;base64,...')
        images_dir: The directory to save images in.
        image_index: A unique index for naming the file.
    Returns:
        A string reference like '[Image: ./images/log_img_1_timestamp.png]' or an error string.
    """
    try:
        base64_content = matched_string
        # Determine file extension (simple check based on prefix)
        file_ext = ".png" # Default
        if matched_string.startswith("data:image/"):
            prefix = matched_string.split(",", 1)[0]
            base64_content = matched_string.split(",", 1)[1]
            if "jpeg" in prefix or "jpg" in prefix:
                file_ext = ".jpg"
            elif "gif" in prefix:
                file_ext = ".gif"
            elif "webp" in prefix:
                 file_ext = ".webp"
            # Add other common types if needed

        # Generate unique filename using timestamp for better uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"log_img_{image_index}_{timestamp}{file_ext}"
        filepath = os.path.join(images_dir, filename)

        # Decode and save (handle potential whitespace/newlines in base64 string from log)
        # Base64 strings shouldn't strictly contain whitespace, but logs might introduce it
        cleaned_base64 = re.sub(r'\s+', '', base64_content)
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(cleaned_base64))

        # Return relative path reference suitable for log file
        # Use forward slashes for better cross-platform compatibility in references
        relative_path = os.path.join("./images", filename).replace("\\", "/")
        print(f"  Saved image: {relative_path}")
        return f"[Image: {relative_path}]"

    except (IndexError, base64.binascii.Error, OSError, Exception) as e:
        # Log detailed error but return a simple marker in the file
        print(f"  Error processing/saving image data (starts with {matched_string[:30]}..., length {len(matched_string)}): {e}")
        # Return a marker indicating error, don't return the original (potentially huge) string
        return f"[Error saving image: {str(e)}]"

# Main post-processing function - Takes only the log file path
def process_log_images(log_file_path):
    """Reads a log file, finds base64 'data:image' URIs, saves them,
       and replaces them with references IN PLACE."""

    if not os.path.isfile(log_file_path):
        print(f"Error: Log file not found at {log_file_path}")
        return # Exit the function if file not found

    run_dir = os.path.dirname(log_file_path)
    # Ensure images_dir is relative to the log file's directory
    images_dir = os.path.join(run_dir, "images")
    os.makedirs(images_dir, exist_ok=True) # Ensure images directory exists

    print(f"Processing log file: {log_file_path}")
    print(f"Ensuring images directory exists: {images_dir}")

    try:
        with open(log_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading log file '{log_file_path}': {e}")
        return # Exit the function on read error

    # --- Regex Substitution ---
    image_counter = 0

    # Replacement function using the saver
    def replace_match(match):
        nonlocal image_counter
        image_data = match.group(0) # The whole matched string

        # Basic length check to avoid processing tiny strings that might accidentally match
        # data:image URIs are usually quite long.
        if len(image_data) < 100:
            return image_data # Don't process very short strings

        print(f"Found potential image data URI (starts with: {image_data[:40]}..., length: {len(image_data)})")
        image_counter += 1
        # Pass the whole match to the saver function
        ref = save_log_image(image_data, images_dir, image_counter)
        return ref

    # Regex pattern: Find 'data:image/...' URIs.
    # Allows various image types and assumes base64 follows comma.
    # Handles potential whitespace within the base64 part (cleaned in save_log_image).
    # Make it non-greedy (using +?) just in case of malformed data, though unlikely needed here.
    pattern = r'data:image/[a-zA-Z+.-]+;base64,[A-Za-z0-9+/=\s]+?'

    # Perform substitution using the pattern and replacement function on the whole content
    processed_content = re.sub(pattern, replace_match, content, flags=re.IGNORECASE) # Ignore case for 'data:image' part

    # --- Write Output ---
    if image_counter > 0:
        print(f"\nProcessed {image_counter} image URIs.")
        try:
            # Overwrite the original log file
            output_log_path = log_file_path # Modify in place
            with open(output_log_path, "w", encoding="utf-8") as f:
                f.write(processed_content)
            print(f"Successfully updated log file (in place): {output_log_path}")
        except Exception as e:
            print(f"Error writing updated log file '{output_log_path}': {e}")
    else:
        print("No 'data:image' URIs found in the log file needing processing.")

# --- Script Runner (for standalone execution) ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Post-process executor log files to extract base64 images and replace URIs with file paths in place.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  # Process the latest run's executor_log.txt in ./runs
  python process_log_images.py --latest

  # Process the executor_log.txt in a specific run directory
  python process_log_images.py --run_dir runs/session_run_YYYYMMDD_HHMMSS/task_...

  # Process a specific log file
  python process_log_images.py --file path/to/your/executor_log.txt"""
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--file",
        dest='log_file', # Store argument value in 'log_file'
        help="Path to the specific executor_log.txt file to process."
    )
    group.add_argument(
        "--run_dir",
        help="Path to a specific run directory (e.g., runs/session_run_.../task_...). Processes executor_log.txt within it."
    )
    group.add_argument(
        "--latest",
        action="store_true",
        help="Automatically find and process executor_log.txt in the latest run *task* directory within './runs'."
    )

    args = parser.parse_args()

    target_log_file = None
    base_dir = "runs" # Assuming your runs are here

    if args.log_file:
        target_log_file = args.log_file
    elif args.run_dir:
        # Check if the provided path is a valid directory
        if not os.path.isdir(args.run_dir):
             print(f"Error: Provided run directory '{args.run_dir}' not found or is not a directory.")
             sys.exit(1)
        target_log_file = os.path.join(args.run_dir, "executor_log.txt")
        if not os.path.isfile(target_log_file):
            print(f"Error: 'executor_log.txt' not found in directory '{args.run_dir}'.")
            sys.exit(1)
    elif args.latest:
        try:
            if not os.path.isdir(base_dir):
                 print(f"Error: Base directory '{base_dir}' not found.")
                 sys.exit(1)

            # Find the latest session directory first
            session_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d.startswith("session_run_")]
            if not session_dirs:
                print(f"Error: No session directories found matching 'session_run_*' in '{base_dir}'.")
                sys.exit(1)
            session_dirs.sort()
            latest_session_dir_path = os.path.join(base_dir, session_dirs[-1])

            # Find the latest task directory within the latest session
            task_dirs = [d for d in os.listdir(latest_session_dir_path) if os.path.isdir(os.path.join(latest_session_dir_path, d)) and d.startswith("task_")]
            if not task_dirs:
                 print(f"Error: No task directories found matching 'task_*' in the latest session '{latest_session_dir_path}'.")
                 sys.exit(1)
            task_dirs.sort() # Sort by name (which includes timestamp)
            latest_task_dir_path = os.path.join(latest_session_dir_path, task_dirs[-1])

            target_log_file = os.path.join(latest_task_dir_path, "executor_log.txt")
            print(f"Auto-detected latest task run directory: {latest_task_dir_path}")
            if not os.path.isfile(target_log_file):
                print(f"Error: 'executor_log.txt' not found in the latest task directory '{latest_task_dir_path}'.")
                sys.exit(1)

        except Exception as e:
            print(f"An error occurred finding the latest run: {e}")
            sys.exit(1)

    # Now process the determined file using the main function
    if target_log_file:
        process_log_images(target_log_file) # Call the main processing function
    else:
        # This case should ideally not be reached due to argparse setup, but added as a safeguard
        print("Error: Could not determine target log file.")
        parser.print_help()
        sys.exit(1)
