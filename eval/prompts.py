"""Prompts for passing to LLMs, including the base prompt, tool use prompt, and tool metadata."""

import inspect
import random
from pathlib import Path

import pandas as pd

from frankenstein.action import FrankensteinAction
from frankenstein.slot_values import Property, Region, Subject, Year
from frankenstein.tools import arithmetic, data_retrieval
from frankenstein.utils import get_tool_metadata

BASE_PROMPT = """You are a helpful assistant tasked with answering questions that require multiple intermediate steps of reasoning to arrive at a final answer.

The questions involve using World Bank data for various countries and indicators.

Create a step-by-step plan to answer the question, and then execute each step of that plan to arrive at the final answer.

The conversation will only end after you call the `final_answer` tool with your final answer.

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

{get_tool_metadata(toolbox='all')}

"""

ARITHMETIC_TOOLS = f"""The tools you have access to are below:

{get_tool_metadata(toolbox='arithmetic')}

These tools can help you perform arithmetic operations (e.g., summation, averages, differences, ratios) on numeric values. However, you must **recall or retrieve the necessary data yourself**—these tools cannot access external data sources like the World Bank.

Clearly express the data you recall using the following quadruple format: {{'subject': 'subject_name', 'property': 'property_name', 'object': 'object, 'time': 'year'}}.

"""

DATA_TOOLS = f"""The tools you have access to are below:

{get_tool_metadata(toolbox='data')}

These tools allow you to access World Bank indicators and retrieve data for specific countries, indicators, and years. Use them to fetch relevant data to answer the question.

However, you must **perform any necessary arithmetic manually**, without tool support for computation. If the answer requires calculations (e.g., summation, averages), you must compute these yourself based on the retrieved data.

"""


def generate_tool_call_example(tool_name, tool_modules):
    """Generate and execute a single tool call example for a given tool name."""
    # Gather all available tool functions
    tool_map = {}
    for module in tool_modules:
        tool_map.update(dict(inspect.getmembers(module, inspect.isfunction)))

    tool_func = tool_map[tool_name]

    country_codes = Subject.get_values()
    regions = [r for r in Region.get_values() if r and isinstance(r, str)]
    indicator_codes = Property.get_values()
    try:
        wdi_data = pd.read_csv(Path('resources', 'wdi.csv'))
        indicator_names = wdi_data['name'].dropna().unique().tolist()
    except Exception:
        indicator_names = indicator_codes
    try:
        iso_data = pd.read_csv(Path('resources', 'iso_3166.csv'))
        country_names = iso_data['country_name'].dropna().unique().tolist()
    except Exception:
        country_names = country_codes
    years = Year.get_values()

    params = inspect.signature(tool_func).parameters
    kwargs = {}
    for pname, p in params.items():
        if p.default is not inspect.Parameter.empty:
            kwargs[pname] = p.default
        elif pname == 'country_code':
            kwargs[pname] = random.choice(country_codes)
        elif pname == 'country_name':
            kwargs[pname] = random.choice(country_names)
        elif pname == 'region':
            kwargs[pname] = random.choice(regions)
        elif pname == 'indicator_name':
            kwargs[pname] = random.choice(indicator_names)
        elif pname == 'indicator_code':
            kwargs[pname] = random.choice(indicator_codes)
        elif pname == 'year':
            kwargs[pname] = random.choice(years)
        elif pname in {'a', 'b', 'value_a', 'value_b'}:
            kwargs[pname] = round((random.random() - 0.5) * 10, random.randint(3, 10))
        elif pname == 'values':
            kwargs[pname] = [round((random.random() - 0.5) * 10, random.randint(3, 10)) for _ in range(3)]
        elif pname == 'keywords':
            kwargs[pname] = ['water']
        elif pname == 'thought':
            kwargs[pname] = 'Use this field to plan or think aloud about what actions to take.'
        elif pname == 'answer':
            kwargs[pname] = round((random.random() - 0.5) * 100, random.randint(0, 10))
        else:
            kwargs[pname] = 'test'

    action = FrankensteinAction(tool_name, **kwargs)
    result = action.execute()
    tool_call = f'{tool_name}({", ".join(f"{k}={v!r}" for k, v in kwargs.items())})'
    example = f'Example of `{tool_name}` tool call: {tool_call}\nReturns: {result}'
    return example


def create_n_shot_examples(n: int = 3, toolbox: str = 'all') -> str:
    """Create n random examples for each available tool, grouped by tool (DFS order), for the specified toolbox."""
    # Select modules based on toolbox
    if toolbox == 'arithmetic':
        tool_modules = [arithmetic]
    elif toolbox == 'data':
        tool_modules = [data_retrieval]
    else:
        tool_modules = [arithmetic, data_retrieval]

    tool_map = {}
    for module in tool_modules:
        tool_map.update(dict(inspect.getmembers(module, inspect.isfunction)))
    tool_names = list(tool_map.keys())

    all_examples = []
    for tool_name in tool_names:
        tool_examples = []
        for _ in range(n):
            example = generate_tool_call_example(tool_name, tool_modules)
            tool_examples.append(example)
        all_examples.append('\n\n'.join(tool_examples))
    return '\n---\n'.join(all_examples)


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
    print('=== N SHOT EXAMPLES ===')
    print(create_n_shot_examples(3))
