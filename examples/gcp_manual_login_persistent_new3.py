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
from browser_use import Agent
from mss import mss
from PIL import Image


# -----------------------------------------------------------------
# 1.  ENV & directories
# -----------------------------------------------------------------
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

SCREENSHOT_DIR = "screenshots"
DEBUG_LOG_DIR  = "debug_logs"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(DEBUG_LOG_DIR,  exist_ok=True)


# -----------------------------------------------------------------
# 2.  LLMs
# -----------------------------------------------------------------
exec_llm   = ChatOpenAI(model="gpt-4.1", temperature=0.5)
plan_llm   = ChatOpenAI(model="o4-mini",  temperature=1)   # <─ bigger brain


# -----------------------------------------------------------------
# 3.  Screenshot helper (unchanged)
# -----------------------------------------------------------------
class ScreenshotHandler(logging.Handler):
    def __init__(self, log_file, screenshot_dir):
        super().__init__()
        self.log_file       = log_file
        self.screenshot_dir = screenshot_dir
        self.step           = 1
        self.last_goal      = ""
        self.debug_file     = os.path.join(DEBUG_LOG_DIR, "debug_log.txt")

    async def _capture(self, filename):
        await asyncio.sleep(3)                       # wait for page paint
        try:
            with mss() as sct:
                monitor   = {"top": 100, "left": 100, "width": 1200, "height": 800}
                shot      = sct.grab(monitor)
                img       = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)
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
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            file = f"{self.screenshot_dir}/step_{self.step}_{ts}.png"
            asyncio.create_task(self._capture(file))

            entry = {
                "step":       self.step,
                "action":     msg if any(t in msg for t in ["Action", "Navigating", "Entering",
                                                            "Clicking", "Searched for", "User logged in",
                                                            "Clicked"]) else "",
                "next_goal":  msg if "Next goal" in msg else self.last_goal,
                "screenshot": file,
            }
            with open(self.log_file, "a", encoding="utf-8") as f:
                json.dump(entry, f); f.write("\n")

            if "Next goal:" in msg:
                self.last_goal = msg
            print(f"Step {self.step}: Saved {file}")
            self.step += 1

# -----------------------------------------------------------------
# 4.  Main coroutine
# -----------------------------------------------------------------
async def main():
    # ----- logging / screenshots ---------------------------------
    log_json = f"{SCREENSHOT_DIR}/log.json"
    handler  = ScreenshotHandler(log_json, SCREENSHOT_DIR)
    handler.setLevel(logging.INFO)
    for name in ["", "browser_use", "agent", "controller"]:
        logging.getLogger(name).addHandler(handler)

    # -------------------------------------------------------------
    # 4‑A  First agent: open GCP sign‑in page
    # -------------------------------------------------------------
    first_agent = Agent(
        task                 = "Navigate to Google Cloud Platform and go to sign in",
        llm                  = exec_llm,
        planner_llm          = plan_llm,          # <── NEW
        planner_interval     = 1,                 # plan every step
        use_vision_for_planner=False,
        is_planner_reasoning = False,             # json output is fine
        close_browser_on_run = False,
        enable_memory        = False,
    )
    await first_agent.run()
    print("\nLog in manually, then press Enter …")
    input()
    logging.info("User logged in to GCP")

    shared_browser     = first_agent.browser
    shared_browser_ctx = first_agent.browser_context
    del first_agent

    # -------------------------------------------------------------
    # 4‑B  Command loop
    # -------------------------------------------------------------
    try:
        while True:
            act = input("\nNext GCP action (or 'exit'): ").strip()
            if act.lower() == "exit":
                break

            fresh_agent = Agent(
                task                 = act,
                llm                  = exec_llm,
                planner_llm          = plan_llm,          # <── keep planning
                planner_interval     = 1,
                is_planner_reasoning = False,
                browser              = shared_browser,
                browser_context      = shared_browser_ctx,
                close_browser_on_run = False,
                enable_memory        = False,
            )
            await fresh_agent.run()
            del fresh_agent

    finally:
        for name in ["", "browser_use", "agent", "controller"]:
            logging.getLogger(name).removeHandler(handler)
        await shared_browser_ctx.close()
        await shared_browser.close()


# -----------------------------------------------------------------
# 5.  Entry‑point
# -----------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
