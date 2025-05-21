"""Prompts for passing to LLMs, including the base prompt, tool use prompt, and tool metadata."""

from franklin.utils import get_tool_metadata

BASE_PROMPT = """You are a helpful assistant tasked with answering questions that require multiple intermediate steps of reasoning to arrive at a final answer.

The questions involve using World Bank data for various countries and indicators.

Create a step-by-step plan to answer the question, and then execute each step of that plan to arrive at the final answer.

"""

TOOL_USE_BASE = """You have access to a set of tools to help you answer the question:

Pay attention to the tool names, arguments, descriptions, and the types of outputs they return, and think carefully about how to use them to solve the problem.

If there is a tool available that can help you with the next step, you must use it rather than trying to solve the problem without it.

I will execute tool calls that you provide. You can use multiple tools in one step, but make sure you follow the correct format.

Use the results of each tool call to inform your next step. Passing tool calls as arguments to other tool calls is not allowed. Instead, execute each tool call separately and use the results to perform subsequent calls.

If a tool call fails, use the error message to help you debug the issue, re-plan, and try again if possible.

Only provide the answer itself (e.g., the number, list, string, or boolean value) as your answer. Do not include any additional text or explanations. Do not perform any rounding or formatting of the answer.

"""

ALL_TOOLS = f"""The tools you have access to are below:

{get_tool_metadata(toolset='all')}

"""

ARITHMETIC_TOOLS = f"""The tools you have access to are below:

{get_tool_metadata(toolset='arithmetic')}

"""

DATA_TOOLS = f"""The tools you have access to are below:

{get_tool_metadata(toolset='data')}

"""


if __name__ == '__main__':
    print('=== BASE PROMPT ===')
    print(BASE_PROMPT)
    print('=== TOOL USE BASE ===')
    print(TOOL_USE_BASE)
    print('=== ALL TOOLS ===')
    print(ALL_TOOLS)
    print('=== ARITHMETIC TOOLS ===')
    print(ARITHMETIC_TOOLS)
    print('=== DATA TOOLS ===')
    print(DATA_TOOLS)
