#!/usr/bin/env python
# gcp_manual_login_planner.py
# ---------------------------------------------------------------
#  ▸ execution  LLM : gpt‑4.1‑mini      (fast / cheap)
#  ▸ planning   LLM : gpt‑4o            (bigger / better reasoning)
# ---------------------------------------------------------------

import os, sys, asyncio, json, logging
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from browser_use import Agent
from mss import mss
from PIL import Image

# -----------------------------------------------------------------
# 1.  ENV & directories
# -----------------------------------------------------------------
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

BASE_DIR = "runs"
os.makedirs(BASE_DIR, exist_ok=True)

# Enable LangChain debug logging (local only)
os.environ["LANGCHAIN_DEBUG"] = "1"

# -----------------------------------------------------------------
# 2.  Helper to serialize AgentHistoryList
# -----------------------------------------------------------------
def serialize_history(history):
    """Convert AgentHistoryList to a serializable dictionary."""
    try:
        serializable_history = []
        for item in history:
            if hasattr(item, '__dict__'):
                serializable_history.append(item.__dict__)
            elif isinstance(item, (dict, list, str, int, float, bool, type(None))):
                serializable_history.append(item)
            else:
                serializable_history.append(str(item))
        return serializable_history
    except Exception as e:
        return {"error": f"Failed to serialize history: {str(e)}"}

# -----------------------------------------------------------------
# 3.  Custom Callback Handler for LLM Prompts and Responses
# -----------------------------------------------------------------



