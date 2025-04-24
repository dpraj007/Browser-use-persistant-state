import re
import base64
import os
import argparse
from datetime import datetime
import sys # For exit
import json # Added for JSON processing

# Function to parse data URI
def parse_image_data_uri(uri_string):
    """
    Parses a data URI string (e.g., data:image/png;base64,...)
    Returns the image type (e.g., 'png') and the base64 data, or None, None if invalid.
    Handles potential whitespace in base64 part.
    """
    # Make matching the base64 part robust to potential internal whitespace
    match = re.match(r'data:image/(?P<type>[a-zA-Z+.-]+);base64,(?P<data>[\s\S]+)', uri_string)
    if match:
        img_type = match.group('type')
        # Clean whitespace from base64 data *after* matching
        b64_data = re.sub(r'\s+', '', match.group('data'))
        return img_type, b64_data
    return None, None


def find_and_replace_data_uris(data_structure, images_dir, image_counter_list, images_extracted_list):
    """
    Recursively traverses dicts and lists to find strings starting with 'data:image',
    saves them, and replaces the string with the relative path in-place.
    Args:
        data_structure: The dict or list to traverse.
        images_dir: Path to the directory to save images.
        image_counter_list: A list containing the current image counter [count].
        images_extracted_list: A list containing the count of successfully extracted images [count].
    Returns:
        True if any replacement occurred within this structure, False otherwise.
    """
    replaced_here = False
    if isinstance(data_structure, dict):
        # Iterate over a copy of items for safe modification
        for key, value in list(data_structure.items()):
            if isinstance(value, str) and value.strip().startswith('data:image'):
                print(f"Found potential image data URI in dict key '{key}'")
                image_counter_list[0] += 1
                current_index = image_counter_list[0]
                relative_image_path = save_log_image(value, images_dir, current_index)
                if relative_image_path:
                    data_structure[key] = relative_image_path # Replace in place
                    images_extracted_list[0] += 1
                    replaced_here = True
                else:
                    print(f"  Failed to save image for key '{key}' (index {current_index}), keeping original URI.")
            elif isinstance(value, (dict, list)):
                 # Recurse and update replaced_here if replacement happens deeper
                 if find_and_replace_data_uris(value, images_dir, image_counter_list, images_extracted_list):
                     replaced_here = True
    elif isinstance(data_structure, list):
         # Iterate over a copy of indices for safe modification
        for index in range(len(data_structure)):
            item = data_structure[index]
            if isinstance(item, str) and item.strip().startswith('data:image'):
                 print(f"Found potential image data URI in list index {index}")
                 image_counter_list[0] += 1
                 current_index = image_counter_list[0]
                 relative_image_path = save_log_image(item, images_dir, current_index)
                 if relative_image_path:
                     data_structure[index] = relative_image_path # Replace in place
                     images_extracted_list[0] += 1
                     replaced_here = True
                 else:
                      print(f"  Failed to save image for list index {index} (index {current_index}), keeping original URI.")
            elif isinstance(item, (dict, list)):
                 # Recurse and update replaced_here if replacement happens deeper
                 if find_and_replace_data_uris(item, images_dir, image_counter_list, images_extracted_list):
                      replaced_here = True
    return replaced_here

