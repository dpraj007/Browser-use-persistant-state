import os
import glob
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from datetime import datetime
import math # For calculating bins

def create_distribution_matrix(results):
    """ Calculates the distribution of prompt counts into bins. """
    bins = {
        "< 20": 0, "20-29": 0, "30-39": 0, "40-49": 0,
        "50-59": 0, "60-69": 0, "70-79": 0, "80-89": 0,
        "90-99": 0, ">= 100": 0, "Errors": 0
    }
    total_files_checked = len(results)

    for _, count, error in results:
        if error:
            bins["Errors"] += 1
            continue
        # count will be None if there was an error, handled above
        if count < 20:
            bins["< 20"] += 1
        elif count >= 100:
            bins[">= 100"] += 1
        else:
            # Calculate the lower bound of the bin (e.g., 30 for counts 30-39)
            lower_bound = math.floor(count / 10) * 10
            bin_key = f"{lower_bound}-{lower_bound + 9}"
            if bin_key in bins:
                bins[bin_key] += 1
            else:
                # Should not happen with current bins, but good for safety
                print(f"Warning: Could not place count {count} into a bin.")

    return bins, total_files_checked

def generate_pdf_report(results, total_prompts, files_with_few_prompts, distribution_matrix, total_files_checked, filename="prompt_count_report.pdf"):
    """Generates a PDF report summarizing the prompt counts including a distribution matrix."""
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

    # --- Distribution Matrix ---
    story.append(Paragraph("Prompt Count Distribution Matrix:", styles['h2']))
    story.append(Spacer(1, 10))

    matrix_data = [['Prompt Count Range', 'Number of Files']]
    # Define order for the matrix rows
    bin_order = ["< 20", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80-89", "90-99", ">= 100", "Errors"]
    for key in bin_order:
         if key in distribution_matrix: # Check if key exists (it should)
              matrix_data.append([key, distribution_matrix[key]])

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
    # --- End Distribution Matrix ---


    # --- Individual File Counts ---
    story.append(Paragraph("Individual File Counts:", styles['h2']))
    # Only show if there are results to display
    processed_files_exist = any(error is None for _, _, error in results)
    if processed_files_exist or any(error is not None for _, _, error in results):
        for file_path, count, error in results:
            if error:
                text = f"<b>{file_path}:</b> Error - {error}"
            else:
                # Display count even if it's 0
                text = f"<b>{file_path}:</b> {count if count is not None else 'N/A'} prompts found"
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
            story.append(Paragraph(file_path, styles['Normal']))
            story.append(Spacer(1, 4))
    elif processed_files_exist: # Only show this message if files were processed
            story.append(Paragraph("No successfully processed files found with fewer than 20 prompts.", styles['Normal']))
    # --- End Files with fewer than 20 prompts ---

    try:
        doc.build(story)
        print(f"\nPDF report generated successfully: {filename}")
    except Exception as e:
        print(f"\nError generating PDF report: {e}")


def count_prompts_in_logs(prompt_threshold=20):
    """
    Finds logs, counts prompts, categorizes counts, prints results/summary,
    and generates a PDF report with a distribution matrix.
    """
    log_files = glob.glob("task_*/executor_log.txt")

    if not log_files:
        print("Error: No executor_log.txt files found in task_*/ directories.")
        # Generate an empty report if requested? Or just exit? Let's exit for now.
        # generate_pdf_report([], 0, [], {}, 0)
        return

    print(f"Found {len(log_files)} log files to check.")
    print("-" * 30)

    total_prompts_all_files = 0
    results_data = [] # Store tuples of (file_path, count, error_message)
    files_with_few_prompts = []

    for log_file in log_files:
        prompt_count = 0
        error_message = None
        processed_successfully = False
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith("=== LLM Prompt (Model:"):
                        prompt_count += 1
            # Only print count if successful
            print(f"File: {log_file} - Prompts Found: {prompt_count}")
            total_prompts_all_files += prompt_count
            processed_successfully = True
        except UnicodeDecodeError as e:
            error_message = f"UnicodeDecodeError: {e}"
            print(f"Error reading {log_file}: {e}. Skipping count for this file.")
        except FileNotFoundError:
            error_message = "File not found."
            print(f"Error: File not found {log_file}. Skipping.")
        except Exception as e:
            error_message = f"Unexpected error: {e}"
            print(f"Unexpected error processing {log_file}: {e}. Skipping this file.")
        finally:
            current_count = prompt_count if processed_successfully else None
            results_data.append((log_file, current_count, error_message))
            if processed_successfully and current_count < prompt_threshold:
                files_with_few_prompts.append(log_file)

    print("-" * 30)
    print(f"Total prompts found across all successfully processed files: {total_prompts_all_files}")

    # Calculate distribution matrix
    distribution_matrix, total_files_checked = create_distribution_matrix(results_data)

    # Print distribution matrix to console
    print("-" * 30)
    print("Prompt Count Distribution Summary:")
    print(f"{'Range':<10} | {'Files':<5}")
    print("-" * 18)
    bin_order = ["< 20", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80-89", "90-99", ">= 100", "Errors"]
    for key in bin_order:
        if key in distribution_matrix:
            print(f"{key:<10} | {distribution_matrix[key]:<5}")
    print("-" * 18)
    print(f"{'Total':<10} | {total_files_checked:<5}")


    # Print files with fewer than the threshold prompts to console
    if files_with_few_prompts:
        print("-" * 30)
        print(f"Files with fewer than {prompt_threshold} prompts:")
        for file_path in files_with_few_prompts:
            print(file_path)
    else:
         # Check if any files were processed successfully before printing this message
        if any(count is not None and error is None for _, count, error in results_data):
             print(f"\nNo successfully processed files found with fewer than {prompt_threshold} prompts.")


    # Generate the PDF report
    generate_pdf_report(
        results_data,
        total_prompts_all_files,
        files_with_few_prompts,
        distribution_matrix,
        total_files_checked
    )


if __name__ == "__main__":
    count_prompts_in_logs()