class LLMLogCallback(BaseCallbackHandler):
    def __init__(self, log_file, global_log_file, agent_id):
        self.log_file = log_file
        self.global_log_file = global_log_file
        self.agent_id = agent_id
        self.current_interaction_start = None
        
        # Create an images directory next to the log file
        self.images_dir = os.path.join(os.path.dirname(log_file), "images")
        os.makedirs(self.images_dir, exist_ok=True)

    def _save_image_and_get_reference(self, image_data, prefix="img"):
        """Save base64 image data to file and return reference path"""
        try:
            if isinstance(image_data, str) and image_data.startswith(("data:image", "iVBOR")):
                # Generate unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"{prefix}_{timestamp}.png"
                filepath = os.path.join(self.images_dir, filename)
                
                # Extract and save image data
                if image_data.startswith("data:image"):
                    import base64
                    image_data = image_data.split(",")[1]
                
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(image_data))
                
                # Return relative path from log file
                return f"[Image: ./images/{filename}]"
            return image_data
        except Exception as e:
            return f"[Error saving image: {str(e)}]"

    def _format_content(self, content):
        """Helper method to format response content"""
        if not content:
            return "Empty content\n"
        
        try:
            # Try parsing as JSON first
            json_response = json.loads(content)
            
            # Handle images in JSON
            if isinstance(json_response, dict):
                for key, value in json_response.items():
                    if isinstance(value, str) and value.startswith(("data:image", "iVBOR")):
                        json_response[key] = self._save_image_and_get_reference(value, f"json_{key}")
            
            return json.dumps(json_response, indent=4, ensure_ascii=False) + "\n"
        
        except json.JSONDecodeError:
            # If not JSON, check if it's a base64 image
            if content.startswith(("data:image", "iVBOR")):
                return self._save_image_and_get_reference(content) + "\n"
            return f"{content}\n"

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.current_interaction_start = datetime.now()
        model_name = serialized.get("kwargs", {}).get("model_name", "unknown")
        timestamp = self.current_interaction_start.strftime("%Y-%m-%d %H:%M:%S")
        
        # Process prompts to handle any images
        processed_prompts = []
        for prompt in prompts:
            if isinstance(prompt, str):
                if prompt.startswith(("data:image", "iVBOR")):
                    processed_prompts.append(self._save_image_and_get_reference(prompt, "prompt"))
                else:
                    processed_prompts.append(prompt)
            else:
                processed_prompts.append(str(prompt))
        
        log_entry = f"\n=== LLM Prompt (Model: {model_name}) at {timestamp} ===\n"
        for prompt in processed_prompts:
            log_entry += f"{prompt}\n"
        
        # Write to both files
        for file_path in [self.log_file, self.global_log_file]:
            try:
                with open(file_path, "a", encoding="utf-8") as f:
                    if file_path == self.global_log_file:
                        f.write(f"\n=== {self.agent_id} - {log_entry}")
                    else:
                        f.write(log_entry)
                    f.flush()
            except Exception as e:
                print(f"Error writing to {file_path}: {e}")


    def on_llm_end(self, response, **kwargs):
        # --- Debug Start ---
        print(f"\n--- DEBUG ({self.agent_id}): Entering on_llm_end ---")
        print(f"--- DEBUG ({self.agent_id}): Response type: {type(response)}")
        print(f"--- DEBUG ({self.agent_id}): Response object: {response}")
        # --- Debug End ---

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        duration = ""
        if self.current_interaction_start:
            duration = f" (Duration: {(datetime.now() - self.current_interaction_start).total_seconds():.2f}s)"

        log_entry = f"\n=== LLM Response at {timestamp}{duration} ===\n"

        # Process response content
        try:
            content_found = False # Flag to track if we found content
            if hasattr(response, 'generations'):
                # --- Debug Start ---
                print(f"--- DEBUG ({self.agent_id}): Found 'generations' attribute.")
                # --- Debug End ---
                if response.generations:
                    for gen_list in response.generations:
                        for gen in gen_list:
                            if hasattr(gen, 'message') and hasattr(gen.message, 'content'):
                                content = gen.message.content
                                # --- Debug Start ---
                                print(f"--- DEBUG ({self.agent_id}): Extracted content from gen.message.content (Length: {len(content)})")
                                # --- Debug End ---
                                log_entry += self._format_content(content)
                                content_found = True
                            else:
                                # --- Debug Start ---
                                print(f"--- DEBUG ({self.agent_id}): Generation object lacks 'message' or 'content'. Gen: {gen}")
                                # --- Debug End ---
                                log_entry += "No message content available in generation\n"
                else:
                     # --- Debug Start ---
                    print(f"--- DEBUG ({self.agent_id}): 'generations' attribute is empty.")
                    # --- Debug End ---
                    log_entry += "Empty generations list in response\n"

            elif hasattr(response, 'content'):
                # --- Debug Start ---
                print(f"--- DEBUG ({self.agent_id}): Found 'content' attribute.")
                # --- Debug End ---
                content = response.content
                # --- Debug Start ---
                print(f"--- DEBUG ({self.agent_id}): Extracted content from response.content (Length: {len(content) if content else 0})")
                # --- Debug End ---
                log_entry += self._format_content(content)
                content_found = True

            else:
                # --- Debug Start ---
                print(f"--- DEBUG ({self.agent_id}): Did not find 'generations' or 'content' attributes.")
                # --- Debug End ---
                # This case should already be handled by the check below,
                # but we add the print for clarity.
                pass # Let the final check handle adding "NO RESPONSE RECEIVED"

            # Final check if no content was processed
            if not content_found:
                 # --- Debug Start ---
                print(f"--- DEBUG ({self.agent_id}): No content processed, logging 'NO RESPONSE RECEIVED'.")
                # --- Debug End ---
                log_entry += "NO RESPONSE RECEIVED\n"

        except Exception as e:
            # --- Debug Start ---
            print(f"--- DEBUG ({self.agent_id}): Exception during response processing: {e}")
            # --- Debug End ---
            log_entry += f"Error processing response: {str(e)}\n"

        # --- Debug Start ---
        print(f"--- DEBUG ({self.agent_id}): Final log entry content (before writing):\n{log_entry}")
        # --- Debug End ---

        # Write to both files
        for file_path in [self.log_file, self.global_log_file]:
            try:
                with open(file_path, "a", encoding="utf-8") as f:
                    prefix = f"=== {self.agent_id} - " if file_path == self.global_log_file else ""
                    # --- Debug Start ---
                    print(f"--- DEBUG ({self.agent_id}): Attempting to write to {file_path}")
                    # --- Debug End ---
                    f.write(prefix + log_entry.replace("\n=== ", "\n")) # Avoid double prefix if log_entry starts with ===
                    f.flush()
                    # --- Debug Start ---
                    print(f"--- DEBUG ({self.agent_id}): Successfully wrote to {file_path}")
                    # --- Debug End ---
            except Exception as e:
                print(f"Error writing to {file_path}: {e}")
                 # --- Debug Start ---
                print(f"--- DEBUG ({self.agent_id}): FAILED writing to {file_path}: {e}")
                # --- Debug End ---

        # --- Debug Start ---
        print(f"--- DEBUG ({self.agent_id}): Exiting on_llm_end ---\n")

    def on_llm_error(self, error, **kwargs):
        # --- Debug Start ---
        print(f"\n--- DEBUG ({self.agent_id}): Entering on_llm_error ---")
        print(f"--- DEBUG ({self.agent_id}): Error: {error}")
        # --- Debug End ---
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"\n=== LLM Error at {timestamp} ===\n{str(error)}\n\n"

        # Write to both files
        for file_path in [self.log_file, self.global_log_file]:
            try:
                with open(file_path, "a", encoding="utf-8") as f:
                    prefix = f"=== {self.agent_id} - " if file_path == self.global_log_file else ""
                     # --- Debug Start ---
                    print(f"--- DEBUG ({self.agent_id}): Attempting to write ERROR to {file_path}")
                    # --- Debug End ---
                    f.write(prefix + log_entry.replace("\n=== ", "\n"))
                    f.flush()
                    # --- Debug Start ---
                    print(f"--- DEBUG ({self.agent_id}): Successfully wrote ERROR to {file_path}")
                    # --- Debug End ---
            except Exception as e:
                print(f"Error writing LLM Error to {file_path}: {e}")
                # --- Debug Start ---
                print(f"--- DEBUG ({self.agent_id}): FAILED writing ERROR to {file_path}: {e}")
                # --- Debug End ---

        # --- Debug Start ---
        print(f"--- DEBUG ({self.agent_id}): Exiting on_llm_error ---\n")

    def _format_content(self, content):
        """Helper method to format response content"""
        if not content:
            # --- Debug Start ---
            print(f"--- DEBUG ({self.agent_id}): Formatting empty content.")
            # --- Debug End ---
            return "Empty content\n"

        try:
            # --- Debug Start ---
            print(f"--- DEBUG ({self.agent_id}): Attempting to format as JSON.")
            # --- Debug End ---
            json_response = json.loads(content)
            # Handle images in JSON
            if isinstance(json_response, dict):
                for key, value in json_response.items():
                    if isinstance(value, str) and value.startswith(("data:image", "iVBOR")):
                         # --- Debug Start ---
                        print(f"--- DEBUG ({self.agent_id}): Found image in JSON key '{key}'. Saving.")
                        # --- Debug End ---
                        json_response[key] = self._save_image_and_get_reference(value, f"json_{key}")
            # --- Debug Start ---
            print(f"--- DEBUG ({self.agent_id}): Formatted as JSON successfully.")
            # --- Debug End ---
            return json.dumps(json_response, indent=4, ensure_ascii=False) + "\n"

        except json.JSONDecodeError:
             # --- Debug Start ---
            print(f"--- DEBUG ({self.agent_id}): Failed to parse as JSON. Checking for image.")
            # --- Debug End ---
            # If not JSON, check if it's a base64 image
            if isinstance(content, str) and content.startswith(("data:image", "iVBOR")):
                 # --- Debug Start ---
                print(f"--- DEBUG ({self.agent_id}): Found standalone image. Saving.")
                # --- Debug End ---
                return self._save_image_and_get_reference(content) + "\n"
            # --- Debug Start ---
            print(f"--- DEBUG ({self.agent_id}): Formatting as plain text.")
            # --- Debug End ---
            return f"{content}\n"
        except Exception as e:
             # --- Debug Start ---
            print(f"--- DEBUG ({self.agent_id}): Exception during _format_content: {e}")
            # --- Debug End ---
            return f"[Error formatting content: {str(e)}]\n"

