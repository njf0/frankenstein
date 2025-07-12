python eval/evaluate.py --save --model "Qwen3-4B" --split "answerable-full"
python eval/evaluate.py --save --model "Qwen3-4B" --split "answerable-full" --toolbox "arithmetic"
python eval/evaluate.py --save --model "Qwen3-4B" --split "answerable-full" --toolbox "data"
python eval/evaluate.py --save --model "Qwen3-4B" --split "answerable-full" --n-shots 1
python eval/evaluate.py --save --model "Qwen3-4B" --split "answerable-full" --n-shots 3
python eval/evaluate.py --save --model "Qwen3-4B" --split "answerable-partial"