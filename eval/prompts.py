import json

from franklin.utils import get_tool_metadata

BASE_PROMPT = """You are a helpful assistant tasked with answering questions that require multiple intermediate steps of reasoning to arrive at a final answer.

The questions involve using World Bank data for various countries and indicators, and you have access to a set of tools that can help you retrieve and process this data.

Step-by-step, use the tools provided to execute that plan. Use the `think` tool to think aloud about the steps you will take to solve the problem. Use the `final_answer` tool to return your final answer.

Use the results of each tool call to inform your next step. Note that passing tool calls as the arguments to other tool calls is not allowed. Instead, execute each tool call separately and use the results to perform subsequent calls.

If a tool call fails, use the error message to help you debug the issue, re-plan, and try again if possible.

Bear in mind that some data may not be available for certain countries, indicators, or years, but the question may still be answerable.

"""

FULL_TOOL_USE = f"""The tools you have access to are below:

{get_tool_metadata()}

Pay attention to the tool names, arguments, descriptions, and the types of outputs they return, and think carefully about how to use them to solve the problem.

If there is a tool available that can help you with the next step, you must use it rather than trying to solve the problem without it.

Your output must be a JSON structure as follows: {{'tool_calls': [{{'name': 'tool_name_1', 'arguments': {{'arg1': 'value1', 'arg2': 'value2'}}}}, {{'name': 'tool_name_2', 'arguments': {{'arg1': 'value1', 'arg2': 'value2'}}}}, ...]}}

I will execute tool calls that you provide. You can use multiple tools in one step, make sure you follow the correct format.

If you have found the answer, call the final_answer tool and provide your answer as the argument, as below:

{{'tool_calls': [{{'name': 'final_answer', 'arguments': {{'answer': '<your answer here>'}}}}]}}

Only provide the answer (e.g., the number, list, string, or boolean value) in the answer field. Do not include any additional text or explanations. Do not perform any rounding or formatting of the answer.

"""


SIMULATE_TOOL_USE = f"""Here is the list of available tools:

{json.dumps(get_tool_metadata(), indent=2)}

To perform each step in the task, simulate a tool use step by calling the tool with the required parameters, and then providing the output yourself by simulating the tool's response.

When simulating a tool call, *only generate the tool call* and do not include any other text. Include your output as a 'result' key in the tool call, like this:

{json.dumps({"name": "tool_name", "arguments": {"arg1": "value1", "arg2": "value2"}, "result": "simulated_output"}, indent=2)}

To provide the final answer, use the final_answer tool to return the answer.

"""


if __name__ == "__main__":
    print(json.dumps(FULL_TOOL_USE, indent=2))
