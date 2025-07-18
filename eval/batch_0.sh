# python eval/evaluate.py --save --model "Llama-3.2-3B-Instruct" --split "answerable-full" --n-shots 1
python eval/evaluate.py --save --model "Qwen3-32B" --split "answerable-full"
python eval/evaluate.py --save --model "Qwen3-32B" --split "answerable-full" --toolbox "data"
python eval/evaluate.py --save --model "Qwen3-32B" --split "answerable-full" --n-shots 1
