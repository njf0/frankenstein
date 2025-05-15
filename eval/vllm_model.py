import json
import logging
from copy import deepcopy

from openai import OpenAI
from pydantic import ValidationError
from rich.logging import RichHandler
from vllm import LLM
from vllm.sampling_params import GuidedDecodingParams, SamplingParams

from eval.prompts import BASE_PROMPT, FULL_TOOL_USE, SIMULATE_TOOL_USE
from franklin.action import FranklinAction
from franklin.schema import ToolCalls


# --- Main Model Class ---
class vLLMModel:
    def __init__(
        self,
        model_name: str,
        use_tools: str = 'none',  # Should match 'full' / 'simulate' / 'none'
        debug: bool = False,
    ) -> None:
        """Initialize the model with the given parameters.

        Parameters
        ----------
        model_name: str
            Name of the model to use.
        use_tools: str
            Tool-use mode. Can be 'full', 'simulate', or 'none'.
        debug: bool
            Enable debug mode.

        """
        self.model_name = model_name

        # self.client = OpenAI(
        #     base_url='http://localhost:8000/v1',
        #     api_key='token-abc123',
        # )

        if use_tools == 'full':
            self.system_prompt = BASE_PROMPT + FULL_TOOL_USE
        elif use_tools == 'simulate':
            self.system_prompt = BASE_PROMPT + SIMULATE_TOOL_USE
        else:
            self.system_prompt = BASE_PROMPT

        self.use_tools = use_tools
        self.debug = debug

        # Initialize the LLM with the model name and prompt
        self.llm = LLM(
            model=self.model_name,
            trust_remote_code=True,
            guided_decoding_backend='xgrammar',
        )

        # Generate grammar from Pydantic model
        self.json_schema = ToolCalls.model_json_schema()
        self.guided_decoding_params_json = GuidedDecodingParams(json=self.json_schema)

    def _has_final_answer(
        self,
        messages: list[dict],
    ) -> bool:
        """Check if the final answer has been provided in the messages.

        Parameters
        ----------
        messages: list[dict]
            List of messages exchanged in the conversation.

        Returns
        -------
        bool
            True if the final answer has been provided, False otherwise.

        """
        for message in messages:
            # Check if the message is a tool call with the name 'final_answer'
            if (message.get('role') == 'tool' and message.get('name') == 'final_answer') or (
                message.get('role') == 'assistant' and messages.count(message) > 10
            ):
                return True

    def process_tool_call(
        self,
        tool_call: dict,
    ) -> dict:
        """Process a tool call and return the result.

        Parameters
        ----------
        tool_call: dict
            The tool call to process.

        Returns
        -------
        dict
            The processed tool call as a dictionary.

        """
        name = tool_call.get('name')
        args = tool_call.get('arguments', {})

        return FranklinAction(name, **args).execute(error_handling='raise')

    def generate(
        self,
        messages: list[dict],
    ) -> str:
        """Generate a response from the model based on the input messages.

        Parameters
        ----------
        messages: list[dict]
            List of messages exchanged in the conversation.

        Returns
        -------
        str
            The generated response from the model.

        """
        # Set sampling parameters with a fixed temperature of 0.2
        sampling_params = SamplingParams(
            max_tokens=4096,
            guided_decoding=self.guided_decoding_params_json,
            temperature=0.2,
        )

        # Generate the response using the LLM
        outputs = self.llm.chat(
            messages,
            sampling_params=sampling_params,
            use_tqdm=False,
        )

        # Extract the generated text from the outputs
        output_text = outputs[0].outputs[0].text

        # # Try VLLM serve
        # completion = self.client.chat.completions.create(
        #     model=self.model_name,
        #     messages=messages,
        #     extra_body={'guided_json': self.json_schema},
        # )

        # output_text = completion.choices[0].message.content

        return output_text

    def loop(
        self,
        input_text: str,
    ) -> list[dict]:
        """Run a full tool-using loop for a single input.

        Parameters
        ----------
        input_text: str
            The input text to process.

        Returns
        -------
        list[dict]
            List of messages exchanged in the conversation.

        """
        # Initialize the messages list with system and user prompts
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': input_text},
        ]
        # print(messages[0])
        # print(messages[1])
        logging.info(f'❓ {input_text}')

        # Main loop to process messages until a final answer is provided
        while not self._has_final_answer(messages):
            # Do an input thing where I can just press enter to continue or any other key to stop
            if self.debug:
                i = input('')
                if i.lower() != '':
                    break

            # Generate a response from the model
            messages_copy = deepcopy(messages)
            output_text = self.generate(messages_copy)

            # Parse the output text using the FullOutput model
            try:
                parsed = ToolCalls.model_validate_json(output_text)
            except ValidationError:
                try:
                    parsed = ToolCalls.model_validate_json(json.loads(output_text))
                except (json.JSONDecodeError, json.decoder.JSONDecodeError):
                    # Handle any parsing errors
                    messages.append(
                        {
                            'role': 'user',
                            'content': 'Error processing JSON output. Please try again with fewer tool calls.',
                        }
                    )
                    # print(messages[-1])
                    logging.error(messages[-1]['content'])  # noqa: TRY400
                    continue

            # Check if the output is a tool call
            tool_calls = parsed.tool_calls if isinstance(parsed.tool_calls, list) else [parsed.tool_calls]

            # Check if the output is empty
            if not tool_calls:
                messages.append(
                    {
                        'role': 'user',
                        'content': 'No tool calls found.',
                    }
                )
                logging.error(messages[-1]['content'])
                continue

            # Process each tool call
            for call in tool_calls:
                # Convert Pydantic model to JSON
                call_json = call.model_dump()

                # Append tool call message
                messages.append(
                    {
                        'role': 'assistant',
                        'tool_calls': [
                            {
                                'type': 'function',
                                'function': {
                                    'name': call_json['name'],
                                    'arguments': json.dumps(call_json['arguments']),
                                },
                            }
                        ],
                    }
                )
                args_string = ', '.join([f"{k} = '{v}'" for k, v in call_json['arguments'].items()])
                logging.info(f'{call_json["name"]}({args_string})')

                # Process the tool call and get the output
                try:
                    tool_call_output = self.process_tool_call(tool_call=call_json)

                    # Check if the tool call output is empty
                    if tool_call_output['result'] is None:
                        result = 'Your function call was correct, but no data is available for this query.'

                        # Append modified message
                        messages.append(
                            {
                                'role': 'tool',
                                'name': tool_call_output['name'],
                                'content': str(result),
                            }
                        )
                        logging.warning(result)

                    # Or append as normal
                    else:
                        messages.append(
                            {
                                'role': 'tool',
                                'name': call_json['name'],
                                'content': str(tool_call_output['result']),
                            }
                        )
                        logging.info(f'→ {tool_call_output["result"]}')

                # Handle any exceptions that occur during processing
                except Exception as e:
                    # Append the error message to the list
                    messages.append(
                        {
                            'role': 'tool',
                            'name': call_json['name'],
                            'content': f'Error: {e!s}',
                        }
                    )
                    logging.exception(f'Error: {e!s}')

        logging.info('🏁 Generation complete.')

        return messages


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
        return FranklinAction(name, **args).execute(error_handling='raise')

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
        return response.output_parsed

    def loop(
        self,
        input_text: str,
    ) -> list[dict]:
        """Run a full tool-using loop for a single input."""
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': input_text},
        ]
        logging.info(f'❓ {input_text}')

        while not self._has_final_answer(messages):
            if self.debug:
                i = input('')
                if i.lower() != '':
                    break

            messages_copy = deepcopy(messages)
            try:
                parsed = self.generate(messages_copy)
            except Exception as e:
                messages.append(
                    {
                        'role': 'user',
                        'content': f'Error processing structured output: {e!s}',
                    }
                )
                logging.exception(messages[-1]['content'])
                continue

            tool_calls = parsed.tool_calls if isinstance(parsed.tool_calls, list) else [parsed.tool_calls]

            if not tool_calls:
                messages.append(
                    {
                        'role': 'user',
                        'content': 'No tool calls found.',
                    }
                )
                logging.error(messages[-1]['content'])
                continue

            for call in tool_calls:
                call_json = dict(call)  # Already a dict from TypedDict
                messages.append(
                    {
                        'role': 'assistant',
                        'tool_calls': [
                            {
                                'type': 'function',
                                'function': {
                                    'name': call_json['name'],
                                    'arguments': json.dumps(call_json['arguments']),
                                },
                            }
                        ],
                    }
                )
                args_string = ', '.join([f"{k} = '{v}'" for k, v in call_json['arguments'].items()])
                logging.info(f'{call_json["name"]}({args_string})')

                try:
                    tool_call_output = self.process_tool_call(tool_call=call_json)
                    if tool_call_output['result'] is None:
                        result = 'Your function call was correct, but no data is available for this query.'
                        messages.append(
                            {
                                'role': 'tool',
                                'name': tool_call_output['name'],
                                'content': str(result),
                            }
                        )
                        logging.warning(result)
                    else:
                        messages.append(
                            {
                                'role': 'tool',
                                'name': call_json['name'],
                                'content': str(tool_call_output['result']),
                            }
                        )
                        logging.info(f'→ {tool_call_output["result"]}')
                except Exception as e:
                    messages.append(
                        {
                            'role': 'tool',
                            'name': call_json['name'],
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

    messages = model.generate(
        messages=[
            {'role': 'system', 'content': model.system_prompt},
            {'role': 'user', 'content': 'What was the Arable land (% of land area) of Oman in 2015?'},
        ]
    )
