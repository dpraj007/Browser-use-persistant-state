# path=runs/count_prompts_2.py
import sys
import re
import argparse
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from datetime import datetime
import math

# Regex for prompt blocks: supports Model= or Model:
prompt_block_regex = re.compile(
    r"=== LLM Prompt \([Mm]odel[:=][^)]+\) ===(.*?)=== LLM Response ===",
    re.DOTALL
)

BIN_SIZE = 5
MAX_BIN = 100


def create_distribution_matrix(results):
    """ Calculates the distribution of prompt counts into bins. """
    bins = {f"{i}-{i+BIN_SIZE-1}": 0 for i in range(0, MAX_BIN, BIN_SIZE)}
    bins[f">= {MAX_BIN}"] = 0
    bins["Errors"] = 0
    total = len(results)

    for path, count, error in results:
        if error or count is None:
            bins["Errors"] += 1
        elif count < 0:
            # Handle potentially negative counts if they occur
            print(f"Warning: Negative count {count} found for {path}. Placing in Errors.")
            bins["Errors"] += 1
        elif count >= MAX_BIN:
            bins[f">= {MAX_BIN}"] += 1
        else:
            # Calculate the lower bound of the bin
            lower = (count // BIN_SIZE) * BIN_SIZE
            key = f"{lower}-{lower+BIN_SIZE-1}"
            # Ensure the key exists (it should with the current setup)
            if key in bins:
                bins[key] += 1
            else:
                print(f"Warning: Could not place count {count} into a bin (key={key}). Placing in Errors.")
                bins["Errors"] += 1 # Fallback for unexpected counts
    return bins, total


def generate_pdf_report(results, total_prompts, few_prompts, dist_matrix, total_files, filename):
    """Generates a PDF report summarizing the prompt counts."""
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Planner Log Prompt Count Report", styles['h1']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Report generated on: {datetime.now():%Y-%m-%d %H:%M:%S}", styles['Normal']))
    story.append(Spacer(1, 12))

    if not results:
        story.append(Paragraph("No log files were found or processed.", styles['Normal']))
        doc.build(story)
        print(f"Report saved (no files processed): {filename}")
        return

    # Distribution Matrix Table
    story.append(Paragraph("Prompt Count Distribution Matrix:", styles['h2']))
    matrix_data = [["Range", "Files"]]
    # Define the order for matrix rows consistently
    order = [f"{i}-{i+BIN_SIZE-1}" for i in range(0, MAX_BIN, BIN_SIZE)] + [f">= {MAX_BIN}", "Errors"]
    for key in order:
        # Use .get() for safety in case a key somehow wasn't created
        matrix_data.append([key, dist_matrix.get(key, 0)])
    matrix_data.append(["Total Files Checked", total_files])

    tbl = Table(matrix_data)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),        # Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),   # Header text color
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),              # Center alignment
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),    # Header font bold
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),             # Header bottom padding
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),     # Data rows background (excl. Total & Errors)
        ('BACKGROUND', (0, -2), (-1, -2), colors.lightcoral if "Errors" in order else colors.beige), # Error row background
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),# Total row background
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),  # Total row font bold
        ('GRID', (0, 0), (-1, -1), 1, colors.black),        # Grid lines
    ]))
    story.append(tbl)
    story.append(Spacer(1, 18))

    # Bar Chart
    # Exclude 'Errors' from the chart data if desired, or plot them separately
    chart_values = [dist_matrix.get(k, 0) for k in order if k != "Errors"]
    chart_labels = [k.replace('-', '-\n') for k in order if k != "Errors"]

    # Only create chart if there are non-error values > 0
    if any(v > 0 for v in chart_values):
        story.append(Paragraph("Prompt Count Distribution Chart (Excluding Errors):", styles['h2']))
        drawing = Drawing(500, 250) # Adjusted width for labels
        bc = VerticalBarChart()
        bc.x, bc.y = 50, 50
        bc.height, bc.width = 180, 400 # Adjusted width
        bc.data = [chart_values] # Data must be list of lists
        bc.strokeColor = colors.black

        bc.valueAxis.valueMin = 0
        # Calculate max value safely
        max_val = max(chart_values) if chart_values else 0
        bc.valueAxis.valueMax = max_val + math.ceil(max_val * 0.1) if max_val > 0 else 10 # Add 10% padding or set to 10
        bc.valueAxis.valueStep = max(1, math.ceil(bc.valueAxis.valueMax / 10)) # Aim for ~10 steps

        bc.categoryAxis.labels.boxAnchor = 'ne' # Anchor point for rotation
        bc.categoryAxis.labels.dx = 8           # Horizontal offset
        bc.categoryAxis.labels.dy = -15         # Vertical offset (move up)
        bc.categoryAxis.labels.angle = 45       # Rotation angle
        bc.categoryAxis.labels.fontName = 'Helvetica'
        bc.categoryAxis.labels.fontSize = 8     # Adjust font size if needed
        bc.categoryAxis.categoryNames = chart_labels

        # Optional: Bar styling
        bc.bars[0].fillColor = colors.blue
        bc.barSpacing = 2

        drawing.add(bc)
        story.append(drawing)
        story.append(Spacer(1, 18))
    elif total_files > dist_matrix.get("Errors", 0): # Check if there were files processed without errors
        story.append(Paragraph("No non-error prompt counts to display in the chart.", styles['Normal']))
        story.append(Spacer(1, 18))


    # Individual File Counts
    story.append(Paragraph("Individual File Counts:", styles['h2']))
    # Check if there's anything to report (successful counts or errors)
    if any(count is not None or error is not None for _, count, error in results):
        # Get script's parent directory to attempt making paths relative
        try:
            base_path = Path(__file__).parent
            can_make_relative = True
        except NameError: # Handle if __file__ is not defined (e.g., interactive session)
            base_path = Path.cwd()
            can_make_relative = False # Less reliable to make relative

        for path, count, error in results:
            display_path = path # Default to the full Path object
            if can_make_relative:
                try:
                    # Use Path.relative_to for robust relative path calculation
                    display_path = path.relative_to(base_path)
                except ValueError:
                    # Keep absolute path if it's not relative (e.g., different drive on Windows)
                    display_path = path

            if error:
                text = f"<b>{display_path}:</b> Error - {error}"
            elif count is not None:
                text = f"<b>{display_path}:</b> {count} prompts found"
            else: # Should ideally be caught by 'error', but for safety
                text = f"<b>{display_path}:</b> Unknown status"

            story.append(Paragraph(text, styles['Code'])) # Use 'Code' style for better path visibility
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 12))
    else:
         # This case is less likely if the initial check passes, but for completeness
        story.append(Paragraph("No files were processed or available to report individual counts.", styles['Normal']))
        story.append(Spacer(1, 12))


    story.append(Paragraph(f"<b>Total prompt blocks found across all successfully processed files: {total_prompts}</b>", styles['Normal']))
    story.append(Spacer(1, 18))

    # Files with fewer than threshold prompts
    if few_prompts:
        story.append(Paragraph(f"Files Found with Fewer Than Threshold Prompts:", styles['h2']))
         # Reuse base_path logic from individual counts
        try:
            base_path = Path(__file__).parent
            can_make_relative = True
        except NameError:
            base_path = Path.cwd()
            can_make_relative = False

        for p in few_prompts:
            display_path = p
            if can_make_relative:
                try:
                    display_path = p.relative_to(base_path)
                except ValueError:
                    display_path = p
            story.append(Paragraph(str(display_path), styles['Code'])) # Use 'Code' style
            story.append(Spacer(1, 4))
    elif any(count is not None and error is None for _, count, error in results):
         # Only show this if files were processed successfully
         story.append(Paragraph("No successfully processed files found with fewer than the threshold prompts.", styles['Normal']))

    try:
        doc.build(story)
        print(f"\nReport saved successfully to {filename}")
    except Exception as e:
        print(f"\nError building PDF report: {e}")
        import traceback
        traceback.print_exc() # Provide details on PDF generation errors