# Function to save image and return relative path (modified)
def save_log_image(uri_string, images_dir, image_index):
    """
    Parses a data URI, decodes base64 image data, saves it with a unique name,
    and returns the relative reference path.
    Args:
        uri_string: The full data URI string (e.g., 'data:image/png;base64,...')
        images_dir: The directory to save images in.
        image_index: A unique index for naming the file.
    Returns:
        A string relative path like 'images/log_img_1_timestamp.png' or None if error.
    """
    try:
        img_type, b64_data = parse_image_data_uri(uri_string)
        if not img_type or not b64_data:
             # Reduce noise: only print warning if it looks like a data URI but failed parsing
             if uri_string.strip().startswith('data:image'):
                 print(f"  Warning: Could not parse suspected data URI (starts with {uri_string[:40]}...)")
             return None # Indicate failure to parse

        # Check minimum length, simple heuristic for potentially truncated data
        # PNG header is ~40 bytes, smallest valid PNG ~67 bytes, smallest JPG ~200-600 bytes
        # Base64 encoding increases size by ~33%. Let's set a low threshold.
        MIN_B64_LEN = 100 # Heuristic minimum length for a valid base64 image string
        if len(b64_data) < MIN_B64_LEN:
             print(f"  Warning: Skipping potentially truncated image data URI (length {len(b64_data)} < {MIN_B64_LEN})")
             return None

        file_ext = f".{img_type}" # Use parsed type for extension

        # Generate unique filename using timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"log_img_{image_index}_{timestamp}{file_ext}"
        # Ensure images_dir is used correctly to create the full path
        filepath = os.path.join(images_dir, filename)
        # Create the images dir *inside* save_log_image if it doesn't exist yet
        # This avoids needing to create it before processing if no images are found
        os.makedirs(images_dir, exist_ok=True)

        # Decode and save
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(b64_data)) # Use cleaned b64_data

        # Return relative path using forward slashes - relative to CWD if images_dir is relative
        # Or relative to the dir containing images_dir if it's nested
        # For simplicity, let's make it relative to the images_dir itself.
        # The path written into the JSON should be relative TO THE LOG FILE LOCATION usually.
        # The current argparse setup makes -d relative to CWD.
        # Let's return a path relative to CWD based on image_dir_name provided.
        relative_path = os.path.join(images_dir, filename).replace("\\", "/") # Path relative to CWD
        print(f"  Saved image: {filepath} (Referenced as: {relative_path})")
        return relative_path

    except (base64.binascii.Error) as b64_err:
         print(f"  Error decoding base64 for image index {image_index} (starts with {uri_string[:30]}...): {b64_err}")
         return None
    except (OSError, Exception) as e:
        # Log detailed error but return None
        print(f"  Error processing/saving image index {image_index} (starts with {uri_string[:30]}...): {e}")
        return None # Indicate failure to save

