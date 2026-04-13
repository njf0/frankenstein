# frankenstein

`frankenstein` is a research codebase for generating and evaluating multi-hop question answering over tabular data.

The project pairs an LLM "meta-reasoner" with a small tool set for data retrieval and arithmetic, then evaluates both answer accuracy and tool-use behaviour. The repo includes the dataset-generation code, the released dataset splits, and the evaluation and analysis code used in the project.

## Repository Layout

- `frankenstein/`: question templates, slot filling, tool definitions, model wrappers, and dataset generation code
- `dataset/`: released dataset splits
- `eval/`: evaluation runner, batch scripts, and analysis utilities
- `resources/`: indicator and country/region metadata used by the generator and tools
- `examples/`: model-specific chat templates

Note: analysis notebooks are provided, but the runs that they depend on are not included in the repo due to size.

The four dataset splits included here are:

- `answerable-full`
- `answerable-partial`
- `unanswerable-partial`
- `unanswerable-missing`

## Setup

After cloning the repo, use `uv` to create the virtual environment and install dependencies:

```bash
uv sync
source .venv/bin/activate
```

For model inference, the evaluator can be pointed at API-backed models or locally served models, depending on your setup. For local open-weight models, a `vllm serve` workflow is one straightforward option.

## Dataset Generation

Pre-generated dataset files are already included under `dataset/`, so you do not need to rebuild them to run evaluations.

To regenerate the dataset:

```bash
python frankenstein/fill_templates.py --number 100 --save --overwrite
```

`--number` controls how many examples to generate per template/category where possible. You can also restrict generation to particular templates with `--templates`.

## Running Evaluations

The main entry point is `eval/evaluate.py`.

Example runs:

```bash
python eval/evaluate.py --model-name "Llama-3.1-8B-Instruct" --split answerable-full --save
python eval/evaluate.py --model-name "openai/gpt-5-mini" --split unanswerable-partial --toolbox data --save
```

Saved outputs are written under `eval/runs/` as JSONL files containing per-example metadata, messages, and tool calls.

The available toolboxes are:

- `all`
- `arithmetic`
- `data`
- `none`

## Analysis

`eval/analysis.py` contains the main analysis helpers for comparing predicted and gold tool calls, computing precision/recall-style summaries, and inspecting error patterns.

The notebooks in `eval/` build on saved run outputs for exploratory and summary analysis.

## Notes

- The reasoning tools live in `frankenstein/tools/`.
- The current generator and tool layer are built around World Bank indicator data and UN M49 country/region structure.
- The code is organised around the workflow used in the project rather than as a general-purpose framework, but the core dataset-generation and evaluation pieces are reasonably self-contained.

## Acknowledgements

This project uses metadata derived from World Bank Open Data and UN M49 country and region classifications.

## License

MIT. See `LICENSE`.
