import argparse
import json
import logging
from pathlib import Path

import networkx as nx
import yaml
from rich.console import Console
from rich.logging import RichHandler
from rich.syntax import Syntax

DATA_DIR = Path('resources')
INDICATOR_DATA_DIR = DATA_DIR / 'wdi'
INDICATOR_KEY = DATA_DIR / 'wdi.csv'
UN_M49 = DATA_DIR / 'un_m49_cleaned.csv'


class GraphReport:
    """Analyze a tool-use graph and generate a report documenting missing or unclear argument provenance.

    Parameters
    ----------
    path_to_graph_file : Path or None
        Path to the graph file (.gexf).
    graph_object : nx.DiGraph or None
        An in-memory networkx DiGraph object.
    tool_schema_path : str or None
        Path to the tool schema JSONL file.

    """

    def __init__(
        self,
        path_to_graph_file: Path | None = None,
        graph_object: nx.DiGraph | None = None,
        tool_schema_path: str | None = None,
        enable_logging: bool = True,
    ):
        """Initialize the GraphReport.

        Parameters
        ----------
        path_to_graph_file : Path or None
            Path to the graph file (.gexf).
        graph_object : nx.DiGraph or None
            An in-memory networkx DiGraph object.
        tool_schema_path : str or None
            Path to the tool schema JSONL file.
        enable_logging : bool
            If False, disables logging output from this class.

        """
        if not enable_logging:
            logging.getLogger().setLevel(logging.CRITICAL + 1)

        if path_to_graph_file:
            logging.info(f"Loading graph from file: '{path_to_graph_file}'")
            self.G = nx.read_gexf(path_to_graph_file)
            logging.info(f'Loaded graph with {len(self.G.nodes)} nodes and {len(self.G.edges)} edges.')
        elif graph_object:
            logging.info('Using provided in-memory graph object.')
            self.G = graph_object
        else:
            raise ValueError('Either path_to_graph_file or graph_object must be provided.')

        self.tool_schema = None
        if tool_schema_path:
            logging.info(f'Loading tool schema from: {tool_schema_path}')
            self.tool_schema = self.load_tool_schema(tool_schema_path)
            logging.info(f'Loaded tool schema with {len(self.tool_schema)} tools.')

    def load_tool_schema(self, path_to_tool_schema: str) -> dict:
        """Load the tool schema from a JSONL file.

        Parameters
        ----------
        path_to_tool_schema : str
            Path to the tool schema JSONL file.

        Returns
        -------
        dict
            Mapping of tool names to their required arguments and types.

        """
        tools = {}
        with open(path_to_tool_schema) as f:
            for line in f:
                obj = json.loads(line)
                fn = obj['function']
                name = fn['name']
                params = fn['parameters']
                required = set(params.get('required', []))
                properties = params.get('properties', {})
                types = {k: v.get('type', 'string') for k, v in properties.items()}
                tools[name] = {'required': required, 'types': types}
        logging.debug(f'Tool schema loaded: {list(tools.keys())}')
        return tools

    def generate_graph_yaml(self) -> str:
        """Generate a YAML-style report of the tool-use graph, with explicit argument provenance.

        Returns
        -------
        str
            YAML string representing the report.

        """
        G = self.G
        tools = self.tool_schema
        report = {}

        logging.info('Building argument provenance mapping and collecting issues.')
        # Build mapping from (node, arg_name) -> source node
        arg_sources = {}
        issues = []
        for src, dst, edata in G.edges(data=True):
            slot = edata.get('label', None)
            if slot:
                arg = slot.split('=')[0] if '=' in slot else slot
                arg_sources[(dst, arg)] = src

        # Nodes
        nodes_list = []
        for node, data in G.nodes(data=True):
            node_dict = {'id': node}
            if data:
                call_index = data.get('call_index')
                tool_name = data.get('label')
                result = data.get('result')
                tool_args = {k.removeprefix('arg_'): v for k, v in data.items() if k.startswith('arg_')}

                if call_index is not None:
                    node_dict['call_index'] = call_index
                if tool_name is not None:
                    node_dict['tool_name'] = tool_name if node != 'question_root' else None
                    if node == 'question_root':
                        node_dict['original_question'] = tool_name

                # Arguments with provenance
                if tool_args:
                    args_list = []
                    for arg, v in tool_args.items():
                        origin = arg_sources.get((node, arg))
                        if not origin:
                            issues.append(
                                f'Node `{node}` arg `{arg}` = `{v}` has no incoming edge, indicating that it is not derived from a previous tool call and so its provenance is unclear.'
                            )
                            origin = None
                        args_list.append({'name': arg, 'value': v, 'source_node': origin})
                    node_dict['arguments'] = args_list

                # Result
                if result is not None:
                    node_dict['result'] = result
            else:
                node_dict['note'] = 'No attributes'

            nodes_list.append(node_dict)
        report['nodes'] = nodes_list

        # Edges
        edges_list = []
        for src, dst, edata in G.edges(data=True):
            label = edata.get('label', None)
            edge_dict = {'from': src, 'to': dst, 'arg': None}
            if label:
                if '=' in label:
                    arg, value = label.split('=', 1)
                    edge_dict['arg'] = {arg: value}
                else:
                    edge_dict['arg'] = label
            edges_list.append(edge_dict)
        report['edges'] = edges_list

        # Issues
        report['issues'] = issues

        logging.info(f'Collected {len(issues)} issues in the graph.')
        # Output YAML
        yaml_str = yaml.dump(report, sort_keys=False, allow_unicode=True)
        return yaml_str

    def report_args(self, yaml_path: str | None = None):
        """Generate and optionally save a YAML report of the graph.

        Parameters
        ----------
        yaml_path : str or None
            If provided, path to save the YAML report. If None, print to stdout.

        """
        yaml_report = self.generate_graph_yaml()
        if yaml_path:
            logging.info(f"Writing YAML report to: '{yaml_path}'")
            with open(yaml_path, 'w', encoding='utf-8') as f:
                f.write(yaml_report)
            logging.info('YAML report written successfully.')
        else:
            logging.info('Printing YAML report to console.')
            # Pretty print YAML to console using rich
            console = Console()
            syntax = Syntax(yaml_report, 'yaml', line_numbers=True)
            console.print(syntax)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(message)s',
        datefmt='[%X]',
        handlers=[RichHandler()],
    )

    parser = argparse.ArgumentParser(description='Report missing or incorrect tool arguments in a graph.')
    parser.add_argument('--graph-file', type=str, required=True, help='Path to the graph file (.gexf or .graphml)')
    parser.add_argument(
        '--tool-schema',
        type=str,
        help='Path to the tool schema JSONL file',
        default='frankenstein/tools/tool_schema.jsonl',
    )
    parser.add_argument('--yaml', action='store_true', help='If set, output YAML file named after the graph file')
    args = parser.parse_args()

    logging.info('Starting GraphReport analysis...')
    report = GraphReport(path_to_graph_file=Path(args.graph_file), tool_schema_path=args.tool_schema)

    yaml_path = None
    if args.yaml:
        graph_stem = Path(args.graph_file).stem
        yaml_path = f'graphs/outputs/{graph_stem}.yaml'

    report.report_args(yaml_path=yaml_path)
    logging.info('Done.')
