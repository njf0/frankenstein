import ast  # <-- Add this import
import inspect
import json
import re
from typing import Union, get_args, get_origin

import rich.console
import rich.table

from frankenstein.tools import arithmetic, data_retrieval, utils


def parse_json_arguments(obj):
    """Recursively parse JSON-formatted argument strings in tool_calls and any string that looks like a JSON list/dict."""
    if isinstance(obj, dict):
        # If this is a tool_call dict with a function and arguments as a string, parse it
        if (
            'function' in obj
            and isinstance(obj['function'], dict)
            and 'arguments' in obj['function']
            and isinstance(obj['function']['arguments'], str)
        ):
            try:
                obj['function']['arguments'] = json.loads(obj['function']['arguments'])
            except Exception:
                # Try ast.literal_eval as fallback
                try:
                    obj['function']['arguments'] = ast.literal_eval(obj['function']['arguments'])
                except Exception:
                    pass  # leave as is if not valid
        # Recurse into all dict values
        return {k: parse_json_arguments(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [parse_json_arguments(v) for v in obj]
    elif isinstance(obj, str):
        s = obj.strip()
        if (s.startswith('[') and s.endswith(']')) or (s.startswith('{') and s.endswith('}')):
            try:
                return json.loads(s)
            except Exception:
                try:
                    return ast.literal_eval(s)
                except Exception:
                    return obj
        return obj
    elif hasattr(obj, '__dict__'):
        # For objects like ChatCompletionMessageToolCall, Function, etc.
        d = vars(obj)
        # If this is a tool_call object with a function and arguments as a string, parse it
        if 'function' in d and hasattr(d['function'], 'arguments') and isinstance(d['function'].arguments, str):
            try:
                d['function'].arguments = json.loads(d['function'].arguments)
            except Exception:
                try:
                    d['function'].arguments = ast.literal_eval(d['function'].arguments)
                except Exception:
                    pass
        # Recurse into all attributes
        return {k: parse_json_arguments(v) for k, v in d.items()}
    else:
        return obj


def to_json_safe(obj):
    """Recursively convert objects to JSON-serializable types."""
    if isinstance(obj, dict):
        return {k: to_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_json_safe(v) for v in obj]
    elif hasattr(obj, '__dict__'):
        return to_json_safe(vars(obj))
    else:
        return obj


def print_slot_value_table(
    allowed_values: dict,
    num_combinations: int,
):
    """Print a table of slot values and the number of allowed values for each slot.

    Parameters
    ----------
    allowed_values: dict
        Allowed values for the slots.
    num_combinations: int
        The number of combinations.

    """
    table = rich.table.Table(title='Combinations', show_footer=True)
    table.add_column('Field')
    table.add_column('Values')

    for field, values in allowed_values.items():
        table.add_row(field, str(len(values.get_values())))

    # Footer row for total number of combinations
    table.columns[0].footer = 'Total'
    table.columns[1].footer = str(num_combinations)

    console = rich.console.Console()
    console.print(table)


def parse_args_section(
    docstring: str,
) -> dict:
    """Parse the Args section of a docstring into a dict.

    Parameters
    ----------
    docstring : str
        The docstring to parse.

    Returns
    -------
    dict
        A dictionary mapping parameter names to their descriptions.

    """
    args_section = {}
    if not docstring:
        return args_section

    # Find the Args section
    args_match = re.search(r'Args:\n(.*?)(\n\S|\Z)', docstring, re.DOTALL)
    if not args_match:
        return args_section

    args_text = args_match.group(1)

    # Match parameter lines like: param_name: description...
    param_matches = re.finditer(r'^\s*(\w+):\s*(.*?)(?=\n\s*\w+:|\Z)', args_text, re.DOTALL | re.MULTILINE)
    for match in param_matches:
        param_name = match.group(1)
        description = match.group(2).strip().replace('\n', ' ')
        args_section[param_name] = description

    return args_section


def python_type_to_openai(
    python_type: type,
) -> dict:
    """Convert a Python type to OpenAI schema format.

    Parameters
    ----------
    python_type : type
        The Python type to convert.

    Returns
    -------
    dict
        A dictionary representing the OpenAI schema format.

    """
    origin = get_origin(python_type)
    args = get_args(python_type)

    if origin in [list, tuple]:
        item_type = python_type_to_openai(args[0]) if args else {'type': 'string'}
        return {'type': 'array', 'items': item_type}

    if origin is Union:
        return python_type_to_openai(args[0])  # Simplified fallback

    if python_type in [str, int, float, bool]:
        return {'type': {str: 'string', int: 'integer', float: 'number', bool: 'boolean'}[python_type]}

    return {'type': 'string'}  # Fallback


def get_tool_metadata(
    toolset: str = 'all',
    schema: str = 'openai',
):
    """Generate function metadata in a given schema format.

    Parameters
    ----------
    toolset : str
        The toolset to use. Options are 'all', 'arithmetic', or 'data'.
    schema : str
        The schema format to use. Options are 'openai', 'claude', or 'basic'.

    Returns
    -------
    list
        A list of dictionaries containing function metadata.

    """
    # Always include utils tools
    modules = []
    if toolset == 'all':
        modules = [arithmetic, data_retrieval]
    elif toolset == 'arithmetic':
        modules = [arithmetic]
    elif toolset == 'data':
        modules = [data_retrieval]
    elif toolset == 'utils':
        modules = []
    else:
        raise ValueError(f'Invalid toolset: {toolset}')
    modules.append(utils)  # Always add utils

    metadata = []

    for module in modules:
        for name, func in inspect.getmembers(module, inspect.isfunction):
            doc = inspect.getdoc(func) or 'No description available.'
            signature = inspect.signature(func)
            arg_descriptions = parse_args_section(doc)

            # Parse parameters
            params = []
            required = []
            param_properties = {}

            for param in signature.parameters.values():
                param_name = param.name
                param_type = param.annotation if param.annotation is not inspect.Parameter.empty else str

                if schema in {'openai', 'claude'}:
                    param_schema = python_type_to_openai(param_type)
                    param_schema['description'] = arg_descriptions.get(param_name, f'{param_name} parameter')
                    param_properties[param_name] = param_schema
                    if param.default is inspect.Parameter.empty:
                        required.append(param_name)
                else:
                    params.append({'name': param_name, 'type': str(param_type)})

            if schema == 'openai':
                metadata.append(
                    {
                        'type': 'function',
                        'function': {
                            'name': name,
                            'description': doc.split('\n\n')[0],
                            'parameters': {'type': 'object', 'properties': param_properties, 'required': required},
                        },
                    }
                )

            elif schema == 'claude':
                metadata.append(
                    {
                        'name': name,
                        'description': doc.split('\n\n')[0],
                        'input_schema': {'type': 'object', 'properties': param_properties, 'required': required},
                    }
                )

            elif schema == 'basic':
                metadata.append(
                    {
                        'name': name,
                        'description': doc.split('\n\n')[0],
                        'arguments': params,
                        'output': str(signature.return_annotation),
                    }
                )

            else:
                raise ValueError(f'Unknown schema type: {schema}')

    return metadata


if __name__ == '__main__':
    # Example usage
    metadata = get_tool_metadata(toolset='all')
    for func in metadata:
        print(func)
