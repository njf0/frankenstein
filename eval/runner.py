"""Runner class to run a tool-using loop with a language model."""

import json
import logging

import litellm
from rich.logging import RichHandler

from eval.prompts import ALL_TOOLS, ARITHMETIC_TOOLS, BASE_PROMPT, DATA_TOOLS, TOOL_USE_BASE
from franklin.action import FranklinAction
from franklin.utils import get_tool_metadata


class Runner:
    """A class to run a tool-using loop with a language model."""

    def __init__(
        self,
        model_name: str,
        toolset: str = 'all',
        debug: bool = False,
    ) -> None:
        """Initialize the Runner class.

        Parameters
        ----------
        model_name : str
            The name of the model to use.
        tools : list[dict] | None
            A list of tools to use. If None, the default tools will be used.
        debug : bool
            If True, the loop will wait for user input after each message.

        """
        self.model_name = model_name

        if toolset == 'arithmetic':
            self.system_prompt = BASE_PROMPT + TOOL_USE_BASE + ARITHMETIC_TOOLS
            self.tools = get_tool_metadata(toolset='arithmetic')
        elif toolset == 'data':
            self.system_prompt = BASE_PROMPT + TOOL_USE_BASE + DATA_TOOLS
            self.tools = get_tool_metadata(toolset='data')
        elif toolset == 'all':
            self.system_prompt = BASE_PROMPT + TOOL_USE_BASE + ALL_TOOLS
            self.tools = get_tool_metadata(toolset='all')

        self.debug = debug
        self.MAX_REPEATED_TOOL_CALLS = 10
        self.tool_call_counts = {}

        litellm._logging._disable_debugging()

    def _should_stop(
        self,
        messages: list[dict],
        finish_reason: str | None = None,
    ) -> bool:
        """Check if the loop should stop based on conditions.

        Parameters
        ----------
        messages : list[dict]
            The list of messages exchanged with the model.
        finish_reason : str | None
            Optional finish reason returned by the model.

        Returns
        -------
        bool
            True if stopping condition is met, False otherwise.

        """
        if finish_reason == 'stop':
            # log message content before stopping
            logging.info(f'💬 {messages[-1].get("content")}')
            logging.info('🛑 Model indicated a stop condition.')
            return True

        for message in messages:
            tool_calls = message.get('tool_calls', [])
            for tool_call in tool_calls:
                if tool_call.get('function', {}).get('name') == 'final_answer':
                    # Log a final answer function call as below
                    parsed_args = json.loads(tool_call['function']['arguments'])
                    name = tool_call['function']['name']
                    args_string = ', '.join([f"{k} = '{v}'" for k, v in parsed_args.items()])
                    logging.info(f'🔧 {name}({args_string})')
                    logging.info('🏁 Final answer tool called.')
                    return True

        # Check repeated tool calls (already counted in self.tool_call_counts)
        for (tool, args_json), count in self.tool_call_counts.items():
            if count >= self.MAX_REPEATED_TOOL_CALLS:
                logging.warning(f'🛑 Tool "{tool}" called 10 times with same arguments: {args_json}')
                return True

        return False

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
        )
        message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        return message, finish_reason

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

        if self.debug:
            # Log the system prompt
            logging.info(f'🧑‍💻 SYSTEM PROMPT: {self.system_prompt}')
            # Log the user input
            logging.info(f'🧑‍💻 USER PROMPT: {input_text}')

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

            message, finish_reason = self.generate(messages)

            messages.append(
                {
                    'role': message.role,
                    'content': message.content,
                    'tool_calls': message.tool_calls,
                }
            )
            logging.info(f'💬 {message.content}')

            # Check stopping conditions
            if self._should_stop(messages, finish_reason=finish_reason):
                break

            for tool_call in message.tool_calls:
                # Parse the function call
                name = tool_call.function.name
                arguments = tool_call.function.arguments
                parsed_args = json.loads(arguments)

                # Format and log the function call
                args_string = ', '.join([f"{k} = '{v}'" for k, v in parsed_args.items()])
                logging.info(f'🔧 {name}({args_string})')

                # Update the tool call counts
                key = (name, json.dumps(parsed_args, sort_keys=True))
                self.tool_call_counts[key] = self.tool_call_counts.get(key, 0) + 1

                # Execute the function call
                try:
                    result = FranklinAction(action=name, **parsed_args).execute(error_handling='raise')
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
                        'tool_call_id': tool_call.id,
                        'content': str(result),
                    }
                )

        return messages


if __name__ == '__main__':
    FORMAT = '%(message)s'
    logging.basicConfig(level='NOTSET', format=FORMAT, datefmt='[%X]', handlers=[RichHandler()])

    runner = Runner(
        model_name='openai/gpt-4o-mini',
        toolset='all',
        debug=True,
    )

    runner.loop(
        'Which country in Eastern Europe had the highest increase in proportion of GDP represented by tax revenue between 2007 and 2013?'
    )
