# import os
# import sys

# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# import asyncio

# from dotenv import load_dotenv
# from langchain_openai import ChatOpenAI

# from browser_use import Agent

# load_dotenv()

# # Initialize the model
# llm = ChatOpenAI(
# 	model='gpt-4o',
# 	temperature=0.0,
# )
# task = 'Find the founders of browser-use and draft them a short personalized message'

# agent = Agent(task=task, llm=llm)


# async def main():
# 	await agent.run()


# if __name__ == '__main__':
# 	asyncio.run(main())


import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add project root to path

import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI # Import ChatOpenAI

# Import Browser/Context classes
from browser_use import Agent, Browser, BrowserConfig, BrowserContextConfig

# Load .env file (contains API keys and logging level)
load_dotenv()

# --- Configuration ---
# Ensure your OPENAI_API_KEY is in the .env file
LLM_MODEL = "gpt-4.1" # Or any other OpenAI model you prefer
TASK = "Login to GCP and summarize my resource usages over the year . When asked for login ask me to enter details" # Define the task for the agent

# --- Paths for Saving Results ---
SAVE_CONVERSATION_PATH = "./tmp/conversation_logs" # Directory to save agent conversation steps
SAVE_TRACE_PATH = "./tmp/traces" # Directory to save Playwright traces
SAVE_HAR_PATH = "./tmp/network_logs/log.har" # File path to save HAR network logs

# Create directories if they don't exist
os.makedirs(SAVE_CONVERSATION_PATH, exist_ok=True)
os.makedirs(SAVE_TRACE_PATH, exist_ok=True)
os.makedirs(os.path.dirname(SAVE_HAR_PATH), exist_ok=True)
# --- End Configuration ---

# Initialize the OpenAI model
llm = ChatOpenAI(
    model=LLM_MODEL,
    temperature=0.0,
    # Add other parameters like max_tokens if needed
)

# Initialize Browser and Context with saving options
browser = Browser(
    config=BrowserConfig(
        # You can add browser-level configs here if needed
        new_context_config=BrowserContextConfig(
            trace_path=SAVE_TRACE_PATH,
            save_har_path=SAVE_HAR_PATH,
            # Add other context configs like user_agent, viewport size etc. if needed
        )
    )
)

# Initialize the Agent, passing the OpenAI LLM and conversation path
agent = Agent(
    task=TASK,
    llm=llm,
    browser=browser, # Pass the configured browser
    save_conversation_path=SAVE_CONVERSATION_PATH # Enable saving conversation history
)

async def main():
    print(f"Starting agent with task: {TASK}")
    print(f"Using model: {LLM_MODEL}")
    print(f"Saving conversation logs to: {os.path.abspath(SAVE_CONVERSATION_PATH)}")
    print(f"Saving traces to: {os.path.abspath(SAVE_TRACE_PATH)}")
    print(f"Saving HAR logs to: {os.path.abspath(SAVE_HAR_PATH)}")

    try:
        # Run the agent
        await agent.run(max_steps=1000) # Limit steps for this test
        print("Agent run finished.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure browser is closed
        await browser.close()
        print("Browser closed.")

if __name__ == '__main__':
    # Ensure the event loop policy is set correctly for Windows if needed
    # if os.name == 'nt':
    #     asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
