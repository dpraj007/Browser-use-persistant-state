import os
import glob
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.axes import CategoryAxis, ValueAxis
from datetime import datetime
import math # For calculating bins
import os
import re

def create_distribution_matrix(results):
    """ Calculates the distribution of prompt counts into bins of size 5. """
    bins = {}
    # Create bins 0-4, 5-9, ..., 95-99
    for i in range(0, 100, 5):
        bin_key = f"{i}-{i+4}"
        bins[bin_key] = 0
    bins[">= 100"] = 0
    bins["Errors"] = 0

    total_files_checked = len(results)

    for _, count, error in results:
        if error:
            bins["Errors"] += 1
            continue
        # count will be None if there was an error, handled above
        if count is None: # Should be caught by error check, but safer
             bins["Errors"] += 1
             continue

        if count < 0:
            # Handle potentially negative counts if they can occur
            print(f"Warning: Negative count {count} found. Placing in Errors.")
            bins["Errors"] += 1
        elif count >= 100:
            bins[">= 100"] += 1
        else:
            # Calculate the lower bound of the bin (e.g., 0 for 0-4, 5 for 5-9)
            lower_bound = math.floor(count / 5) * 5
            bin_key = f"{lower_bound}-{lower_bound + 4}"
            if bin_key in bins:
                bins[bin_key] += 1
            else:
                # Should not happen with current bins, but good for safety
                print(f"Warning: Could not place count {count} into a bin (key={bin_key}).")

    return bins, total_files_checked

