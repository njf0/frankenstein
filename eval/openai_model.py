import json
import logging
from copy import deepcopy

from frankenstein.action import FrankensteinAction
from frankenstein.model import ToolCalls
from openai import OpenAI
from rich.logging import RichHandler

from eval.prompts import BASE_PROMPT, FULL_TOOL_USE, SIMULATE_TOOL_USE


class OpenAIModel:
    def __init__(
        self,
        model_name: str,
        use_tools: str = 'none',
        debug: bool = False,
    ) -> None:
        """Initialize the OpenAI model with the given parameters."""
        self.model_name = model_name

        self.client = OpenAI()

        if use_tools == 'full':
            self.system_prompt = BASE_PROMPT + FULL_TOOL_USE
        elif use_tools == 'simulate':
            self.system_prompt = BASE_PROMPT + SIMULATE_TOOL_USE
        else:
            self.system_prompt = BASE_PROMPT

        self.use_tools = use_tools
        self.debug = debug

        # Use OpenAIFinalOutput for OpenAI structured outputs
        # self.json_schema = OpenAIOutput.model_json_schema()

    def _has_final_answer(
        self,
        messages: list[dict],
    ) -> bool:
        """Check if the final answer has been provided in the messages."""
        for message in messages:
            if (message.get('role') == 'tool' and message.get('name') == 'final_answer') or (
                message.get('role') == 'assistant' and messages.count(message) > 10
            ):
                return True

    def process_tool_call(
        self,
        tool_call: dict,
    ) -> dict:
        """Process a tool call and return the result."""
        name = tool_call.get('name')
        args = tool_call.get('arguments', {})
        return FrankensteinAction(name, **args).execute(error_handling='raise')

    def generate(
        self,
        messages: list[dict],
    ) -> str:
        """Generate a response from the OpenAI model using Structured Outputs."""
        response = self.client.responses.parse(
            model=self.model_name,
            input=messages,
            text_format=ToolCalls,
        )
        return response.output_parsed.tool_calls

    def loop(
        self,
        input_text: str,
    ) -> list[dict]:
        """Run a full tool-using loop for a single input."""
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': input_text},
        ]
        tool_call_history = []  # <-- Track tool calls here
        logging.info(f'❓ {input_text}')

        while not self._has_final_answer(messages):
            if self.debug:
                i = input('')
                if i.lower() != '':
                    break

            messages_copy = deepcopy(messages)
            try:
                tool_calls = self.generate(messages_copy)

            except Exception as e:
                print(tool_calls)
                messages.append(
                    {
                        'role': 'user',
                        'content': f'Error processing structured output: {e!s}',
                    }
                )
                logging.error(messages[-1]['content'])  # noqa: TRY400
                continue

            if not tool_calls:
                messages.append(
                    {
                        'role': 'user',
                        'content': 'No tool calls found.',
                    }
                )
                logging.error(messages[-1]['content'])
                continue

            # Only add allowed fields to messages
            messages.append({'role': 'assistant', 'content': json.dumps([call.model_dump() for call in tool_calls], indent=2)})
            # Loop through the tool calls and execute
            for call in tool_calls:
                # Track tool call in separate list
                tool_call_history.append(
                    {
                        'name': call.__class__.__name__,
                        'arguments': call.model_dump(),
                    }
                )

                args_string = ', '.join([f"{k} = '{v}'" for k, v in call.model_dump().items()])
                logging.info(f'{call.__class__.__name__}({args_string})')

                try:
                    tool_call_output = call.forward()
                    messages.append(
                        {
                            'role': 'tool',
                            'name': call.__class__.__name__,
                            'content': tool_call_output,
                        }
                    )
                    logging.info(f'→ {tool_call_output!s}')

                # If the tool call fails, log the error and continue
                except Exception as e:
                    messages.append(
                        {
                            'role': 'tool',
                            'name': call.__class__.__name__,
                            'content': f'Error: {e!s}',
                        }
                    )
                    logging.exception(f'Error: {e!s}')

        logging.info('🏁 Generation complete.')
        return messages


# --- If run directly ---
if __name__ == '__main__':
    FORMAT = '%(message)s'
    logging.basicConfig(level='NOTSET', format=FORMAT, datefmt='[%X]', handlers=[RichHandler()])

    # print(json.dumps(FullOutput.model_json_schema(), indent=2))

    model = OpenAIModel(
        model_name='gpt-4o-mini',
        use_tools='full',
    )

    # messages = model.generate(
    #     messages=[
    #         {'role': 'system', 'content': model.system_prompt},
    #         {'role': 'user', 'content': 'What was the Arable land (% of land area) of Oman in 2015?'},
    #     ],
    # )

    model.system_prompt = (
        'Answer the question by creating a tool call. I will then execute the tool call and return the result to you.'
    )

    messages = model.loop('What is 2+3?')
    print(messages)
