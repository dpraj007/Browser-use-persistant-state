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
    def __init__(self, log_file):
        self.log_file = log_file

    def on_llm_start(self, serialized, prompts, **kwargs):
        model_name = serialized.get("kwargs", {}).get("model_name", "unknown")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"\n=== LLM Prompt (Model: {model_name}) ===\n")
            for prompt in prompts:
                f.write(f"{prompt}\n")
            f.flush()

    def on_llm_end(self, response, **kwargs):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"\n=== LLM Response ===\n")
            for generation in response.generations:
                for gen in generation:
                    try:
                        # Attempt to parse and pretty-print the JSON
                        json_response = json.loads(gen.text)
                        formatted_json = json.dumps(json_response, indent=4, ensure_ascii=False)
                        f.write(f"{formatted_json}\n")
                    except json.JSONDecodeError:
                        # If not valid JSON, log as plain text
                        f.write(f"{gen.text}\n")
            f.write("\n")
            f.flush()

    def on_llm_error(self, error, **kwargs):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"\n=== LLM Error ===\n{str(error)}\n\n")
            f.flush()

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
async def main():
    # Create unique run folder
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(BASE_DIR, f"run_{run_ts}")
    os.makedirs(run_dir, exist_ok=True)

    # Set up log files for planner and executor
    planner_log_file = os.path.join(run_dir, "planner_log.txt")
    executor_log_file = os.path.join(run_dir, "executor_log.txt")
    run_log_file = os.path.join(run_dir, "run_log.txt")

    # Set up general run logger
    run_logger = logging.getLogger("run")
    run_logger.setLevel(logging.INFO)
    run_file_handler = logging.FileHandler(run_log_file, encoding="utf-8")
    run_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    run_logger.addHandler(run_file_handler)

    # Set up LLM callbacks
    planner_callback = LLMLogCallback(planner_log_file)
    executor_callback = LLMLogCallback(executor_log_file)

    # -----------------------------------------------------------------
    # 5‑A  First agent: open GCP sign‑in page
    # -----------------------------------------------------------------
    exec_llm = ChatOpenAI(model="gpt-4.1", temperature=0.5, callbacks=[executor_callback])
    plan_llm = ChatOpenAI(model="o4-mini", temperature=1.0, callbacks=[planner_callback])

    first_agent = Agent(
        task="Navigate to Google Cloud Platform and go to sign in",
        llm=exec_llm,
        planner_llm=plan_llm,
        planner_interval=1,
        use_vision_for_planner=False,
        is_planner_reasoning=False,
        close_browser_on_run=False,
        enable_memory=False,
    )

    # Set up screenshot handler for this run
    screenshot_dir = os.path.join(run_dir, "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)
    log_json = os.path.join(run_dir, "log.json")
    handler = ScreenshotHandler(log_json, screenshot_dir)
    handler.setLevel(logging.INFO)
    for name in ["", "browser_use", "agent", "controller"]:
        logging.getLogger(name).addHandler(handler)

    # Log task start
    run_logger.info(f"Task Started: Navigate to Google Cloud Platform and go to sign in")

    # Run the agent
    run_logger.info("Running Agent for Task")
    history = await first_agent.run()

    # Serialize and log agent history
    serialized_history = serialize_history(history)
    with open(os.path.join(run_dir, "run_result.json"), "w", encoding="utf-8") as f:
        json.dump(serialized_history, f, indent=2)

    # Log browser state after run
    try:
        context = first_agent.browser_context
        pages = await context.pages()
        if not pages:
            page = await context.new_page()
            await page.goto("about:blank")
        else:
            page = pages[0]
        current_url = await page.evaluate("() => window.location.href")
        run_logger.info(f"Browser State After Run: URL = {current_url}")
    except Exception as e:
        run_logger.error(f"Browser State Error: {str(e)}")

    # Force executor LLM call to confirm sign-in page
    try:
        from langchain_core.messages import HumanMessage
        prompt = f"""
        Current URL: {current_url}
        Task: Verify that the Google Cloud Platform sign-in page is loaded and identify the next action.
        Instructions: Confirm if the sign-in interface is present. If so, suggest the next action (e.g., click the sign-in button or mark task as done). Return a JSON response with the format:
        {{
            "current_state": {{"evaluation": "Description of page state"}},
            "next_action": "Suggested action (e.g., click_element, done)"
        }}
        """
        response = await exec_llm.ainvoke([HumanMessage(content=prompt)])
        with open(executor_log_file, "a", encoding="utf-8") as f:
            f.write(f"\n=== Forced Executor LLM Call ===\n")
            f.write(f"Prompt: {prompt}\n")
            f.write(f"Response: {response.content}\n")
            f.flush()
    except Exception as e:
        with open(executor_log_file, "a", encoding="utf-8") as f:
            f.write(f"\n=== Forced Executor LLM Error: {str(e)} ===\n")
            f.flush()

    print("\nLog in manually, then press Enter …")
    input()
    run_logger.info("User logged in to GCP")

    shared_browser = first_agent.browser
    shared_browser_ctx = first_agent.browser_context
    del first_agent

    # Remove handler for first agent
    for name in ["", "browser_use", "agent", "controller"]:
        logging.getLogger(name).removeHandler(handler)

    # -------------------------------------------------------------
    # 5‑B  Command loop
    # -------------------------------------------------------------
    try:
        while True:
            act = input("\nNext GCP action (or 'exit'): ").strip()
            if act.lower() == "exit":
                break

            # Create new run folder for each command loop task
            run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            task_run_dir = os.path.join(BASE_DIR, f"task_{act.replace(' ', '_')}_{run_ts}")
            os.makedirs(task_run_dir, exist_ok=True)

            # Set up log files for this task run
            task_planner_log = os.path.join(task_run_dir, "planner_log.txt")
            task_executor_log = os.path.join(task_run_dir, "executor_log.txt")
            task_run_log = os.path.join(task_run_dir, "run_log.txt")

            # Set up task run logger
            task_run_logger = logging.getLogger(f"task_run_{act}")
            task_run_logger.setLevel(logging.INFO)
            task_file_handler = logging.FileHandler(task_run_log, encoding="utf-8")
            task_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
            task_run_logger.addHandler(task_file_handler)

            # Set up LLM callbacks for this task
            task_planner_callback = LLMLogCallback(task_planner_log)
            task_executor_callback = LLMLogCallback(task_executor_log)

            # Create new agent for this task
            exec_llm_task = ChatOpenAI(model="gpt-4.1", temperature=0.5, callbacks=[task_executor_callback])
            plan_llm_task = ChatOpenAI(model="o4-mini", temperature=1.0, callbacks=[task_planner_callback])

            fresh_agent = Agent(
                task=act,
                llm=exec_llm_task,
                planner_llm=plan_llm_task,
                planner_interval=1,
                is_planner_reasoning=False,
                browser=shared_browser,
                browser_context=shared_browser_ctx,
                close_browser_on_run=False,
                enable_memory=False,
            )

            # Set up screenshot handler for this task run
            task_screenshot_dir = os.path.join(task_run_dir, "screenshots")
            os.makedirs(task_screenshot_dir, exist_ok=True)
            task_log_json = os.path.join(task_run_dir, "log.json")
            task_handler = ScreenshotHandler(task_log_json, task_screenshot_dir)
            task_handler.setLevel(logging.INFO)
            for name in ["", "browser_use", "agent", "controller"]:
                logging.getLogger(name).addHandler(task_handler)

            # Log task start
            task_run_logger.info(f"Task Started: {act}")

            # Run the agent
            task_run_logger.info("Running Agent for Task")
            history = await fresh_agent.run()

            # Serialize and log agent history
            serialized_history = serialize_history(history)
            with open(os.path.join(task_run_dir, "run_result.json"), "w", encoding="utf-8") as f:
                json.dump(serialized_history, f, indent=2)

            # Log browser state after run
            try:
                context = fresh_agent.browser_context
                pages = await context.pages()
                if not pages:
                    page = await context.new_page()
                    await page.goto("about:blank")
                else:
                    page = pages[0]
                current_url = await page.evaluate("() => window.location.href")
                task_run_logger.info(f"Browser State After Run: URL = {current_url}")
            except Exception as e:
                task_run_logger.error(f"Browser State Error: {str(e)}")

            # Force executor LLM call for command loop task
            try:
                prompt = f"""
                Current URL: {current_url}
                Task: {act}
                Instructions: Verify the current page state and suggest the next action to accomplish the task. Return a JSON response with the format:
                {{
                    "current_state": {{"evaluation": "Description of page state"}},
                    "next_action": "Suggested action (e.g., click_element, input_text)"
                }}
                """
                response = await exec_llm_task.ainvoke([HumanMessage(content=prompt)])
                with open(task_executor_log, "a", encoding="utf-8") as f:
                    f.write(f"\n=== Forced Executor LLM Call ===\n")
                    f.write(f"Prompt: {prompt}\n")
                    f.write(f"Response: {response.content}\n")
                    f.flush()
            except Exception as e:
                with open(task_executor_log, "a", encoding="utf-8") as f:
                    f.write(f"\n=== Forced Executor LLM Error: {str(e)} ===\n")
                    f.flush()

            # Clean up: remove handler after task
            for name in ["", "browser_use", "agent", "controller"]:
                logging.getLogger(name).removeHandler(task_handler)
            del fresh_agent

    finally:
        await shared_browser_ctx.close()
        await shared_browser.close()
        # Close the run log handlers
        run_logger.removeHandler(run_file_handler)
        run_file_handler.close()

# -----------------------------------------------------------------
# 6.  Entry‑point
# -----------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())