# Main processing function - Modified to work line-by-line and handle JSON
def process_log_file(input_file, output_file, image_dir_name):
    """
    Reads a log file line by line, finds JSON structures, recursively searches
    for base64 'data:image' URIs within them, saves images, replaces URIs
    with relative paths in the JSON, and writes to a new output file.
    """
    # Image directory creation is handled within save_log_image now
    # But print the intended directory
    print(f"Processing log file: {input_file}")
    print(f"Saving images to directory: {image_dir_name}")
    print(f"Writing processed log to: {output_file}")

    # Use lists to pass counters by reference to the recursive function
    image_counter_list = [0]
    images_extracted_list = [0]
    processed_lines = 0


    try:
        with open(input_file, 'r', encoding='utf-8') as infile, \
             open(output_file, 'w', encoding='utf-8') as outfile:

            for line_num, line in enumerate(infile, 1):
                processed_lines += 1
                original_line = line # Keep original for writing if processing fails
                prefix = ""
                json_str = None
                line_modified = False # Flag to track if line was changed

                # Basic check for potential JSON content, handling prefixes
                stripped_line = line.strip()
                if stripped_line.startswith('{') or stripped_line.startswith('['):
                    json_str = stripped_line
                elif ": {" in stripped_line or ": [" in stripped_line:
                    # Try to find start of JSON after a potential prefix
                    match = re.match(r'^(.*?[:\s]+)(\{.*\}|\[.*\])$', stripped_line, re.DOTALL)
                    if match:
                        prefix = match.group(1).rstrip() + " " # Keep prefix, ensure one space separation
                        json_str = match.group(2)
                    else:
                        # Handle cases where prefix detection might fail but JSON is likely present
                        # Look for the first '{' or '['
                        first_brace = stripped_line.find('{')
                        first_bracket = stripped_line.find('[')
                        start_index = -1
                        if first_brace != -1 and first_bracket != -1:
                            start_index = min(first_brace, first_bracket)
                        elif first_brace != -1:
                            start_index = first_brace
                        elif first_bracket != -1:
                             start_index = first_bracket

                        if start_index != -1:
                             prefix = stripped_line[:start_index].rstrip() + " "
                             json_str = stripped_line[start_index:]


                if json_str:
                    try:
                        data = json.loads(json_str)

                        # --- Use recursive function to find and replace image data ---
                        if find_and_replace_data_uris(data, image_dir_name, image_counter_list, images_extracted_list):
                             line_modified = True
                        # --- End of image finding logic ---

                        if line_modified:
                            # Write the modified line back (preserving prefix if any)
                            try:
                                modified_json_str = json.dumps(data)
                                outfile.write(prefix + modified_json_str + '\n')
                            except TypeError as json_err:
                                print(f"Warning: Could not re-serialize JSON on line {line_num} after modification: {json_err}. Writing original line.")
                                outfile.write(original_line)
                        else:
                            # Write the original line if JSON parsed but no image was replaced/found
                            outfile.write(original_line)

                    except json.JSONDecodeError:
                        # Line looked like JSON but wasn't valid, write original
                        outfile.write(original_line)
                    except Exception as e:
                         # Catch other potential errors during JSON processing/recursion
                         print(f"Warning: Error processing JSON structure on line {line_num}: {e}. Writing original line.")
                         outfile.write(original_line) # Write original on error
                else:
                    # Line doesn't contain recognizable JSON, write original
                    # TODO: Add optional non-JSON base64 search here if needed (e.g., for screenshot='...')
                    outfile.write(original_line)

                # Optional progress indicator
                # if processed_lines % 100 == 0:
                #      print(f"Processed {processed_lines} lines...")

        images_extracted = images_extracted_list[0] # Get final count

        print("-" * 30)
        print(f"Processing complete.")
        print(f"Processed {processed_lines} total lines from '{input_file}'.")
        print(f"Found {image_counter_list[0]} potential image URIs.")
        print(f"Successfully extracted and saved {images_extracted} images to '{image_dir_name}'.")
        print(f"Output written to '{output_file}'.")
        # Add note if some URIs were found but not saved
        if image_counter_list[0] > images_extracted:
            print(f"Note: {image_counter_list[0] - images_extracted} potential image URIs were found but could not be saved (see warnings above).")
        print("-" * 30)

    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
    except IOError as e:
        print(f"Error reading/writing file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during file processing: {e}")
        sys.exit(1)


# --- Script Runner (Modified argparse) ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process log files containing JSON lines to extract base64 images, save them, and replace data URIs with file paths.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
  python examples/process_log_images.py -i executor_log.txt -o executor_log_processed.txt -d run_images"""
    )
    # Replaced old args with new ones
    parser.add_argument(
        '-i', '--input',
        required=True, # Make input file mandatory
        help="Path to the input executor log file to process."
    )
    parser.add_argument(
        '-o', '--output',
        required=True, # Make output file mandatory
        help="Path to the output log file where processed content will be written."
    )
    parser.add_argument(
        '-d', '--dir',
        default='images', # Default image directory name
        help="Directory name (relative to CWD or absolute) to save extracted images (default: images)."
    )

    args = parser.parse_args()

    # Basic check: prevent input and output being the same file
    input_abs = os.path.abspath(args.input)
    output_abs = os.path.abspath(args.output)
    if input_abs == output_abs:
        print(f"Error: Input ({args.input}) and output ({args.output}) file paths resolve to the same file.")
        sys.exit(1)

    # Resolve image directory path (relative to CWD or absolute)
    image_dir_path = os.path.abspath(args.dir)


    # Call the main processing function with parsed arguments
    process_log_file(input_abs, output_abs, image_dir_path)