import os
import sys
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
import streamlit as st
from langchain_openai import ChatOpenAI

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from browser_use import Agent, Browser, BrowserConfig

# Environment setup
load_dotenv()
if not os.getenv('OPENAI_API_KEY'):
    st.error("OPENAI_API_KEY not found in environment variables!")
    st.stop()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Streamlit page config
st.set_page_config(
    page_title="GCP Browser Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize models
@st.cache_resource
def init_models():
    exec_llm = ChatOpenAI(model="gpt-4.1", temperature=0.5)
    plan_llm = ChatOpenAI(model="o4-mini", temperature=1)
    return exec_llm, plan_llm

# Session state initialization
if 'browser' not in st.session_state:
    st.session_state.browser = None
if 'browser_context' not in st.session_state:
    st.session_state.browser_context = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False

# Helper function for async operations
async def run_async(coro):
    try:
        return await coro
    except Exception as e:
        logger.error(f"Async operation failed: {str(e)}")
        st.error(f"Operation failed: {str(e)}")
        return None

# Initialize GCP session
async def init_gcp_session():
    try:
        exec_llm, plan_llm = init_models()
        
        # Initialize browser with config
        browser = Browser(
            config=BrowserConfig(
                headless=False,  # Set to True for headless mode
                viewport_expansion=0
            )
        )
        
        agent = Agent(
            task="Navigate to Google Cloud Platform and go to sign in",
            llm=exec_llm,
            planner_llm=plan_llm,
            browser=browser,
            planner_interval=1,
            use_vision_for_planner=False,
            is_planner_reasoning=False,
            close_browser_on_run=False,
            enable_memory=False,
            max_steps=10
        )
        
        await agent.run()
        return agent
    except Exception as e:
        logger.error(f"Session initialization failed: {str(e)}")
        st.error(f"Failed to initialize session: {str(e)}")
        return None

# Main UI
st.title("GCP Browser Agent Interface 🤖")

# Display chat history
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Handle GCP session initialization
if not st.session_state.is_logged_in:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("Start by initializing the GCP login session and then confirm once you've logged in manually.")
    
    if st.button("Start GCP Login Session", type="primary"):
        with st.spinner("Initializing GCP login page..."):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                agent = loop.run_until_complete(init_gcp_session())
                if agent:
                    st.session_state.browser = agent.browser
                    st.session_state.browser_context = agent.browser_context
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": "🌐 GCP login page is ready. Please log in manually in the browser window and click 'Confirm Login' when done."
                    })
            except Exception as e:
                st.error(f"Failed to start session: {str(e)}")
            finally:
                loop.close()
            st.rerun()

    if st.session_state.browser and st.button("Confirm Login", type="primary"):
        st.session_state.is_logged_in = True
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": "✅ Login confirmed! You can now start sending GCP commands."
        })
        st.rerun()

else:
    # Chat input for GCP commands
    if prompt := st.chat_input("Enter your GCP command"):
        if prompt.lower() == "exit":
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                async def cleanup():
                    if st.session_state.browser_context:
                        await st.session_state.browser_context.close()
                    if st.session_state.browser:
                        await st.session_state.browser.close()
                loop.run_until_complete(cleanup())
            except Exception as e:
                logger.error(f"Cleanup failed: {str(e)}")
            finally:
                loop.close()
                st.session_state.clear()
                st.rerun()
        
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        with st.chat_message("assistant"):
            with st.spinner("Executing command..."):
                async def execute_command(command):
                    try:
                        exec_llm, plan_llm = init_models()
                        
                        agent = Agent(
                            task=command,
                            llm=exec_llm,
                            planner_llm=plan_llm,
                            planner_interval=1,
                            is_planner_reasoning=False,
                            browser=st.session_state.browser,
                            browser_context=st.session_state.browser_context,
                            close_browser_on_run=False,
                            enable_memory=False,
                            max_steps=25
                        )
                        result = await agent.run()
                        return result
                    except Exception as e:
                        logger.error(f"Command execution failed: {str(e)}")
                        st.error(f"Command failed: {str(e)}")
                        return None

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(execute_command(prompt))
                    if result:
                        response = f"✅ Completed command: {prompt}"
                        if hasattr(result, 'extracted_content'):
                            response += f"\n\n📋 Result: {result.extracted_content}"
                        st.write(response)
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": response
                        })
                finally:
                    loop.close()

# Sidebar with session control and status
with st.sidebar:
    st.header("Session Control")
    if st.button("Reset Session", type="secondary"):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def cleanup():
                if st.session_state.browser_context:
                    await st.session_state.browser_context.close()
                if st.session_state.browser:
                    await st.session_state.browser.close()
            loop.run_until_complete(cleanup())
        except Exception as e:
            logger.error(f"Reset failed: {str(e)}")
            st.error(f"Error during reset: {str(e)}")
        finally:
            loop.close()
            st.session_state.clear()
            st.rerun()
    
    st.markdown("---")
    st.markdown("### Session Status")
    st.write(f"Logged in: {'✅' if st.session_state.is_logged_in else '❌'}")
    st.write(f"Browser active: {'✅' if st.session_state.browser else '❌'}")
    
    st.markdown("---")
    st.markdown("### Help")
    st.markdown("""
    **Commands:**
    - Type your GCP commands in the chat
    - Type 'exit' to close the session
    - Use 'Reset Session' to start over
    """)

# Footer
st.markdown("---")
st.markdown("💡 Type 'exit' to end the session and close the browser.")

if __name__ == "__main__":
    # This will only run when the script is run directly
    logging.info("GCP Browser Agent Interface started")