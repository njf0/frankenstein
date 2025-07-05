python eval/evaluate.py --save --model "openai/gpt-4.1-mini" --split "answerable-full"
# python eval/evaluate.py --save --model "openai/gpt-4.1-mini" --split "answerable-full" --toolbox "arithmetic"
python eval/evaluate.py --save --model "openai/gpt-4.1-mini" --split "answerable-full" --toolbox "data"
python eval/evaluate.py --save --model "openai/gpt-4.1-mini" --split "answerable-full" --n-shots 1
python eval/evaluate.py --save --model "openai/gpt-4.1-mini" --split "answerable-full" --n-shots 3