# frankenstein

FRANK-inspired object-level reasoning with an LLM-based meta-level reasoner.

---

## Overview

**frankenstein** is a framework for evaluating large language models (LLMs) on complex, multi-hop question answering tasks over tabular data. Inspired by the FRANK benchmark, this project combines object-level reasoning with an LLM-driven meta-reasoner to address challenging data scenarios.

## Features

- **Object-Level Reasoning:** Modular actions for manipulating and querying tabular data.
- **Meta-Level LLM Reasoner:** Uses LLMs to plan, decompose, and solve multi-step questions.
- **World Bank Data Integration:** Access to a range of global development indicators.
- **Tool-Use Evaluation:** Tracks and analyzes tool calls and reasoning steps.
- **Flexible Prompting:** Configurable prompts and toolsets for different evaluation settings.
- **Extensible Architecture:** Designed for adding new tools, datasets, and evaluation templates.
- **Logging & Visualization:** Provides logs and output tables for evaluation and debugging.

## Motivation

Evaluating LLMs on real-world, multi-hop reasoning tasks is important for understanding their capabilities and limitations. **frankenstein** offers a platform for such evaluation, enabling users to:

- Benchmark LLMs on compositional, data-driven questions.
- Analyze reasoning chains and intermediate tool use.
- Develop and test new prompting and tool-use strategies.

## Setup
```bash
cd frankenstein
uv sync
source .venv/bin/activate
python setup.sh
```

## Usage

1. **Install dependencies:**
   See `pyproject.toml` for required packages.

2. **Fetch World Bank data:**
   Use the scripts in `resources/` to download and preprocess indicator data.

3. **Generate and evaluate questions:**
   Use the evaluation scripts to run LLMs on datasets and analyze their performance.

4. **Customize and extend:**
   Add new tools, templates, or datasets as needed.

## Project Highlights

- **Research-Ready:** Built for reproducibility and extensibility.
- **Transparent:** Reasoning steps and tool calls are logged for inspection.
- **Open to Contributions:** Feedback and improvements are welcome.

## Acknowledgements

- Uses data from the [World Bank Open Data](https://data.worldbank.org/).

---