def generate_pdf_report(results, total_prompts, files_with_few_prompts, distribution_matrix, total_files_checked, filename="prompt_count_report.pdf"):
    """Generates a PDF report summarizing the prompt counts including a distribution matrix and chart."""
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title = "Executor Log Prompt Count Report"
    story.append(Paragraph(title, styles['h1']))
    story.append(Spacer(1, 12))

    # Report Generation Time
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(f"Report generated on: {now}", styles['Normal']))
    story.append(Spacer(1, 12))

    if not results:
        story.append(Paragraph("No log files were found or processed.", styles['Normal']))
        doc.build(story)
        print(f"\nPDF report generated (no files processed): {filename}")
        return

    # --- Distribution Matrix Table ---
    story.append(Paragraph("Prompt Count Distribution Matrix:", styles['h2']))
    story.append(Spacer(1, 10))

    matrix_data = [['Prompt Count Range', 'Number of Files']]
    # Define order for the matrix rows dynamically
    bin_order = [f"{i}-{i+4}" for i in range(0, 100, 5)] + [">= 100", "Errors"]
    for key in bin_order:
         if key in distribution_matrix: # Check if key exists
              matrix_data.append([key, distribution_matrix.get(key, 0)]) # Use .get for safety

    # Add Total row
    matrix_data.append(['Total Files Checked', total_files_checked])

    # Create and style the table
    table = Table(matrix_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey), # Header row background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), # Header text color
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), # Center align all cells
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # Header font bold
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12), # Header bottom padding
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige), # Data rows background (excluding total)
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey), # Total row background
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), # Total row font bold
        ('GRID', (0, 0), (-1, -1), 1, colors.black) # Grid lines
    ]))
    story.append(table)
    story.append(Spacer(1, 18))
    # --- End Distribution Matrix Table ---

    # --- Distribution Bar Chart ---
    story.append(Paragraph("Prompt Count Distribution Graph:", styles['h2']))
    story.append(Spacer(1, 10))

    # Prepare data for the chart (exclude 'Errors')
    chart_bin_order = [f"{i}-{i+4}" for i in range(0, 100, 5)] + [">= 100"]
    chart_data = [distribution_matrix.get(key, 0) for key in chart_bin_order]
    # Add newline for potentially long labels - ensuring it's done safely
    chart_labels = [str(key).replace("-","-\n") if isinstance(key, str) else str(key) for key in chart_bin_order]

    if any(c > 0 for c in chart_data): # Only draw chart if there's data (excluding errors)
        drawing = Drawing(500, 250) # Increased width slightly for more labels
        bc = VerticalBarChart()
        bc.x = 50
        bc.y = 50
        bc.height = 180 # Adjusted height
        bc.width = 450 # Adjusted width
        bc.data = [chart_data] # Data needs to be list of lists

        bc.strokeColor = colors.black
        bc.valueAxis.valueMin = 0
        # Optional: Set max y-value explicitly, add some padding
        max_val = max(chart_data) if chart_data else 0
        # Ensure max_val calculation doesn't error if chart_data is empty or contains non-numerics (though it shouldn't)
        try:
            numeric_chart_data = [d for d in chart_data if isinstance(d, (int, float))]
            max_val = max(numeric_chart_data) if numeric_chart_data else 0
        except ValueError:
             max_val = 0 # Fallback if max fails

        bc.valueAxis.valueMax = max_val + math.ceil(max_val * 0.1) if max_val > 0 else 10
        # Optional: Set step size for y-axis
        # step = max(1, math.ceil(bc.valueAxis.valueMax / 10))
        # bc.valueAxis.valueStep = step if step > 0 else 1 # Ensure step is positive

        # Apply angle directly to categoryAxis.labels
        bc.categoryAxis.labels.angle = 60 # Angle labels to prevent overlap (Corrected: was boxAngle on categoryAxis)
        bc.categoryAxis.labels.dx = 8      # Adjust horizontal position
        bc.categoryAxis.labels.dy = -10    # Adjust vertical position
        bc.categoryAxis.labels.fontName = 'Helvetica'
        bc.categoryAxis.labels.fontSize = 7 # Smaller font for labels
        bc.categoryAxis.categoryNames = chart_labels

        # Optional: Bar styling
        bc.bars[0].fillColor = colors.lightblue
        bc.barSpacing = 2

        drawing.add(bc)
        story.append(drawing)
    else:
        story.append(Paragraph("No data (excluding errors) to display in the graph.", styles['Normal']))

    story.append(Spacer(1, 18))
    # --- End Distribution Bar Chart ---


    # --- Individual File Counts ---
    story.append(Paragraph("Individual File Counts:", styles['h2']))
    # Only show if there are results to display
    processed_files_exist = any(error is None for _, _, error in results)
    if processed_files_exist or any(error is not None for _, _, error in results):
        for file_path, count, error in results:
            # Ensure file path is relative to the script dir for cleaner output if possible
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                relative_path = os.path.relpath(file_path, script_dir)
            except ValueError: # Handles cases where paths are on different drives (Windows) or if file_path is None/invalid
                relative_path = file_path if file_path else "Unknown Path" # Fallback to absolute path or placeholder

            if error:
                text = f"<b>{relative_path}:</b> Error - {error}"
            else:
                # Display count even if it's 0
                text = f"<b>{relative_path}:</b> {count if count is not None else 'N/A'} prompts found"
            story.append(Paragraph(text, styles['Normal']))
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 12))
    else:
        # This case should ideally be covered by the initial "No log files" check
        story.append(Paragraph("No files processed or all resulted in errors.", styles['Normal']))
        story.append(Spacer(1,12))
    # --- End Individual File Counts ---

    # Total prompt count across successful files
    story.append(Paragraph(f"<b>Total Prompts Found Across All Successfully Processed Files: {total_prompts}</b>", styles['Normal']))
    story.append(Spacer(1, 18))

    # --- Files with fewer than 20 prompts ---
    if files_with_few_prompts:
        story.append(Paragraph("Files with Fewer Than 20 Prompts:", styles['h2']))
        for file_path in files_with_few_prompts:
             # Ensure file path is relative to the script dir for cleaner output if possible
            try:
                script_dir = os.path.dirname(os.path.abspath(__file__))
                relative_path = os.path.relpath(file_path, script_dir)
            except ValueError: # Handles cases where paths are on different drives (Windows) or if file_path is None/invalid
                relative_path = file_path if file_path else "Unknown Path" # Fallback to absolute path or placeholder
            story.append(Paragraph(relative_path, styles['Normal']))
            story.append(Spacer(1, 4))
    elif processed_files_exist: # Only show this message if files were processed
            story.append(Paragraph("No successfully processed files found with fewer than 20 prompts.", styles['Normal']))
    # --- End Files with fewer than 20 prompts ---

    try:
        doc.build(story)
        print(f"\nPDF report generated successfully: {filename}")
    except Exception as e:
        print(f"\nError generating PDF report: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback for debugging PDF errors


def count_prompts_in_logs(prompt_threshold=20):
    """
    Finds logs, counts prompt blocks (text between prompt/response markers),
    categorizes counts, prints results/summary, and generates a PDF report.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__)) # Get the directory the script is in
    task_pattern = os.path.join(script_dir, "task_*/executor_log.txt") # Build full path pattern
    # run_pattern = os.path.join(script_dir, "run_*/executor_log.txt")   # Build full path pattern

    task_logs = glob.glob(task_pattern) # Use the full pattern
    # run_logs = glob.glob(run_pattern)   # Use the full pattern
    log_files = task_logs  # Combine the lists

    # Sort log files for consistent reporting order
    log_files.sort()

    if not log_files:
        # Updated error message to reflect both patterns searched
        print(f"Error: No executor_log.txt files found in {script_dir}/task_*/ or {script_dir}/run_*/ directories.")
        pdf_filename = os.path.join(script_dir, "prompt_count_report.pdf")
        generate_pdf_report([], 0, [], {}, 0, filename=pdf_filename)
        return

    print(f"Found {len(log_files)} log files to check (in task_*/ and run_*/ within {script_dir}).")
    print("-" * 30)
    total_prompts_all_files = 0
    results_data = [] # Store tuples of (file_path, count, error_message)
    files_with_few_prompts = []

    # Regex to find the content between the prompt and response markers
    # Handles 'Model=' or 'model=', captures content non-greedily across multiple lines
    prompt_block_regex = re.compile(
        r"=== LLM Prompt \([Mm]odel=[^)]+\) ===(.*?)=== LLM Response ===",
        re.DOTALL # Make '.' match newline characters
    )

    for log_file in log_files:
        prompt_count = 0
        error_message = None
        processed_successfully = False
        # Get relative path for console output
        try:
            relative_log_file = os.path.relpath(log_file, script_dir)
        except ValueError:
            relative_log_file = log_file

        try:
            # Read the entire file content
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all occurrences of the pattern
            matches = prompt_block_regex.findall(content)
            prompt_count = len(matches) # The count is the number of blocks found

            # Only print count if successful
            print(f"File: {relative_log_file} - Prompt Blocks Found: {prompt_count}") # Changed "Prompts" to "Prompt Blocks" for clarity
            total_prompts_all_files += prompt_count
            processed_successfully = True
        except UnicodeDecodeError as e:
            error_message = f"UnicodeDecodeError: {e}"
            print(f"Error reading {relative_log_file}: {e}. Skipping count for this file.")
        except FileNotFoundError:
            error_message = "File not found."
            print(f"Error: File not found {relative_log_file}. Skipping.")
        except Exception as e:
            error_message = f"Unexpected error: {e}"
            print(f"Unexpected error processing {relative_log_file}: {e}. Skipping this file.")
        finally:
            current_count = prompt_count if processed_successfully else None
            # Store absolute path in results_data for PDF generation
            results_data.append((log_file, current_count, error_message))
            if processed_successfully and current_count is not None and current_count < prompt_threshold:
                # Store absolute path here too
                files_with_few_prompts.append(log_file)

    print("-" * 30)
    print(f"Total prompt blocks found across all successfully processed files: {total_prompts_all_files}") # Changed "prompts" to "prompt blocks"

    # Calculate distribution matrix
    distribution_matrix, total_files_checked = create_distribution_matrix(results_data)

    # Print distribution matrix to console
    print("-" * 30)
    print("Prompt Block Count Distribution Summary:") # Changed "Prompt" to "Prompt Block"
    # Adjust column width if needed due to longer keys like "95-99"
    print(f"{'Range':<10} | {'Files':<5}")
    print("-" * 18)
    # Use the same bin order as the PDF table
    bin_order = [f"{i}-{i+4}" for i in range(0, 100, 5)] + [">= 100", "Errors"]
    # total_files_console = 0 # Not strictly needed as we print total_files_checked
    for key in bin_order:
        if key in distribution_matrix:
            count = distribution_matrix[key]
            print(f"{key:<10} | {count:<5}")
    print("-" * 18)
    # Print the original total_files_checked for consistency with table/data
    print(f"{'Total':<10} | {total_files_checked:<5}")


    # Print files with fewer than the threshold prompts to console
    if files_with_few_prompts:
        print("-" * 30)
        print(f"Files with fewer than {prompt_threshold} prompt blocks:") # Changed "prompts" to "prompt blocks"
        for file_path in files_with_few_prompts:
            try:
                 relative_path = os.path.relpath(file_path, script_dir)
            except ValueError:
                 relative_path = file_path
            print(relative_path)
    else:
         # Check if any files were processed successfully before printing this message
        if any(count is not None and error is None for _, count, error in results_data):
             print(f"\nNo successfully processed files found with fewer than {prompt_threshold} prompt blocks.") # Changed "prompts" to "prompt blocks"


    # Generate the PDF report in the same directory as the script
    pdf_filename = os.path.join(script_dir, "prompt_count_report.pdf")
    # Pass the updated total count name if you change the PDF title/text, but variable name is fine
    generate_pdf_report(
        results_data,
        total_prompts_all_files, # Variable name still reflects the total count
        files_with_few_prompts,
        distribution_matrix,
        total_files_checked,
        filename=pdf_filename
    )


if __name__ == "__main__":
    # Add basic error handling around the main function call
    try:
        count_prompts_in_logs()
    except Exception as e:
        print(f"\nAn unexpected error occurred in the main script execution: {e}")
        import traceback
        traceback.print_exc()
