"""Runner class to run a tool-using loop with a language model."""

import argparse
import datetime
import json
import logging
import random
from pathlib import Path

import litellm
import pandas as pd
from rich.logging import RichHandler

from eval.prompts import ALL_TOOLS, ARITHMETIC_TOOLS, BASE_PROMPT, DATA_TOOLS, TOOL_USE_BASE, create_n_shot_examples
from frankenstein.action import FrankensteinAction
from frankenstein.utils import get_tool_metadata, parse_json_arguments, to_json_safe

SINGLE_TOOL_CALL_MODELS = {
    'Llama-3.1',
    'Llama-3.2',
}


class Runner:
    """A class to run a tool-using loop with a language model."""

    def __init__(
        self,
        model_name: str,
        toolset: str = 'all',
        debug: bool = False,
        n_shots: int = 0,
    ) -> None:
        """Initialize the Runner class.

        Parameters
        ----------
        model_name : str
            The name of the model to use.
        toolset : str
            The toolset to use.
        debug : bool
            If True, the loop will wait for user input after each message.
        n_shots : int
            Number of n-shot examples to prepend to the prompt.

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

        if toolset == 'arithmetic':
            self.system_prompt = BASE_PROMPT + TOOL_USE_BASE + ARITHMETIC_TOOLS
            self.tools = get_tool_metadata(toolset='arithmetic')
        elif toolset == 'data':
            self.system_prompt = BASE_PROMPT + TOOL_USE_BASE + DATA_TOOLS
            self.tools = get_tool_metadata(toolset='data')
        elif toolset == 'all':
            self.system_prompt = BASE_PROMPT + TOOL_USE_BASE + ALL_TOOLS
            self.tools = get_tool_metadata(toolset='all')

        # Add n-shot examples if requested
        if self.n_shots > 0:
            self.system_prompt += '\n\n' + create_n_shot_examples(self.n_shots, toolset=toolset)

        self.debug = debug
        self.MAX_REPEATED_TOOL_CALLS = 10
        self.tool_call_counts = {}

        if self.debug:
            # Print config
            logging.info(f"🔧 Model: '{self.model_name}'")
            logging.info(f"🔧 Toolset: '{toolset}'")
            logging.info(f'🔧 Debug mode: {self.debug}')
            logging.info(f'🔧 N-shots: {self.n_shots}')
            # logging.info(f'🔧 System prompt: {self.system_prompt}')
            # litellm._turn_on_debug()

        else:
            litellm._logging._disable_debugging()

    def generate(
        self,
        messages: list[dict],
    ) -> tuple[dict, str]:
        """Generate a response from the model and return both message and finish_reason.

        Parameters
        ----------
        messages : list[dict]
            The list of messages exchanged with the model.

        Returns
        -------
        tuple[dict, str]
            The generated message and the finish reason.

        """
        response = litellm.completion(
            model=self.model_name,
            messages=messages,
            tools=self.tools,
            api_base=self.api_base,
        )
        output = response.choices[0]
        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        return output

    def loop(
        self,
        input_text: str,
    ) -> list[dict]:
        """Run a full tool-using loop for a single input.

        Parameters
        ----------
        input_text : str
            The input text to start the loop.

        Returns
        -------
        list[dict]
            The list of messages exchanged with the model.

        """
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': input_text},
        ]

        logging.info(f'❓ {input_text}')

        while True:
            if self.debug:
                i = input('')
                if i.lower() == 'nodebug':
                    self.debug = False
                    logging.info('🪲  Debug mode disabled.')
                if i.lower() == 'exit':
                    logging.info('🛑  Cancelled by user.')
                    break

            # Generate a response from the model
            output = self.generate(messages)
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

            messages.append(
                {
                    'role': message.role,
                    'content': message.content,
                    'tool_calls': parsed_tool_calls,
                }
            )

            # Execute each tool call
            for tool_call in parsed_tool_calls:
                name = tool_call['function']['name']
                arguments = tool_call['function']['arguments']
                parsed_args = json.loads(arguments)

                # Format and log the function call
                args_string = ', '.join([f"{k} = '{v}'" for k, v in parsed_args.items()])
                logging.info(f'🔨 {name}({args_string})')

                # Update the tool call counts
                key = (name, json.dumps(parsed_args, sort_keys=True))
                self.tool_call_counts[key] = self.tool_call_counts.get(key, 0) + 1

                # Execute the function call
                try:
                    result = FrankensteinAction(action=name, **parsed_args).execute(error_handling='raise')
                    logging.info(f'↪️  {result}')

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

            # --- Folded stop condition here ---
            # Stop if 'final_answer' tool has been called once
            for (tool, args_json), count in self.tool_call_counts.items():
                if tool == 'final_answer' and count == 1:
                    logging.info('🏁 Final answer tool called.')
                    return messages

            # Check repeated tool calls (already counted in self.tool_call_counts)
            for (tool, args_json), count in self.tool_call_counts.items():
                if count >= self.MAX_REPEATED_TOOL_CALLS:
                    logging.warning(f'🛑 Tool "{tool}" called 10 times with same arguments: {args_json}')
                    return messages

        return messages

    def clean_messages(
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


if __name__ == '__main__':
    # vLLM serve commands
    # vllm serve --model "public/hf/models/meta-llama/Meta-Llama-3.1-8B-Instruct" --serve-model-name "Llama-3.1-8B-Instruct"
    # vllm serve --model "public/hf/models/Qwen/Qwen3-4B" --serve-model-name "Qwen3-4B"

    parser = argparse.ArgumentParser(description='Run a tool-using loop with a language model.')
    parser.add_argument(
        '--model_name',
        type=str,
        default='openai/gpt-4o-mini',
        help='The name of the model to use.',
    )
    parser.add_argument(
        '--toolset',
        type=str,
        default='all',
        choices=['arithmetic', 'data', 'all'],
        help='The toolset to use.',
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='If set, the loop will wait for user input after each message.',
    )
    parser.add_argument(
        '--n_shots',
        type=int,
        default=0,
        help='Number of n-shot tool call examples to prepend to the prompt.',
    )
    parser.add_argument(
        '--save',
        action='store_true',
        help='When running runner.py with --save, messages will be saves to eval/dumps/',
    )

    args = parser.parse_args()

    FORMAT = '%(message)s'
    logging.basicConfig(level='NOTSET', format=FORMAT, datefmt='[%X]', handlers=[RichHandler()])

    runner = Runner(
        model_name=args.model_name,
        toolset=args.toolset,
        debug=args.debug,
        n_shots=args.n_shots,
    )

    variants = Path('dataset', 'answerable_full').iterdir()
    variant = random.choice(list(variants))
    with variant.open('r') as f:
        dataset = pd.read_json(f, lines=True)
    dataset = dataset.sample(1)

    messages = runner.loop(dataset['question'].to_list()[0])

    # --- Added: Check and log correctness of the model-generated answer ---
    # Try to extract the expected answer from the dataset
    expected_answer = dataset['answer'].to_list()[0] if 'answer' in dataset.columns else None

    # Find the content of the 'final_answer' tool call in the messages
    final_answer = None
    for message in messages:
        if message.get('role') == 'assistant' and message.get('tool_calls'):
            for tool_call in message['tool_calls']:
                if tool_call.get('function', {}).get('name') == 'final_answer':
                    # Parse the function call arguments to get the final answer
                    parsed_args = json.loads(tool_call['function']['arguments'])
                    final_answer = parsed_args.get('answer')
                    break

    # Log the final answer and compare it with the expected answer
    if final_answer is not None:
        logging.info(f'Final answer: {final_answer}')
        if expected_answer is not None:
            logging.info(f'Expected answer: {expected_answer}')
            if str(final_answer) == str(expected_answer) or str(expected_answer) in str(final_answer):
                logging.info('✅ Final answer matches the expected answer.')
            else:
                logging.warning('❌ Final answer does not match the expected answer.')
    else:
        logging.warning('⚠️  No final answer found in the messages.')

    if args.save:
        timestamp = datetime.datetime.now()
        output_path = Path('eval', 'dumps', f'{timestamp}').with_suffix('.json')
        cleaned = runner.clean_messages(messages)
        with output_path.open('w') as f:
            f.write(json.dumps(cleaned, indent=2) + '\n')

        logging.info(f"💾 Saved messages to '{output_path}'")