# -----------------------------------------------------------------
# 4.  Screenshot helper
# -----------------------------------------------------------------
class ScreenshotHandler(logging.Handler):
    def __init__(self, log_file, screenshot_dir):
        super().__init__()
        self.log_file = log_file
        self.screenshot_dir = screenshot_dir
        self.step = 1
        self.last_goal = ""
        self.debug_file = os.path.join(self.screenshot_dir, "debug_log.txt")

    async def _capture(self, filename):
        await asyncio.sleep(3)  # wait for page paint
        try:
            with mss() as sct:
                monitor = {"top": 100, "left": 100, "width": 1200, "height": 800}
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
                img.save(filename, "PNG")
        except Exception as e:
            print(f"Error capturing screenshot: {e}")

    def emit(self, record):
        msg = record.getMessage()
        with open(self.debug_file, "a", encoding="utf-8") as f:
            f.write(f"DEBUG: Checking message: '{msg}'\n")

        triggers = [
            "Action 1/1:",
            "Next goal:",
            "Searched for",
            "Navigating to",
            "Entering",
            "Clicking",
            "User logged in",
            "Clicked",
        ]
        if any(t in msg for t in triggers):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file = f"{self.screenshot_dir}/step_{self.step}_{ts}.png"
            asyncio.create_task(self._capture(file))

            entry = {
                "step": self.step,
                "action": msg if any(t in msg for t in ["Action", "Navigating", "Entering",
                                                       "Clicking", "Searched for", "User logged in",
                                                       "Clicked"]) else "",
                "next_goal": msg if "Next goal" in msg else self.last_goal,
                "screenshot": file,
            }
            with open(self.log_file, "a", encoding="utf-8") as f:
                json.dump(entry, f)
                f.write("\n")

            if "Next goal:" in msg:
                self.last_goal = msg
            print(f"Step {self.step}: Saved {file}")
            self.step += 1

