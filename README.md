
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./static/browser-use-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="./static/browser-use.png">
  <img alt="Shows a black Browser Use Logo in light color mode and a white one in dark color mode." src="./static/browser-use.png"  width="full">
</picture>

<h1 align="center">Browser‑use — NYU Cloud Agent Project Fork 🤖</h1>

<!-- Badges mostly point to upstream so stargazers / docs links keep working -->
[![GitHub stars](https://img.shields.io/github/stars/browser-use/browser-use?style=social)](https://github.com/browser-use/browser-use/stargazers)
[![Discord](https://img.shields.io/discord/1303749220842340412?color=7289DA&label=Discord&logo=discord&logoColor=white)](https://link.browser-use.com/discord)
[![Documentation](https://img.shields.io/badge/Documentation-📕-blue)](https://docs.browser-use.com)
[![Twitter Follow](https://img.shields.io/twitter/follow/Gregor?style=social)](https://x.com/gregpr07)
[![Twitter Follow](https://img.shields.io/twitter/follow/Magnus?style=social)](https://x.com/mamagnus00)


> **ℹ️ About this fork**  
> This repository is a specific fork of `browser-use` adapted and utilized for the **NYU Tandon School of Engineering project: "Improving VLM Instruct Models to Perform Actions on New Environments"** by Shubham Goel, Dhairyasheel Patil, Jasmitha Pissay Narayana, and Devarshi Chatterjee.
>
> It tracks the upstream project ([browser-use/browser-use](https://github.com/browser-use/browser-use)) while incorporating modifications crucial for our research:
> - **Persistent Playwright Profiles:** Integration of `user_data_dir` and `storage_state_path` options to maintain browser sessions across runs, essential for reusing authenticated states (e.g., after manual MFA login). See `service.py` modifications.
> - **Cloud Console Automation Examples:** Includes specific scripts (like `gcp_administrator_agent.py`) demonstrating automated task execution within the Google Cloud Platform (GCP) console, incorporating a human-in-the-loop step for initial secure login.
> - **Enhanced Logging & State Capture:** Modifications to log detailed execution traces, including screenshots, instructions, DOM actions, and LLM prompts/responses, structured for dataset creation.
> - **Minor Session/Task Management:** Adaptations to handle sequential execution of predefined workflows.
>
> **If you are looking for the general-purpose `browser-use` library, please refer to the [original upstream repository](https://github.com/browser-use/browser-use).** This fork is tailored to the specific needs and context of our research project.

---

## 📊 Project Dataset

The primary output generated using this modified `browser-use` agent is a dataset of screenshot-instruction-action triples for automating tasks within the Google Cloud Platform console.

**Access the dataset here:**  
[➡️ **GCP Automation Dataset (Dummy Link)**](https://drive.google.com/drive/folders/YOUR_DUMMY_SHARED_FOLDER_LINK_HERE)

*(Please replace `YOUR_DUMMY_SHARED_FOLDER_LINK_HERE` with the actual link if available, or keep as is if purely illustrative)*

---

🌐 Browser‑use is the easiest way to connect your AI agents with the browser. (Upstream description)

💡 See what others are building with the original library and share your projects in the main project's [Discord](https://link.browser-use.com/discord)!

# Quick start (Based on Upstream)

Requires Python >= 3.11.

Install the base library via pip:
```bash
pip install browser-use
```
*(Note: Our project used this fork directly from the source code, potentially with additional dependencies listed in our project requirements.)*

Install Playwright browser binaries:
```bash
playwright install chromium
```

Spin up a basic agent (Example from upstream):

```python
from langchain_openai import ChatOpenAI
from browser_use import Agent
import asyncio
from dotenv import load_dotenv
load_dotenv()

async def main():
    agent = Agent(
        task="Compare the price of gpt-4o and Claude 3.5 Sonnet", # Example Task
        llm=ChatOpenAI(model="gpt-4o"), # Example LLM
        # For persistent state in this fork, check modified Agent init or service.py
    )
    await agent.run()

asyncio.run(main())
```

Add your API keys for the desired LLM provider to your `.env` file.
```bash
# Example Keys (Add keys relevant to your LLM provider)
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
# ... etc
```

For general settings, models, and more, check out the upstream [documentation 📕](https://docs.browser-use.com). For usage specific to our project (like running GCP workflows), refer to the scripts within this repository (e.g., `gcp_administrator_agent.py`).

# Demos (Illustrative Examples from Upstream)

<br/><br/>

Example Task: Write a letter in Google Docs.

![Letter to Papa](https://github.com/user-attachments/assets/242ade3e-15bc-41c2-988f-cbc5415a66aa)

<br/><br/>

Example Task: Find Hugging Face models and save to file.

https://github.com/user-attachments/assets/de73ee39-432c-4b97-b4e8-939fd7f323b3

<br/><br/>

*Note: The core capability demonstrated above was leveraged in our project to interact with the more complex GCP console environment.*

# Project Context & Vision

This fork served as the execution engine for our research project aimed at improving VLM agents for performing administrative tasks in complex web UIs like the GCP console. Our goal was to build a robust pipeline for generating interaction data (screenshots, instructions, actions) to facilitate the fine-tuning and evaluation of VLMs for reliable GUI automation.

The vision and roadmap of the *upstream* `browser-use` project can be found in their repository. This fork focuses specifically on the modifications needed for our research objectives.

# Contributing

Contributions are welcome to the **original upstream [browser-use/browser-use](https://github.com/browser-use/browser-use) repository**. This fork is maintained specifically for the context of the completed NYU research project and is unlikely to see further development or accept external contributions.

# Local Setup

To learn more about the base library's structure, check out the upstream documentation on [local setup 📕](https://docs.browser-use.com/development/local-setup).

To run the specific GCP automation scripts developed for our project, examine the Python scripts within this repository and ensure you have the necessary credentials (GCP access, LLM API keys) configured.

`main` branch reflects the state used during our project.

---

# Citation

If you use the original Browser Use library in your research or project, please cite the upstream software:

```bibtex
@software{browser_use2024,
  author = {Müller, Magnus and Žunič, Gregor},
  title = {Browser Use: Enable AI to control your browser},
  year = {2024},
  publisher = {GitHub},
  url = {https://github.com/browser-use/browser-use}
}
```

If you use the **dataset generated** by our project or refer to the findings and methods presented in our associated research paper ("Improving VLM Instruct Models to Perform Actions on New Environments"), please cite our paper directly (details to be added upon publication/submission).

---

 <div align="center"> <img src="https://github.com/user-attachments/assets/06fa3078-8461-4560-b434-445510c1766f" width="400"/>

[![Twitter Follow](https://img.shields.io/twitter/follow/Gregor?style=social)](https://x.com/gregpr07)
[![Twitter Follow](https://img.shields.io/twitter/follow/Magnus?style=social)](https://x.com/mamagnus00)

 </div>

<div align="center">
Upstream project made with ❤️ in Zurich and San Francisco
 </div>
