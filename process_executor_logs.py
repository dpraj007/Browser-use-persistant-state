import os
import glob
import asyncio
from dotenv import load_dotenv
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import HumanMessage


async def process_log_files():
    # Load environment variables from .env file in parent directory
    if not os.path.exists(".env"):
        # Get the absolute path for a clearer error message
        env_path = os.path.abspath(".env")
        print(f"Error: .env file not found at {env_path}")
        return
    load_dotenv(".env")
    # Retrieve environment variables
    PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
    LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # Validate required environment variables
    if not PROJECT_ID:
        print("Error: GOOGLE_CLOUD_PROJECT not found in .env file.")
        return
    if not LOCATION:
        print("Error: GOOGLE_CLOUD_LOCATION not found in .env file.")
        return
    if not CREDENTIALS_PATH:
        print("Error: GOOGLE_APPLICATION_CREDENTIALS not found in .env file.")
        return
    if not os.path.isfile(CREDENTIALS_PATH):
        print(f"Error: Service account key file at {CREDENTIALS_PATH} does not exist.")
        return

    # Set GOOGLE_APPLICATION_CREDENTIALS environment variable
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_PATH

    # Initialize ChatVertexAI model
    try:
        model = ChatVertexAI(
            model_name="gemini-2.5-flash-preview-04-17",
            project=PROJECT_ID,
            location=LOCATION,
            temperature=0.5,
            max_retries=6,
        )
    except Exception as e:
        print(f"Error initializing ChatVertexAI: {e}")
        return

    # Find all executor_log.txt files
    log_files = glob.glob("runs/task_*/executor_log.txt")
    if not log_files:
        print("Error: No executor_log.txt files found in runs/task_*/")
        return

    print(f"Found {len(log_files)} log files to process.")

    for log_file in log_files:
        print(f"Processing file: {log_file}")
        task_folder = os.path.dirname(log_file)

        # Read the log file with UTF-8 encoding
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError as e:
            print(f"Error reading {log_file}: {e}. Skipping this file.")
            continue
        except Exception as e:
            print(f"Unexpected error reading {log_file}: {e}. Skipping this file.")
            continue

        # Find all prompt sections
        sections = []
        for i in range(len(lines)):
            # Corrected condition: Check if the line starts with the generic prompt header
            if lines[i].strip().startswith("=== LLM Prompt (model="):
                start = i + 1
                # Find the end of the prompt section (next line starting with '===')
                for j in range(start, len(lines)):
                    if lines[j].strip().startswith("==="):
                        end = j
                        break
                else: # If no line starting with '===' is found until the end
                    end = len(lines)
                sections.append((start, end))

        print(f"Found {len(sections)} prompt sections in {log_file}")


        # Process each prompt section
        offset = 0 # Keep track of line number changes due to insertions
        for start, end in sections:
            actual_start = start + offset
            actual_end = end + offset
            # Ensure indices are within bounds after potential insertions
            if actual_start >= len(lines) or actual_end > len(lines):
                print(f"Warning: Section indices [{start},{end}] seem out of bounds after processing. Skipping.")
                continue

            prompt_lines = lines[actual_start:actual_end]
            prompt = "".join(prompt_lines).strip()

            # Check if prompt is empty or whitespace, skip if it is
            if not prompt:
                print(f"Warning: Found empty prompt section at original lines [{start},{end}] in {log_file}. Skipping.")
                continue

            # Use ChatVertexAI to generate response
            try:
                # Ensure the model used here is appropriate for the prompts
                # (Consider if you need different models based on original prompt's model)
                response = await model.ainvoke([HumanMessage(content=prompt)])
                llm_response = response.content
            except Exception as e:
                print(f"Error generating response for prompt in {log_file} (original lines [{start},{end}]): {e}. Skipping this prompt.")
                continue

            # Prepare response lines
            response_header = "=== LLM Response ==="
            response_content_lines = llm_response.split("\n")
            # Add newline character back to each line for writelines
            response_lines = [response_header + "\n"] + [line + "\n" for line in response_content_lines] + ["\n"] # Add extra newline for spacing

            # Insert response into the log file lines list
            insert_pos = actual_end
            lines[insert_pos:insert_pos] = response_lines
            inserted = len(response_lines)
            offset += inserted

        # Save the modified log file
        processed_folder = os.path.join(task_folder, "processed")
        os.makedirs(processed_folder, exist_ok=True)
        processed_file = os.path.join(processed_folder, "executor_log_with_response.txt")
        try:
            with open(processed_file, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print(f"Saved processed file: {processed_file}")
        except Exception as e:
            print(f"Error writing to {processed_file}: {e}. Skipping save for this file.")
            continue


if __name__ == "__main__":
    asyncio.run(process_log_files())