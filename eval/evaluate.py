"""Evaluation entry point for running models on Frankenstein dataset splits."""

import argparse
import logging
import re
from pathlib import Path

import openai
import pandas as pd
import requests
from rich.logging import RichHandler

try:
    from eval.runner import Runner
except ImportError:  # pragma: no cover - allows `python eval/evaluate.py`
    from runner import Runner

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
DATASET_DIR = PROJECT_ROOT / 'dataset'
RUNS_DIR = MODULE_DIR / 'runs'
REPEATS_DIR = RUNS_DIR / 'repeats'

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    datefmt='[%X]',
    handlers=[
        RichHandler(
            tracebacks_suppress=[openai],
            markup=True,
        )
    ],
)


class FrankensteinEvaluator:
    """Evaluate the performance of a transformer model on a split/portion/template of the dataset."""

    def __init__(
        self,
        model_name: str,
        toolbox: str = 'all',
        save: bool = False,
        num_samples: int = -1,
        split: str = 'answerable-full',
        n_shots: int = 0,
        debug: bool = False,
        repeats: int = 1,
        single_tool_calls: bool = False,
    ):
        """Initialize the evaluator.

        Parameters
        ----------
        model_name : str
            Path or name of the transformer model.
        toolbox : str
            Toolbox to use for the evaluation. Can be 'all', 'arithmetic', 'data', or 'none'.
        save : bool
            Whether to save the evaluation results.
        num_samples : int
            Number of samples to evaluate.
        split : str
            Dataset split to use.
        n_shots : int
            Number of n-shot tool call examples to prepend to the prompt.
        debug : bool
            Whether to pause after each message during an evaluation run.
        repeats : int
            Number of repeated runs to execute for the same configuration.
        single_tool_calls : bool
            If True, limit execution to one tool call per turn regardless of model output.

        """
        self.model_name = model_name
        self.toolbox = toolbox
        self.save = save
        self.num_samples = num_samples
        self.split = split
        self.n_shots = n_shots
        self.debug = debug
        self.repeats = repeats
        self.single_tool_calls = single_tool_calls

        # Load dataset from dataset/{split}.jsonl or .json
        dataset_path = DATASET_DIR / f'{self.split}.jsonl'
        self.dataset = pd.read_json(dataset_path, orient='records', lines=True, precise_float=True)
        if self.num_samples != -1:
            self.dataset = self.dataset.sample(self.num_samples)
        logging.info(f'Loaded dataset from {dataset_path} with {len(self.dataset)} samples.')

        self.log_config(vars(self))

    def run(
        self,
        repeats: int | None = None,
    ) -> list:
        """Evaluate the model on the dataset (optionally multiple times).

        Parameters
        ----------
        repeats : int | None
            Number of repeated full evaluation runs. If None, uses self.repeats.

        Returns
        -------
        list
            If ``repeats == 1``, returns the saved message sequences for each
            sample. If ``repeats > 1``, returns one such list per repeat.

        """
        repeats = repeats if repeats is not None else self.repeats
        all_repeat_messages: list[list] = []

        model_name = str(self.model_name).split('/')[-1]
        # Determine existing completed/partial repeat runs (only for repeats > 1)
        completed_repeat_indices = set()
        partial_repeat_indices = set()
        if repeats > 1:
            repeats_dir = REPEATS_DIR
            if repeats_dir.exists():
                pattern = f'{model_name}_repeat-*_{self.split}_{self.toolbox}-tools_{self.n_shots}-shot.jsonl'
                for path in repeats_dir.glob(pattern):
                    m = re.search(r'repeat-(\d+)', path.name)
                    if not m:
                        continue
                    ridx = int(m.group(1))
                    try:
                        prev_df = pd.read_json(path, orient='records', lines=True, precise_float=True)
                        # Determine if full: dataset length match and all ids present
                        if len(prev_df) == len(self.dataset):
                            # naive id completeness check
                            if 'id' in prev_df.columns and 'id' in self.dataset.columns:
                                if set(prev_df['id']) == set(self.dataset['id']):
                                    completed_repeat_indices.add(ridx)
                                else:
                                    partial_repeat_indices.add(ridx)
                            else:
                                completed_repeat_indices.add(ridx)
                        else:
                            partial_repeat_indices.add(ridx)
                    except Exception:
                        partial_repeat_indices.add(ridx)

        # Build loop indices: include partial to resume, skip fully completed, then remaining new ones
        repeat_indices = []
        for i in range(1, repeats + 1):
            if i in completed_repeat_indices:
                repeat_indices.append(i)  # We'll load messages directly without rerun
            elif i in partial_repeat_indices or i not in completed_repeat_indices:
                repeat_indices.append(i)

        for repeat_idx in repeat_indices:
            repeat_tag = f'repeat-{repeat_idx}' if repeats > 1 else None
            # Decide output path
            if repeats > 1:
                output_dir = REPEATS_DIR
                output_filename = f'{model_name}_{repeat_tag}_{self.split}_{self.toolbox}-tools_{self.n_shots}-shot.jsonl'
            else:
                output_dir = RUNS_DIR
                output_filename = f'{model_name}_{self.split}_{self.toolbox}-tools_{self.n_shots}-shot.jsonl'
            output_path = output_dir / output_filename

            if repeats > 1 and repeat_idx in completed_repeat_indices:
                logging.info(f'⏩ Skipping repeat {repeat_idx} (already complete).')
                try:
                    prev_df = pd.read_json(output_path, orient='records', lines=True, precise_float=True)
                    all_repeat_messages.append(prev_df['messages'].tolist())
                except Exception as e:
                    logging.warning(f'Failed to load completed repeat {repeat_idx}: {e}; will attempt rerun.')
                continue

            logging.info(
                f'🚀 Starting evaluation run {repeat_idx}/{repeats} -> output: {output_path}'
                if repeats > 1
                else f'🚀 Starting evaluation run -> output: {output_path}'
            )

            results = []
            runner = Runner(
                model_name=self.model_name,
                toolbox=self.toolbox,
                n_shots=self.n_shots,
                debug=self.debug,
                single_tool_calls=self.single_tool_calls,
            )

            # Resume logic per repeat
            completed_ids = set()
            if output_path.exists():
                try:
                    prev_results_df = pd.read_json(output_path, orient='records', lines=True, precise_float=True)
                    results = prev_results_df.to_dict(orient='records')
                    if 'id' in prev_results_df.columns:
                        completed_ids = set(prev_results_df['id'])
                    else:
                        completed_ids = set(prev_results_df['question'])
                    logging.info(f'Resuming {repeat_tag or "run"}: {len(completed_ids)} questions already processed.')
                except Exception as e:
                    logging.warning(f'Could not load previous results for resuming ({repeat_tag or "run"}): {e}')

            for idx, (_, row) in enumerate(self.dataset.iterrows()):
                row_id = row['id'] if 'id' in row else row['question']
                if row_id in completed_ids:
                    continue

                runner.reset()

                logging.info(f"✨ [{repeat_tag or 'run'}] Processing question {idx + 1}/{len(self.dataset)} of '{output_path}'")
                logging.info('🔎 Question Metadata')
                self.log_question_info(row)

                messages, tokens_used = runner.loop(row['question'])
                gold_answer = row['answer']
                answer_format = row['answer_format']

                correct, error = runner.match_results(messages, gold_answer, answer_format)
                pred = runner.matcher.extract_final_answer(messages)

                result_row = row.to_dict()
                result_row.update(
                    {
                        'repeat': repeat_idx if repeats > 1 else 1,
                        'messages': runner.format_messages(messages),
                        'tokens': tokens_used,
                        'pred': pred,
                        'correct': correct if correct is not None else False,
                        'error': error,
                    }
                )
                results.append(result_row)
                completed_ids.add(row_id)

                if self.save:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    pd.DataFrame(results).to_json(output_path, orient='records', lines=True)

            results_df = pd.DataFrame(results)
            if self.save:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                results_df.to_json(output_path, orient='records', lines=True)
                logging.info(
                    f'✅ Saved evaluation results for {repeat_tag or "run"} to {output_path}'
                    if repeats > 1
                    else f'✅ Saved evaluation results to {output_path}'
                )

            all_repeat_messages.append(results_df['messages'].tolist())

        # Return shape based on repeats for backward compatibility
        return all_repeat_messages[0] if repeats == 1 else all_repeat_messages

    def log_config(
        self,
        config: dict,
    ) -> None:
        """Log the configuration in a formatted way.

        Parameters
        ----------
        config : dict
            Configuration dictionary to log.

        """
        key_width = max(len(str(k)) for k in config)
        logging.info('Model Config')
        for k, v in config.items():
            if k == 'dataset':
                continue
            arrow = '-' * (key_width + 1 - len(str(k))) + '>'
            logging.info(f"⚙️ '{k}' {arrow} {v!r}")

    def log_question_info(
        self,
        row: pd.Series,
    ) -> None:
        """Log metadata in a formatted table.

        Parameters
        ----------
        row : pd.Series
            Dataset row containing question metadata and slot values.

        """
        keys = ['question_template', 'slot_values', 'answerable', 'answer_format', 'data_availability']
        key_width = max(len(str(k)) for k in keys)
        for k in keys:
            if k == 'slot_values':
                for sk, sv in row.get(k, {}).items():
                    # Arrow line replaces padding: key + ('-' * (key_width - len(key))) + '>'
                    arrow = '-' * (key_width + 1 - len(str(sk))) + '>'
                    logging.info(f"🔑 '{sk}' {arrow} {sv!r}")
            else:
                v = row.get(k)
                # Arrow line replaces padding: key + ('-' * (key_width - len(key))) + '>'
                arrow = '-' * (key_width + 1 - len(str(k))) + '>'
                logging.info(f"🔑 '{k}' {arrow} {v!r}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Evaluate a transformer model.')
    parser.add_argument(
        '--model-name',
        '--model',
        type=str,
        dest='model_name',
        default='Llama-3.1-8B-Instruct',
        help='Path or name of the transformer model.',
    )
    parser.add_argument(
        '--split',
        type=str,
        default='answerable-full',
        help='Dataset split to use (e.g., "answerable-full", "unanswerable-partial", etc.).',
    )
    parser.add_argument(
        '--num-samples',
        type=int,
        default=-1,
        help='Number of samples to evaluate. Use -1 for all samples.',
    )
    parser.add_argument(
        '--toolbox',
        type=str,
        choices=['all', 'arithmetic', 'data', 'none'],
        default='all',
        help='Toolbox to use for the evaluation. Can be "all", "arithmetic", "data", or "none".',
    )
    parser.add_argument(
        '--save',
        action='store_true',
        help='Whether to save the evaluation results.',
    )
    parser.add_argument(
        '--n-shots',
        type=int,
        default=0,
        help='Number of n-shot tool call examples to prepend to the prompt.',
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='If set, the loop will wait for user input after each message.',
    )
    parser.add_argument(
        '--repeats',
        type=int,
        default=1,
        help='Number of repeated evaluation runs to perform.',
    )
    parser.add_argument(
        '--single-tool-calls',
        action='store_true',
        help='If set, limit execution to one tool call per turn regardless of model output.',
    )
    parser.add_argument(
        '--slack-webhook',
        type=str,
        default='',
        help='Slack incoming webhook URL to post a completion message.',
    )
    parser.add_argument(
        '--slack-message',
        type=str,
        default='',
        help='Optional Slack completion message. Defaults to a generic completion notice.',
    )
    args = parser.parse_args()

    # Post start message to Slack if webhook provided
    if args.slack_webhook:
        model_short = str(args.model_name).split('/')[-1]
        start_msg = 'Starting Frankenstein evaluation.\n'
        for a in args.__dict__:
            if a == 'slack_webhook' or a == 'slack_message':
                continue
            v = args.__dict__[a]
            if a == 'model_name':
                v = str(v).split('/')[-1]
            start_msg += f'`--{a}` {v}\n'

        payload = {"text": start_msg}

        try:
            r = requests.post(args.slack_webhook, json=payload, timeout=10)
            if r.status_code >= 300:
                logging.warning(f'Failed to send Slack start message: HTTP {r.status_code} - {r.text}')
            else:
                logging.info('📣 Sent start message to Slack.')
        except Exception as e:
            logging.warning(f'Could not send Slack start message: {e}')

    evaluator = FrankensteinEvaluator(
        model_name=args.model_name,
        toolbox=args.toolbox,
        save=args.save,
        num_samples=args.num_samples,
        split=args.split,
        n_shots=args.n_shots,
        debug=args.debug,
        repeats=args.repeats,
        single_tool_calls=args.single_tool_calls,
    )
    evaluator.args = args  # Attach args for logging
    result = evaluator.run(repeats=args.repeats)

    # NEW: Post completion message to Slack if webhook provided
    if args.slack_webhook:
        try:
            total_samples = len(evaluator.dataset)
            model_name = str(args.model_name).split('/')[-1]
            msg = args.slack_message or f'Evaluation complete for {model_name} on {total_samples} samples.'
            payload = {"text": msg}
            r = requests.post(args.slack_webhook, json=payload, timeout=10)
            if r.status_code >= 300:
                logging.warning(f'Failed to send Slack message: HTTP {r.status_code} - {r.text}')
            else:
                logging.info('📣 Sent completion message to Slack.')
        except Exception as e:
            logging.warning(f'Could not send Slack message: {e}')
