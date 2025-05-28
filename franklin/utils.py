import inspect
import re
from typing import Union, get_args, get_origin

import rich.console
import rich.table

from franklin.tools import arithmetic, data_retrieval, utils


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
