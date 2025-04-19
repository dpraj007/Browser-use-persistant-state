

import os
import sys
import asyncio
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent
from mss import mss
from PIL import Image


# ---------------------------------------------------------------------------
# 1.  Initial setup
# ---------------------------------------------------------------------------
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

SCREENSHOT_DIR = "screenshots"
DEBUG_LOG_DIR  = "debug_logs"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(DEBUG_LOG_DIR,  exist_ok=True)

# ---- LLM configuration ----------------------------------------------------
llm = ChatOpenAI(model="gpt-4.1-mini", temperature=0.0)


# ---------------------------------------------------------------------------
# 2.  Helper for screenshots (unchanged)
# ---------------------------------------------------------------------------
class ScreenshotHandler(logging.Handler):
    def __init__(self, log_file, screenshot_dir):
        super().__init__()
        self.log_file = log_file
        self.screenshot_dir = screenshot_dir
        self.step = 1
        self.last_goal = ""
        self.debug_file = os.path.join(DEBUG_LOG_DIR, "debug_log.txt")

    async def _capture(self, filename):
        # Wait a bit so the browser finished painting
        await asyncio.sleep(3)
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
                "action":     msg if any(t in msg for t in ["Action", "Navigating", "Entering", "Clicking",
                                                            "Searched for", "User logged in", "Clicked"]) else "",
                "next_goal":  msg if "Next goal" in msg else self.last_goal,
                "screenshot": file,
            }
            with open(self.log_file, "a", encoding="utf-8") as f:
                json.dump(entry, f)
                f.write("\n")

            if "Next goal:" in msg:
                self.last_goal = msg
            print(f"Step {self.step}: Saved {file}")
            self.step += 1


# ---------------------------------------------------------------------------
# 3.  Main coroutine
# ---------------------------------------------------------------------------
async def main():
    # ---- logging / screenshot handler -------------------------------------
    log_json = f"{SCREENSHOT_DIR}/log.json"
    handler  = ScreenshotHandler(log_json, SCREENSHOT_DIR)
    handler.setLevel(logging.INFO)
    logging.getLogger("").addHandler(handler)
    logging.getLogger("browser_use").addHandler(handler)
    logging.getLogger("agent").addHandler(handler)
    logging.getLogger("controller").addHandler(handler)

    # -----------------------------------------------------------------------
    # 3‑A  First agent: open GCP sign‑in page (browser created here)
    # -----------------------------------------------------------------------
    print("Opening GCP login page …")
    first_agent = Agent(
        task="Navigate to Google Cloud Platform and go to sign in",
        llm=llm,
        close_browser_on_run=False,   # keep window open
        enable_memory=False,          # we don’t need long‑term vector memory
    )
    await first_agent.run()
    logging.info("Navigating to GCP sign‑in")

    # -----------------------------------------------------------------------
    # 3‑B  User performs manual sign‑in
    # -----------------------------------------------------------------------
    print("\nPlease log into your GCP account manually in the browser.")
    input("Press Enter when you are on the GCP dashboard: ")
    logging.info("User logged in to GCP")

    # ---- keep the logged‑in Playwright session alive ----------------------
    shared_browser       = first_agent.browser
    shared_browser_ctx   = first_agent.browser_context

    # We no longer need the initial agent object itself
    del first_agent

    # -----------------------------------------------------------------------
    # 3‑C  Command loop – each action gets a fresh Agent with clean context
    # -----------------------------------------------------------------------
    try:
        while True:
            action = input("\nEnter next GCP action (or 'exit'): ").strip()
            if action.lower() == "exit":
                print("Exiting …")
                break

            print(f"\nPerforming action: {action}")
            fresh_agent = Agent(
                task                 = action,
                llm                  = llm,
                browser              = shared_browser,
                browser_context      = shared_browser_ctx,
                close_browser_on_run = False,
                enable_memory        = False,
            )
            await fresh_agent.run()
            del fresh_agent

    finally:
        # -------------------------------------------------------------------
        # 3‑D  Clean‑up – close the shared browser context exactly once
        # -------------------------------------------------------------------
        logging.getLogger("").removeHandler(handler)
        logging.getLogger("browser_use").removeHandler(handler)
        logging.getLogger("agent").removeHandler(handler)
        logging.getLogger("controller").removeHandler(handler)

        await shared_browser_ctx.close()
        await shared_browser.close()


# ---------------------------------------------------------------------------
# 4.  Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())