# -----------------------------------------------------------------
# 5.  Main coroutine
# -----------------------------------------------------------------
import os, sys, asyncio, json, logging
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from browser_use import Agent
from mss import mss
from PIL import Image
# Add this import (assuming process_log_images.py is in the same directory or python path)
from process_log_images import process_log_images

# ... (rest of the file including ENV setup, helpers, LLMLogCallback, ScreenshotHandler) ...


# -----------------------------------------------------------------
# 5.  Main coroutine
# -----------------------------------------------------------------
async def main():
    # --- Initial Setup ---
    # Create unique run folder for the entire session
    run_ts_session = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_run_dir = os.path.join(BASE_DIR, f"session_run_{run_ts_session}")
    os.makedirs(session_run_dir, exist_ok=True)

    # Create global LLM log file for the whole session
    global_llm_log_file = os.path.join(session_run_dir, "all_llm_calls.log")

    # Set up general session run logger
    run_logger = logging.getLogger("session_run")
    run_logger.setLevel(logging.INFO)
    run_file_handler = logging.FileHandler(os.path.join(session_run_dir, "session_log.txt"), encoding="utf-8")
    run_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    run_logger.addHandler(run_file_handler)
    # Add console handler for immediate feedback
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    run_logger.addHandler(console_handler)

    run_logger.info(f"Session started. Logs and artifacts in: {session_run_dir}")
    run_logger.info(f"Global LLM log: {global_llm_log_file}")

    # Initialize shared browser variables
    shared_browser = None
    shared_browser_ctx = None
    first_agent_run_dir = None # To store the directory of the first agent run

    # --- 5-A: First agent: open GCP sign-in page ---
    try:
        run_logger.info("--- Starting Initial Agent: Navigate to GCP Sign-in ---")

        # Create run directory for the first agent
        first_agent_run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        first_agent_run_dir = os.path.join(session_run_dir, f"initial_agent_{first_agent_run_ts}")
        os.makedirs(first_agent_run_dir, exist_ok=True)
        run_logger.info(f"Initial agent run directory: {first_agent_run_dir}")

        # Set up log files for this specific agent run
        planner_log_file = os.path.join(first_agent_run_dir, "planner_log.txt")
        executor_log_file = os.path.join(first_agent_run_dir, "executor_log.txt")

        # Set up LLM callbacks for the initial agent
        initial_agent_id = "initial_agent"
        planner_callback = LLMLogCallback(planner_log_file, global_llm_log_file, initial_agent_id)
        executor_callback = LLMLogCallback(executor_log_file, global_llm_log_file, initial_agent_id)

        # Initialize LLMs for the initial agent
        exec_llm = ChatOpenAI(model="gpt-4.1", temperature=0.5, callbacks=[executor_callback])
        plan_llm = ChatOpenAI(model="o4-mini", temperature=1.0, callbacks=[planner_callback])

        # Create the first agent
        first_agent = Agent(
            task="Navigate to Google Cloud Platform and go to sign in",
            llm=exec_llm,
            planner_llm=plan_llm,
            planner_interval=1,
            use_vision_for_planner=False,
            close_browser_on_run=False,
            enable_memory=False, # Keep memory off for this simple setup
        )

        # Set up screenshot handler for this run
        screenshot_dir = os.path.join(first_agent_run_dir, "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        log_json = os.path.join(first_agent_run_dir, "log.json")
        handler = ScreenshotHandler(log_json, screenshot_dir)
        handler.setLevel(logging.INFO)
        logger_names_to_attach = ["", "browser_use", "agent", "controller"] # Root logger + relevant library loggers
        for name in logger_names_to_attach:
            logging.getLogger(name).addHandler(handler)

        # Run the initial agent
        run_logger.info("Running initial agent...")
        history = await first_agent.run()
        run_logger.info("Initial agent finished.")

        # Log executor actions from history
        run_logger.info(f"Logging initial agent executor actions to: {executor_log_file}")
        with open(executor_log_file, "a", encoding="utf-8") as f:
            f.write("\n=== Executor Actions from History (Initial Run) ===\n")
            serialized_history = serialize_history(history)
            for i, entry in enumerate(serialized_history):
                f.write(f"\nStep {i+1}:\n")
                if isinstance(entry, dict):
                    # Attempt to pretty-print action/llm_output if they are dicts/lists
                    action_str = json.dumps(entry.get('action'), indent=2, ensure_ascii=False) if isinstance(entry.get('action'), (dict, list)) else entry.get('action')
                    llm_output_str = json.dumps(entry.get('llm_output'), indent=2, ensure_ascii=False) if isinstance(entry.get('llm_output'), (dict, list)) else entry.get('llm_output')
                    if action_str: f.write(f"  Action: {action_str}\n")
                    if llm_output_str: f.write(f"  LLM Output: {llm_output_str}\n")
                    # Log other keys
                    for key, value in entry.items():
                        if key not in ['action', 'llm_output']:
                            f.write(f"  {key}: {value}\n")
                else:
                    f.write(f"  {entry}\n")
            f.write("\n")

        # Serialize and log agent history
        run_result_path = os.path.join(first_agent_run_dir, "run_result.json")
        run_logger.info(f"Saving initial agent run result to: {run_result_path}")
        with open(run_result_path, "w", encoding="utf-8") as f:
            json.dump(serialized_history, f, indent=2)

        # Log browser state
        current_url = "unknown"
        try:
            context = first_agent.browser_context
            pages = await context.pages()
            if pages:
                page = pages[0]
                current_url = await page.evaluate("() => window.location.href")
            else: # Should ideally not happen if agent ran, but handle defensively
                run_logger.warning("No pages found in browser context after initial agent run.")
                page = await context.new_page()
                await page.goto("about:blank")
                current_url = "about:blank"
            run_logger.info(f"Browser State After Initial Run: URL = {current_url}")
        except Exception as e:
            run_logger.error(f"Error getting browser state after initial run: {str(e)}")

        # Optional: Force executor LLM call for verification (already in your code)
        try:
            run_logger.info("Performing forced executor LLM call for verification...")
            prompt = f"""
            Current URL: {current_url}
            Task: Verify that the Google Cloud Platform sign-in page is loaded and identify the next action.
            Instructions: Confirm if the sign-in interface is present. If so, suggest the next action (like 'Manual login required'). Return JSON:
            {{
                "current_state": {{"evaluation": "Description of page state"}},
                "next_action": "Suggested action"
            }}
            """
            response = await exec_llm.ainvoke([HumanMessage(content=prompt)])
            # Logging this call is handled by the executor_callback already.
            run_logger.info("Forced LLM call completed.")
            if hasattr(response, 'content'):
                 run_logger.debug(f"Forced LLM response content: {response.content}")
            else:
                 run_logger.warning("Forced LLM call did not return 'content'.")

        except Exception as e:
            run_logger.error(f"Error during forced executor LLM call: {str(e)}")

        # --- Post-process the executor log for the initial task ---
        run_logger.info("--- Post-processing executor log for initial task ---")
        try:
            process_log_images(executor_log_file)
            run_logger.info(f"--- Finished post-processing: {executor_log_file} ---")
        except Exception as e:
            run_logger.error(f"--- Error during post-processing {executor_log_file}: {e} ---")
        # --- End of Post-processing Step ---


        # Prepare for manual login and command loop
        print("\nLog in manually in the browser window, then press Enter here to continue…")
        input()
        run_logger.info("User indicated manual login complete.")

        # Keep browser and context open
        shared_browser = first_agent.browser
        shared_browser_ctx = first_agent.browser_context

        # Clean up initial agent resources BUT keep browser/context
        del first_agent
        for name in logger_names_to_attach:
            try:
                logging.getLogger(name).removeHandler(handler)
            except ValueError:
                pass # Handler might already be removed

    except Exception as e:
        run_logger.exception(f"An error occurred during the initial agent setup or run: {e}")
        # Attempt cleanup even on error
        if 'handler' in locals():
             for name in logger_names_to_attach:
                try:
                    logging.getLogger(name).removeHandler(handler)
                except ValueError: pass
        if 'first_agent' in locals() and hasattr(first_agent, 'browser_context') and first_agent.browser_context:
            await first_agent.browser_context.close()
        if 'first_agent' in locals() and hasattr(first_agent, 'browser') and first_agent.browser:
            await first_agent.browser.close()
        run_logger.info("Exiting due to error in initial phase.")
        return # Exit main if initial setup fails

    # --- 5-B: Command loop ---
    if shared_browser and shared_browser_ctx:
        run_logger.info("--- Starting Command Loop ---")
        try:
            while True:
                act = input("\nEnter the next GCP task/action (or type 'exit' to quit): ").strip()
                if act.lower() == "exit":
                    run_logger.info("Exit command received. Shutting down.")
                    break
                if not act:
                    print("Please enter a task or 'exit'.")
                    continue

                task_run_logger = None
                task_file_handler = None
                task_handler = None # Screenshot handler for the task
                task_agent = None

                try:
                    # Create task-specific run folder inside the session directory
                    run_ts_task = datetime.now().strftime("%Y%m%d_%H%M%S")
                    # Ensure task name is filesystem-friendly
                    safe_act_name = "".join(c if c.isalnum() or c in ('_','-') else '_' for c in act)
                    task_run_dir = os.path.join(session_run_dir, f"task_{safe_act_name}_{run_ts_task}")
                    os.makedirs(task_run_dir, exist_ok=True)
                    run_logger.info(f"Starting task: '{act}'. Task directory: {task_run_dir}")

                    # Set up task-specific log files
                    task_planner_log = os.path.join(task_run_dir, "planner_log.txt")
                    task_executor_log = os.path.join(task_run_dir, "executor_log.txt")
                    task_run_log_path = os.path.join(task_run_dir, "task_run_log.txt")

                    # Set up task-specific logger
                    task_logger_name = f"task_run_{safe_act_name}_{run_ts_task}" # Unique name
                    task_run_logger = logging.getLogger(task_logger_name)
                    task_run_logger.setLevel(logging.INFO)
                    # Prevent propagating to root logger to avoid duplicate console messages
                    task_run_logger.propagate = False
                    # Add file handler for this task's run log
                    task_file_handler = logging.FileHandler(task_run_log_path, encoding="utf-8")
                    task_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
                    task_run_logger.addHandler(task_file_handler)
                    # Optionally add a console handler *if* you want task-specific logs also on console
                    # task_console_handler = logging.StreamHandler()
                    # task_console_handler.setFormatter(logging.Formatter("TASK LOG: %(message)s"))
                    # task_run_logger.addHandler(task_console_handler)

                    # Set up LLM callbacks for the task agent
                    task_agent_id = f"task_{safe_act_name}_{run_ts_task}"
                    task_planner_callback = LLMLogCallback(task_planner_log, global_llm_log_file, task_agent_id)
                    task_executor_callback = LLMLogCallback(task_executor_log, global_llm_log_file, task_agent_id)

                    # Create new LLM instances for the task agent
                    exec_llm_task = ChatOpenAI(model="gpt-4.1", temperature=0.5, callbacks=[task_executor_callback])
                    plan_llm_task = ChatOpenAI(model="o4-mini", temperature=1.0, callbacks=[task_planner_callback])

                    # Create the task agent, reusing the browser/context
                    task_agent = Agent(
                        task=act,
                        llm=exec_llm_task,
                        planner_llm=plan_llm_task,
                        planner_interval=1,
                        browser=shared_browser,          # Reuse browser
                        browser_context=shared_browser_ctx, # Reuse context
                        close_browser_on_run=False,    # Important: Don't close shared browser
                        enable_memory=False,           # Keep memory off
                    )

                    # Set up screenshot handler for this task
                    task_screenshot_dir = os.path.join(task_run_dir, "screenshots")
                    os.makedirs(task_screenshot_dir, exist_ok=True)
                    task_log_json = os.path.join(task_run_dir, "log.json")
                    task_handler = ScreenshotHandler(task_log_json, task_screenshot_dir)
                    task_handler.setLevel(logging.INFO)
                    for name in logger_names_to_attach:
                        logging.getLogger(name).addHandler(task_handler)

                    # Log task start and run the agent
                    task_run_logger.info(f"Task Started: {act}")
                    run_logger.info(f"Running agent for task: '{act}'...")
                    history = await task_agent.run()
                    run_logger.info(f"Agent finished task: '{act}'.")

                    # Log executor actions from task history
                    task_run_logger.info(f"Logging task executor actions to: {task_executor_log}")
                    with open(task_executor_log, "a", encoding="utf-8") as f:
                        f.write("\n=== Executor Actions from History (Command Loop Task) ===\n")
                        serialized_history = serialize_history(history)
                        for i, entry in enumerate(serialized_history):
                           f.write(f"\nStep {i+1}:\n")
                           if isinstance(entry, dict):
                               action_str = json.dumps(entry.get('action'), indent=2, ensure_ascii=False) if isinstance(entry.get('action'), (dict, list)) else entry.get('action')
                               llm_output_str = json.dumps(entry.get('llm_output'), indent=2, ensure_ascii=False) if isinstance(entry.get('llm_output'), (dict, list)) else entry.get('llm_output')
                               if action_str: f.write(f"  Action: {action_str}\n")
                               if llm_output_str: f.write(f"  LLM Output: {llm_output_str}\n")
                               for key, value in entry.items():
                                   if key not in ['action', 'llm_output']:
                                       f.write(f"  {key}: {value}\n")
                           else:
                               f.write(f"  {entry}\n")
                        f.write("\n")


                    # Serialize and log task history
                    task_result_path = os.path.join(task_run_dir, "run_result.json")
                    task_run_logger.info(f"Saving task run result to: {task_result_path}")
                    with open(task_result_path, "w", encoding="utf-8") as f:
                        json.dump(serialized_history, f, indent=2)

                    # Log browser state after task
                    current_url = "unknown"
                    try:
                        pages = await shared_browser_ctx.pages()
                        if pages:
                            page = pages[0] # Assume we're working in the first tab
                            current_url = await page.evaluate("() => window.location.href")
                        else:
                            task_run_logger.warning("No pages found in shared context after task run.")
                            # Avoid creating new pages here unless intended
                        task_run_logger.info(f"Browser State After Task Run: URL = {current_url}")
                    except Exception as e:
                        task_run_logger.error(f"Browser State Error after task: {str(e)}")


                    # Optional: Force executor LLM call after task (already in your code)
                    try:
                        task_run_logger.info("Performing post-task forced executor LLM call...")
                        prompt = f"""
                        Current URL: {current_url}
                        Previous Task Completed: {act}
                        Instructions: Verify the current page state relevant to the completed task and suggest if manual intervention or a specific next action is needed. Return JSON:
                        {{
                            "current_state": {{"evaluation": "Description of page state after task '{act}'"}},
                            "next_action": "Suggested next logical action or 'Ready for next task'"
                        }}
                        """
                        response = await exec_llm_task.ainvoke([HumanMessage(content=prompt)])
                        task_run_logger.info("Post-task forced LLM call completed.")
                        if hasattr(response, 'content'):
                            task_run_logger.debug(f"Post-task Forced LLM response content: {response.content}")
                        else:
                            task_run_logger.warning("Post-task forced LLM call did not return 'content'.")
                    except Exception as e:
                        task_run_logger.error(f"Error during post-task forced executor LLM call: {str(e)}")


                    # --- Added Step: Post-process the executor log for this task ---
                    run_logger.info(f"--- Post-processing executor log for task: {act} ---")
                    task_run_logger.info(f"Post-processing executor log: {task_executor_log}")
                    try:
                        process_log_images(task_executor_log)
                        run_logger.info(f"--- Finished post-processing: {task_executor_log} ---")
                        task_run_logger.info(f"Finished post-processing executor log.")
                    except Exception as e:
                        run_logger.error(f"--- Error during post-processing {task_executor_log}: {e} ---")
                        task_run_logger.error(f"Error during post-processing executor log: {e}")
                    # --- End of Added Step ---


                except Exception as task_error:
                    run_logger.exception(f"An error occurred during task '{act}': {task_error}")
                    if task_run_logger:
                        task_run_logger.error(f"Task failed: {task_error}")

                finally:
                    # --- Task Cleanup ---
                    run_logger.debug(f"Cleaning up resources for task: '{act}'")
                    # Remove screenshot handler added for this task
                    if task_handler:
                        for name in logger_names_to_attach:
                            try:
                                logging.getLogger(name).removeHandler(task_handler)
                            except ValueError: pass # Ignore if already removed
                        task_handler = None # Clear variable

                    # Clean up task agent instance
                    if task_agent:
                        del task_agent
                        task_agent = None

                    # Close and remove task-specific file handler
                    if task_run_logger and task_file_handler:
                        try:
                            task_run_logger.removeHandler(task_file_handler)
                            task_file_handler.close()
                            task_file_handler = None
                        except Exception as log_clean_e:
                            run_logger.error(f"Error cleaning up task file handler: {log_clean_e}")

                    # Remove the task logger instance itself to prevent conflicts if task name repeats
                    if 'task_logger_name' in locals() and task_logger_name in logging.Logger.manager.loggerDict:
                         # Ensure handlers are cleared before deleting logger ref implicitly by loop end
                        if task_run_logger:
                           task_run_logger.handlers.clear()
                        # No direct 'delete logger', just ensure no refs and clear handlers
                        logging.getLogger(task_logger_name).handlers.clear()

        except Exception as loop_error:
             run_logger.exception(f"An unexpected error occurred in the command loop: {loop_error}")

        finally:
            # --- Final Cleanup (after loop ends or error) ---
            run_logger.info("Command loop finished or exited. Performing final cleanup...")
            if shared_browser_ctx:
                run_logger.info("Closing shared browser context...")
                try:
                    await shared_browser_ctx.close()
                    run_logger.info("Shared browser context closed.")
                except Exception as e:
                    run_logger.error(f"Error closing browser context: {e}")
                shared_browser_ctx = None # Clear variable

            if shared_browser:
                 # Context closure should close the browser, but being explicit can help
                run_logger.info("Closing shared browser...")
                try:
                    await shared_browser.close()
                    run_logger.info("Shared browser closed.")
                except Exception as e:
                    run_logger.error(f"Error closing browser: {e}")
                shared_browser = None # Clear variable

            run_logger.info("Final cleanup complete.")

    else:
         run_logger.error("Shared browser context was not initialized. Cannot start command loop.")


    # Clean up main session logger handlers
    if run_logger and run_file_handler:
        run_logger.removeHandler(run_file_handler)
        run_file_handler.close()
    if run_logger and console_handler:
        run_logger.removeHandler(console_handler)

    print("\nScript finished.")


# -----------------------------------------------------------------
# 6.  Entry‑point
# -----------------------------------------------------------------
if __name__ == "__main__":
    # Basic logging setup until main() takes over with file handlers
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExecution interrupted by user (Ctrl+C).")
    except Exception as main_err:
        logging.exception(f"Unhandled exception in main execution: {main_err}")
