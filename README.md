
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./static/browser-use-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="./static/browser-use.png">
  <img alt="Shows a black Browser Use Logo in light color mode and a white one in dark color mode." src="./static/browser-use.png"  width="full">
</picture>

<h1 align="center">Browser‑use — GCP/AWS Automation Fork (NYU VLM Project) 🤖</h1>

<!-- Badges pointing to upstream for community links -->
[![GitHub stars](https://img.shields.io/github/stars/browser-use/browser-use?style=social)](https://github.com/browser-use/browser-use/stargazers)
[![Discord](https://img.shields.io/discord/1303749220842340412?color=7289DA&label=Discord&logo=discord&logoColor=white)](https://link.browser-use.com/discord) <!-- Link to original Discord -->
[![Documentation](https://img.shields.io/badge/Documentation-📕-blue)](https://docs.browser-use.com) <!-- Link to original Docs -->

> **ℹ️ About this fork**
> This repository is a fork maintained by **Shubham Goel, Dhairyasheel Patil, Jasmitha Pissay Narayana, and Devarshi Chatterjee** for the NYU Tandon "Improving VLM Instruct Models to Perform Actions on New Environments" class project.
> It tracks the upstream [browser-use](https://github.com/browser-use/browser-use) project while adding specific modifications for automating complex cloud console environments:
> - **Persistent Playwright State:** Modified agent (`service.py`) to prevent browser closure (`close_browser_on_run=False`) and potentially leverage `user_data_dir` / `storage_state` for session reuse after manual login/MFA.
> - **Enhanced Logging:** Integrated robust logging mechanisms to capture screenshot-instruction-action triples during automated task execution.
> - **Cloud Console Focus:** Includes example scripts and configurations tailored for automating tasks within Google Cloud Platform (GCP) and initial experiments on Amazon Web Services (AWS).
> - **Human-in-the-Loop Login:** Implemented a simple CLI prompt mechanism to pause execution, allow manual authentication, and then resume automation within the same browser session.
>
> If you need the standard library features, please refer to the [original repository](https://github.com/browser-use/browser-use).

🌐 Browser‑use is the easiest way to connect your AI agents with the browser, adapted here for complex cloud console automation and data generation.

---

## Project Context & Dataset

This fork was instrumental in generating a dataset for fine-tuning Vision-Language Models (VLMs) to perform administrative tasks in cloud consoles. We automated over 200 distinct GCP workflows (e.g., VM provisioning, IAM role configuration, storage bucket setup), capturing high-resolution screenshots, the natural language sub-instruction, and the precise DOM action taken at each step.

💾 **Access the Generated Dataset:**
The complete dataset, containing 10,061 screenshot-instruction-action triples, along with processing scripts, is available here:

➡️ **[Link to GCP Automation Dataset (Google Drive)](https://drive.google.com/drive/folders/DUMMY_LINK_REPLACE_ME)** ⬅️
*(Please replace `DUMMY_LINK_REPLACE_ME` with your actual shareable Google Drive folder ID)*

This dataset serves as the foundation for the future work outlined in our project report, aiming to improve VLM performance in interactive web environments.

---

## Quick Start (Using this Fork's Features)

Ensure you have Python >= 3.11.

Install the base library (this fork assumes modifications are applied locally or installed from this fork's source):
```bash
pip install browser-use


Install Playwright browser binaries:

playwright install chromium
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bash
IGNORE_WHEN_COPYING_END

Example script demonstrating persistent state and a GCP task (adapt LLM provider/model as needed):

# Ensure you have your LLM API key in a .env file (e.g., GEMINI_API_KEY)
# or configure the client appropriately.
from langchain_google_genai import ChatGoogleGenerativeAI # Or other provider
from browser_use import Agent
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def main():
    # Note: This example assumes modifications for persistence
    # and human-in-the-loop login are active in your local Agent setup.
    agent = Agent(
        # Example GCP Task
        task="Navigate to Google Cloud Console 'IAM & Admin' page, then filter the principal list to show only 'Service Accounts'.",
        llm=ChatGoogleGenerativeAI(model="gemini-pro"), # Or "gemini-flash", etc.
        # Add parameters here if your fork exposes them directly,
        # otherwise ensure service.py is modified for persistence.
        # e.g., close_browser_on_run=False (if exposed)
    )

    # The agent should pause for manual login if implemented
    print("Agent starting. Please complete GCP login in the opened browser window if prompted, then press Enter in the console where the agent is running.")

    await agent.run()

    print("Agent run complete. Browser window should remain open if persistence is enabled.")

if __name__ == "__main__":
    asyncio.run(main())
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Python
IGNORE_WHEN_COPYING_END

Add required API keys to your .env file:

# Example for Google Gemini
GEMINI_API_KEY=your_google_api_key

# Add keys for other providers if used (OpenAI, Anthropic, etc.)
# OPENAI_API_KEY=
# ANTHROPIC_API_KEY=
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bash
IGNORE_WHEN_COPYING_END

For base library settings and models, refer to the original documentation 📕.

Project Goals & Future Work

This fork and the generated dataset support our ongoing research into improving VLM agents for complex GUI interactions. Our future work, detailed in our project report, includes:

Addressing Interaction Challenges: Developing robust solutions for scrolling, handling dynamic UI elements (pop-ups, async updates), and improving synthetic data realism within the GCP console.

VLM Adaptation: Fine-tuning models like Qwen-2.5VL-7B using the generated dataset via Supervised Fine-Tuning (SFT) and exploring Reinforcement Fine-Tuning (RFT) for better data efficiency and reasoning.

Reinforcement Learning: Investigating RL techniques to further optimize the agent's decision-making for multi-step tasks, focusing on robust reward design and environment interaction.

Comprehensive Evaluation: Assessing agent performance using metrics beyond task completion, including interaction robustness, efficiency, and generalization within the GCP environment.

Contributing to this Fork

This fork was developed specifically for the NYU class project mentioned above. While direct contributions are not actively solicited, feel free to raise issues related to the specific modifications made here. For contributions to the core browser-use library, please engage with the original repository.

Citation

If you use the core Browser Use library in your research or project, please cite the original work:

@software{browser_use2024,
  author = {Müller, Magnus and Žunič, Gregor},
  title = {Browser Use: Enable AI to control your browser},
  year = {2024},
  publisher = {GitHub},
  url = {https://github.com/browser-use/browser-use}
}
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bibtex
IGNORE_WHEN_COPYING_END

If you use the dataset generated by this fork or reference the specific modifications made for cloud console automation in your work, please cite our project report:

@techreport{goel2024improvingvlm,
  author    = {Goel, Shubham and Patil, Dhairyasheel and Narayana, Jasmitha Pissay and Chatterjee, Devarshi},
  title     = {Improving VLM Instruct Models to Perform Actions on New Environments},
  institution = {NYU Tandon School of Engineering},
  year      = {2024},
  note      = {Class Project Report}
  % Add URL or specific identifier if available
}
IGNORE_WHEN_COPYING_START
content_copy
download
Use code with caution.
Bibtex
IGNORE_WHEN_COPYING_END
<div align="center">
Fork maintained for NYU Tandon CDS Project - Spring 2024
</div>
