#!/usr/bin/env bash
set -euo pipefail

python eval/evaluate.py --save --model-name "Llama-3.2-3B-Instruct" --split "unanswerable-partial" --n-shots 1
python eval/evaluate.py --save --model-name "Qwen3-14B" --split "unanswerable-partial"
python eval/evaluate.py --save --model-name "openai/gpt-5-mini" --n-shots 3
python eval/evaluate.py --save --model-name "openai/gpt-5-nano" --n-shots 1
python eval/evaluate.py --save --model-name "openai/gpt-5-mini" --toolbox data
python eval/evaluate.py --save --model-name "openai/gpt-5-nano" --toolbox data