def main(threshold, log_name):
    """Finds logs, counts prompts, prints summary, generates PDF."""
    try:
        script_dir = Path(__file__).parent.resolve()
    except NameError:
         # Fallback if __file__ is not defined (e.g., running in an interactive environment)
        script_dir = Path.cwd().resolve()
        print(f"Warning: Could not determine script directory reliably, using current working directory: {script_dir}")

    # Look for directories starting with 'run_' or 'task_' in the script's directory
    dirs_to_check = [d for d in script_dir.iterdir() if d.is_dir() and (d.name.startswith('run_') or d.name.startswith('task_'))]

    if not dirs_to_check:
        print(f"Error: No directories starting with 'run_' or 'task_' found in {script_dir}")
        # Generate an empty report
        pdf_filename = script_dir / f"{log_name.replace('.','_')}_report.pdf"
        generate_pdf_report([], 0, [], {}, 0, str(pdf_filename))
        return

    print(f"Checking for '{log_name}' in {len(dirs_to_check)} subdirectories (run_*/ task_*/)...")
    print("-" * 30)

    results = []
    total_prompts = 0
    files_with_few_prompts = []

    for d in sorted(dirs_to_check): # Sort directories for consistent order
        log_path = d / log_name
        count = None
        error_msg = None
        relative_log_path_str = str(log_path.relative_to(script_dir) if script_dir in log_path.parents else log_path)

        try:
            if not log_path.is_file():
                 raise FileNotFoundError(f"Log file not found at expected location: {log_path}")

            # Read the entire file content with UTF-8 encoding
            content = log_path.read_text(encoding='utf-8')

            # Find all non-overlapping matches of the prompt block regex
            matches = prompt_block_regex.findall(content)
            count = len(matches)
            total_prompts += count # Add to total only if successful
            print(f"{relative_log_path_str}: {count} prompts found")

        except FileNotFoundError:
            # Handle missing log files gracefully without setting error_msg unless we want to report it
            print(f"{relative_log_path_str}: Not found")
            # Decide if "Not Found" should be an error in the report
            error_msg = "Log file not found" # Optionally report as error
        except UnicodeDecodeError as e:
            error_msg = f"UnicodeDecodeError - {e}"
            print(f"Error reading {relative_log_path_str}: {error_msg}")
        except Exception as e:
            # Catch any other unexpected errors during file processing
            error_msg = f"Unexpected error - {e}"
            print(f"Error processing {relative_log_path_str}: {error_msg}")

        # Append result regardless of success or failure
        # Use the full log_path (Path object) for internal tracking/PDF generation
        results.append((log_path, count, error_msg))

        # Check threshold only if processing was successful (count is not None and no error_msg)
        if error_msg is None and count is not None and count < threshold:
            # Store the full path object
            files_with_few_prompts.append(log_path)


    print("-" * 30)
    if not results:
        print("No log files were processed.")
        # Generate empty report again if somehow results is empty despite finding dirs
        pdf_filename = script_dir / f"{log_name.replace('.','_')}_report.pdf"
        generate_pdf_report([], 0, [], {}, 0, str(pdf_filename))
        return

    # Calculate distribution matrix
    dist_matrix, total_files_checked = create_distribution_matrix(results)

    # Print distribution summary to console
    print("Prompt Count Distribution Summary:")
    print(f"{'Range':<12} | {'Files':<5}")
    print("-" * 20)
    # Use the same order as the PDF report for consistency
    bin_order = [f"{i}-{i+BIN_SIZE-1}" for i in range(0, MAX_BIN, BIN_SIZE)] + [f">= {MAX_BIN}", "Errors"]
    for key in bin_order:
        count = dist_matrix.get(key, 0) # Use .get() for safety
        print(f"{key:<12} | {count:<5}")
    print("-" * 20)
    print(f"{'Total Checked':<12} | {total_files_checked:<5}")


    # Print files below threshold to console
    if files_with_few_prompts:
        print("-" * 30)
        print(f"Files with fewer than {threshold} prompts:")
        for file_path in files_with_few_prompts:
             # Display path relative to script_dir if possible
            relative_path_str = str(file_path.relative_to(script_dir) if script_dir in file_path.parents else file_path)
            print(relative_path_str)
    else:
        # Check if any files were processed without error before printing this
        if any(count is not None and error is None for _, count, error in results):
             print(f"\nNo successfully processed files found with fewer than {threshold} prompts.")


    # Generate PDF report
    pdf_filename = script_dir / f"{log_name.replace('.','_')}_report.pdf"
    generate_pdf_report(results, total_prompts, files_with_few_prompts, dist_matrix, total_files_checked, str(pdf_filename))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Count LLM prompts in logs across specified directories and generate a PDF report.")
    parser.add_argument(
        '-t', '--threshold',
        type=int,
        default=20,
        help='Minimum prompt blocks threshold to highlight files below it (default: 20)'
    )
    parser.add_argument(
        '-f', '--log-file',
        type=str,
        default='planner_log.txt',
        help='Log filename to process within each run_*/task_* directory (default: planner_log.txt)'
    )
    args = parser.parse_args()

    try:
        main(args.threshold, args.log_file)
    except Exception as e:
        print(f"\nAn unexpected error occurred during script execution: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1) # Exit with a non-zero status code to indicate failure