"""Runner class to run a tool-using loop with a language model."""

import argparse
import datetime
import gc
import json
import logging
from pathlib import Path

import litellm
import pandas as pd
from rich.logging import RichHandler

try:
    from eval.matcher import Matcher
    from eval.prompts import ALL_TOOLS, ARITHMETIC_TOOLS, BASE_PROMPT, DATA_TOOLS, TOOL_USE_BASE, create_n_shot_examples
except ImportError:  # pragma: no cover - allows `python eval/runner.py`
    from matcher import Matcher
    from prompts import ALL_TOOLS, ARITHMETIC_TOOLS, BASE_PROMPT, DATA_TOOLS, TOOL_USE_BASE, create_n_shot_examples

from frankenstein.action import FrankensteinAction
from frankenstein.utils import get_tool_metadata, parse_json_arguments, to_json_safe

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
DATASET_DIR = PROJECT_ROOT / 'dataset'
DUMPS_DIR = MODULE_DIR / 'dumps'

SINGLE_TOOL_CALL_MODELS = {
    'Llama-3.1-8B-Instruct',
    'Llama-3.1-70B-Instruct',
    'Llama-3.1-70B',
    'Llama-3.2-3B-Instruct',
}


class Runner:
    """A class to run a tool-using loop with a language model."""

    def __init__(
        self,
        model_name: str,
        toolbox: str = 'all',
        debug: bool = False,
        n_shots: int = 0,
        rerun_on_incorrect: bool = False,  # New argument
        single_tool_calls: bool = False,
    ) -> None:
        """Initialize the Runner class.

        Parameters
        ----------
        model_name : str
            The name of the model to use.
        toolbox : str
            The toolbox to use.
        debug : bool
            If True, the loop will wait for user input after each message.
        n_shots : int
            Number of n-shot examples to prepend to the prompt.
        rerun_on_incorrect : bool
            If True, prompt the model to try again after an incorrect final answer.
        single_tool_calls : bool
            If True, limit execution to one tool call per turn regardless of model output.

        """
        if model_name.startswith('openai/'):
            # Use the OpenAI API key from the environment variable
            self.api_base = None
            self.model_name = model_name
        else:
            # Use the local model
            self.api_base = 'http://0.0.0.0:8000/v1'
            self.model_name = 'hosted_vllm/' + model_name

        self.n_shots = n_shots
        self.rerun_on_incorrect = rerun_on_incorrect
        self.single_tool_calls = single_tool_calls

        if toolbox == 'arithmetic':
            self.system_prompt = BASE_PROMPT + TOOL_USE_BASE + ARITHMETIC_TOOLS
            self.tools = get_tool_metadata(toolbox='arithmetic')
        elif toolbox == 'data':
            self.system_prompt = BASE_PROMPT + TOOL_USE_BASE + DATA_TOOLS
            self.tools = get_tool_metadata(toolbox='data')
        elif toolbox == 'all':
            self.system_prompt = BASE_PROMPT + TOOL_USE_BASE + ALL_TOOLS
            self.tools = get_tool_metadata(toolbox='all')
        elif toolbox == 'none':
            self.system_prompt = BASE_PROMPT
            self.tools = {}

        # Add n-shot examples if requested
        if self.n_shots > 0:
            self.system_prompt += '\n\n' + create_n_shot_examples(self.n_shots, toolbox=toolbox)

        self.debug = debug
        self.MAX_REPEATED_TOOL_CALLS = 10
        self.tool_call_counts = {}
        self.matcher = Matcher()
        self.total_tokens = 0  # Track total tokens used in this Runner session

        if self.debug:
            # Print config
            logging.info(f"🔧 Model: '{self.model_name}'")
            logging.info(f"🔧 toolbox: '{toolbox}'")
            logging.info(f'🔧 Debug mode: {self.debug}')
            logging.info(f'🔧 N-shots: {self.n_shots}')
            # logging.info(f'🔧 System prompt: {self.system_prompt}')
            # litellm._turn_on_debug()

        else:
            litellm._logging._disable_debugging()

    def generate(
        self,
        messages: list[dict],
    ) -> object | None:
        """Generate the next model response for the current conversation state.

        Parameters
        ----------
        messages : list[dict]
            The list of messages exchanged with the model.

        Returns
        -------
        object | None
            The first choice object returned by LiteLLM, or ``None`` if request
            handling fails.

        """
        # --- Token counting and logging ---
        try:
            self.token_count = litellm.token_counter(messages=messages, model=self.model_name)
            logging.info(f'🔢 {self.token_count} tokens used')
        except Exception as e:
            logging.warning(f'⚠️  Could not count tokens: {e}')

        # Log the number of messages so far
        logging.info(f'📨 {len(messages)} messages created')

        try:
            response = litellm.completion(
                model=self.model_name,
                messages=messages,
                temperature=1,
                # top_p=0.95,
                tools=self.tools,
                tool_choice='auto',
                # tool_choice='required',
                api_base=self.api_base,
                # max_tokens=4096,
                # max_input_tokens=4096,
            )
        except litellm.exceptions.ContextWindowExceededError as e:
            logging.error(f'❌ Context window exceeded: {e}')  # noqa: TRY400
            return None
        except litellm.exceptions.BadRequestError as e:
            logging.error(f'❌ Bad request: {e}')  # noqa: TRY400
            return None
        except litellm.exceptions.RateLimitError as e:
            logging.error(f'❌ Rate limit exceeded: {e}')  # noqa: TRY400
            # Fully exit the evalation loop on rate limit errors to avoid partial results and infinite loops
            logging.exception('🛑 Stopping evaluation loop due to rate limit error.')
            raise SystemExit('Rate limit error encountered.') from e
        except litellm.exceptions.Timeout as e:
            logging.error(f'❌ Timeout error: {e}')  # noqa: TRY400
            return None

        output = response.choices[0]
        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        return output

    def loop(
        self,
        input_text: str,
        gold_answer=None,
        answer_format: str | None = None,
    ) -> tuple[list[dict], int]:
        """Run a full tool-using loop for a single input.

        Parameters
        ----------
        input_text : str
            The input text to start the loop.
        gold_answer : Any, optional
            Gold answer used when optionally rerunning after an incorrect final
            answer.
        answer_format : str | None, optional
            Answer format used by the matcher when rerunning on incorrect
            answers.

        Returns
        -------
        tuple[list[dict], int]
            Final message history and the number of tokens used in the most
            recent model call.

        """
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': input_text},
        ]

        logging.info(f'❓ {input_text!r}')

        while True:
            if self.debug:
                i = input('')
                if i.lower() == 'nodebug':
                    self.debug = False
                    litellm._logging._disable_debugging()
                    logging.info('🪲  Debug mode disabled.')
                if i.lower() == 'exit':
                    logging.info('🛑  Cancelled by user.')
                    break

            # Generate a response from the model
            output = self.generate(messages)
            if output is None:  # Caused by error
                return messages, self.token_count

            # If output is None, it indicates a malformed tool call or an error
            # if output is None:
            #     logging.error("❌   Malformed tool calls detected. Exiting.")
            #     return messages, self.token_count

            # # If output is a RateLimitError, return the messages so far
            # elif isinstance(output, litellm.exceptions.RateLimitError):
            #     return messages, self.token_count

            # Otherwise, process the output
            message = output.message

            # Format and log the model's response
            tool_calls = message.tool_calls or []
            parsed_tool_calls = []
            for tool_call in tool_calls:
                parsed_tool_calls.append(
                    {
                        'function': {
                            'name': tool_call.function.name,
                            'arguments': tool_call.function.arguments,
                        },
                        'id': tool_call.id,
                        'type': tool_call.type,
                    }
                )

            # Log the assistant message content
            logging.info(f'💬 {message.content}')

            # Only include 'tool_calls' if not empty
            assistant_message = {
                'role': message.role,
                'content': message.content,
            }

            # Only include one tool call for single-tool-call models
            single_tool_call_model = self.model_name in SINGLE_TOOL_CALL_MODELS or self.single_tool_calls
            if parsed_tool_calls:
                if single_tool_call_model:
                    assistant_message['tool_calls'] = [parsed_tool_calls[0]]
                else:
                    assistant_message['tool_calls'] = parsed_tool_calls

            messages.append(assistant_message)

            # Filter tool calls for single-tool-call models
            tool_calls_to_execute = parsed_tool_calls
            single_tool_call_model = self.model_name in SINGLE_TOOL_CALL_MODELS or self.single_tool_calls
            if single_tool_call_model:
                tool_calls_to_execute = [parsed_tool_calls[0]] if parsed_tool_calls else []

            # Execute each tool call
            for tool_call in tool_calls_to_execute:
                name = tool_call['function']['name']
                arguments = tool_call['function']['arguments']
                try:
                    parsed_args = json.loads(arguments)
                except json.JSONDecodeError:
                    logging.exception('❌ Could not parse tool call arguments.')
                    return messages, self.token_count

                # Format and log the function call
                args_string = ', '.join([f'{k}={v!r}' for k, v in parsed_args.items()])
                logging.info(f'🔨 {name}({args_string})')

                # Update the tool call counts
                key = (name, json.dumps(parsed_args, sort_keys=True))
                self.tool_call_counts[key] = self.tool_call_counts.get(key, 0) + 1

                # Execute the function call
                try:
                    result = FrankensteinAction(action=name, **parsed_args).execute(error_handling='raise')
                    logging.info(f'↪️  {result!r}')

                except Exception as e:
                    result = e
                    # Check if first word of message is "Warning" or "Error" and log accordingly
                    if str(result).startswith('Warning'):
                        logging.warning(f'⚠️  {result}')
                    elif str(result).startswith('Error'):
                        logging.error(f'❌ {result}')  # noqa: TRY400

                messages.append(
                    {
                        'role': 'tool',
                        'tool_call_id': tool_call.get('id'),
                        'content': str(result),
                    }
                )

                # After first tool call, add user message if single-tool-call model
                if single_tool_call_model:
                    messages.append(
                        {
                            'role': 'user',
                            'content': 'Note: Only the first tool call was executed because this model only supports single tool calls at a time. Please only call one tool per turn.',
                        }
                    )
                    break

            # After each tool call, check total tool calls limit
            total_tool_calls = sum(self.tool_call_counts.values())
            if total_tool_calls >= 100:
                logging.warning('🛑 Stopping: total number of tool calls reached the limit of 100.')
                return messages, self.token_count

            # Also stop after 100 messages to prevent infinite loops
            if len(messages) >= 100:
                logging.warning('🛑 Stopping: total number of messages reached the limit of 100.')
                return messages, self.token_count

            if self.token_count >= 128000:
                logging.warning('🛑 Stopping: token count exceeded 128,000.')
                return messages, self.token_count

            # # Or, stop if the last 5 messages do not contain tool calls
            # last_five_messages = [msg for msg in messages[-5:] if msg['role'] == 'assistant']
            # if all('tool_calls' not in msg or not msg['tool_calls'] for msg in last_five_messages):
            #     logging.warning('🛑 Stopping: last 5 messages do not contain tool calls.')
            #     return messages, self.token_count

            # --- Folded stop condition here ---
            # Stop if 'final_answer' tool has been called once
            final_answer_found = False
            for (tool, args_json), count in self.tool_call_counts.items():
                if tool == 'final_answer' and count == 1:
                    logging.info('🏁 Final answer tool called.')
                    final_answer_found = True
                    break

            if final_answer_found:
                # Run matcher if gold_answer is provided
                if gold_answer is not None:
                    match_result = (
                        self.matcher.match_results(messages, gold_answer, answer_format)
                        if hasattr(self, 'matcher')
                        else (None, None)
                    )
                    if match_result is None or match_result[0] is None:
                        logging.warning('⚠️  No match result available.')
                        return messages, self.token_count
                    is_correct, _ = match_result
                    if not is_correct and self.rerun_on_incorrect:
                        # Append a user message and continue the loop
                        messages.append(
                            {
                                'role': 'user',
                                'content': 'Your answer was incorrect. Re-think your approach and try again.',
                            }
                        )
                        # Reset only the final_answer tool call count so the loop can continue
                        # (or optionally reset all tool_call_counts)
                        for key in list(self.tool_call_counts.keys()):
                            if key[0] == 'final_answer':
                                del self.tool_call_counts[key]
                        continue
                return messages, self.token_count

            # Check repeated tool calls (already counted in self.tool_call_counts)
            for (tool, args_json), count in self.tool_call_counts.items():
                if count >= self.MAX_REPEATED_TOOL_CALLS:
                    logging.warning(
                        f'🛑 Tool "{tool}" called {self.MAX_REPEATED_TOOL_CALLS} times with same arguments: {args_json}'
                    )
                    return messages, self.token_count

            # Optionally run garbage collection to free memory
            gc.collect()

        return messages, self.token_count

    def format_messages(
        self,
        messages: list[dict],
    ) -> str:
        """Clean and parse messages for saving to disk.

        Parameters
        ----------
        messages : list[dict]
            The list of messages to clean and parse.

        Returns
        -------
        str
            A JSON-safe string representation of the cleaned messages.

        """
        parsed_messages = parse_json_arguments(messages)
        return to_json_safe(parsed_messages)

    def match_results(
        self,
        messages: list[dict],
        gold_answer,
        answer_format: str | None = None,
    ) -> tuple[bool | None, float | None]:
        """Extract the final answer from messages and compare it to the gold answer.

        Parameters
        ----------
        messages : list[dict]
            Message history produced by the runner.
        gold_answer : Any
            Gold reference answer.
        answer_format : str | None, optional
            Answer format to pass to the matcher.

        Returns
        -------
        tuple[bool | None, float | None]
            Pair of correctness flag and error magnitude. If no final answer is
            found, both values are ``None``.

        """
        final_answer = None
        for message in messages:
            if message.get('role') == 'assistant' and message.get('tool_calls'):
                for tool_call in message['tool_calls']:
                    if tool_call.get('function', {}).get('name') == 'final_answer':
                        parsed_args = json.loads(tool_call['function']['arguments'])
                        final_answer = parsed_args.get('answer')
                        break
            if final_answer is not None:
                break
        if final_answer is not None:
            return self.matcher.match(final_answer, gold_answer, answer_format)
        else:
            logging.warning('⚠️  No final answer found in the messages.')
            return None, None

    def reset(self) -> None:
        """Reset stateful runner variables before a new evaluation.

        """
        self.tool_call_counts = {}
        self.total_tokens = 0  # Reset token counter
        # Add any other stateful variables that should be reset here


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a tool-using loop with a language model.')
    parser.add_argument(
        '--model-name',
        type=str,
        default='openai/gpt-4o-mini',
        help='The name of the model to use.',
    )
    parser.add_argument(
        '--toolbox',
        type=str,
        default='all',
        choices=['arithmetic', 'data', 'all'],
        help='The toolbox to use.',
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='If set, the loop will wait for user input after each message.',
    )
    parser.add_argument(
        '--n-shots',
        type=int,
        default=0,
        help='Number of n-shot tool call examples to prepend to the prompt.',
    )
    parser.add_argument(
        '--save',
        action='store_true',
        help='When running runner.py with --save, messages will be saved to eval/dumps/.',
    )
    parser.add_argument(
        '--rerun-on-incorrect',
        action='store_true',
        help='If set, rerun the loop with a message if the final answer is incorrect.',
    )
    parser.add_argument(
        '--single-tool-calls',
        action='store_true',
        help='If set, limit execution to one tool call per turn regardless of model output.',
    )

    args = parser.parse_args()

    logging.basicConfig(
        level='NOTSET',
        format='%(message)s',
        datefmt='[%X]',
        handlers=[RichHandler()],
    )

    runner = Runner(
        model_name=args.model_name,
        toolbox=args.toolbox,
        debug=args.debug,
        n_shots=args.n_shots,
        rerun_on_incorrect=args.rerun_on_incorrect,
        single_tool_calls=args.single_tool_calls,
    )

    file = DATASET_DIR / 'answerable-full.jsonl'
    with file.open('r') as f:
        dataset = pd.read_json(f, lines=True)
    dataset = dataset.sample(1)

    messages = runner.loop(
        dataset['question'].to_list()[0],
        gold_answer=dataset['answer'].to_list()[0] if 'answer' in dataset.columns else None,
        answer_format=dataset['answer_format'].to_list()[0] if 'answer_format' in dataset.columns else None,
    )

    # Example: match results if gold answer and format are present
    gold_answer = dataset['answer'].to_list()[0] if 'answer' in dataset.columns else None
    answer_format = dataset['answer_format'].to_list()[0] if 'answer_format' in dataset.columns else None
    if 'metadata' in dataset.columns and isinstance(dataset.iloc[0]['metadata'], dict):
        answer_format = dataset.iloc[0]['metadata'].get('answer_format')
    if gold_answer is not None:
        runner.match_results(messages, gold_answer, answer_format)

    if args.save:
        timestamp = datetime.datetime.now()
        output_path = (DUMPS_DIR / f'{timestamp}').with_suffix('.json')
        output_path.parent.mkdir(parents=True, exist_ok=True)
        parsed_messages = parse_json_arguments(messages)
        with output_path.open('w', encoding='utf-8') as f:
            f.write(json.dumps(to_json_safe(parsed_messages), indent=2) + '\n')
        logging.info(f"💾 Saved messages to '{output_path}'")
