import argparse
import logging
from pathlib import Path

import networkx as nx
import pandas as pd
from rich.logging import RichHandler

from graphs.graph import FrankensteinGraph
from graphs.report import GraphReport


def batch_generate_graphs_and_reports(
    df_path: str,
    tool_schema_path: str,
    out_graph_dir: str = 'graphs',
    out_report_dir: str = 'graphs',
    limit: int | None = None,
    save_fig: bool = True,
):
    """Batch generate GEXF graphs and YAML reports for each row in a dataframe.

    Parameters
    ----------
    df_path : str
        Path to the input dataframe (JSONL).
    tool_schema_path : str
        Path to the tool schema JSONL file.
    out_graph_dir : str
        Directory to save GEXF graph files.
    out_report_dir : str
        Directory to save YAML report files.
    limit : int or None
        If set, process only the first `limit` rows.
    save_fig : bool
        If True, also save a PNG figure of the graph (default: True).

    """
    out_graph_dir = Path(out_graph_dir)
    out_report_dir = Path(out_report_dir)
    out_graph_dir.mkdir(parents=True, exist_ok=True)
    out_report_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_json(df_path, orient='records', lines=True)
    if limit:
        df = df.head(limit)

    logging.info(f'Loaded dataframe with {len(df)} rows from {df_path}')

    for idx, row in df.iterrows():
        row_id = row.get('id', f'row_{idx}')
        logging.info(f'Processing row {idx} (id={row_id})')

        # Build graph
        G = FrankensteinGraph(row, enable_logging=False)
        # Flatten node/edge attributes for GEXF
        for n, data in G.nodes(data=True):
            for k, v in list(data.items()):
                if isinstance(v, (list, dict)):
                    data[k] = str(v)
        for u, v, data in G.edges(data=True):
            for k, v in list(data.items()):
                if isinstance(v, (list, dict)):
                    data[k] = str(v)

        gexf_path = out_graph_dir / f'{row_id}.gexf'
        nx.write_gexf(G, gexf_path)
        logging.info(f'Wrote graph to {gexf_path}')

        # Optionally save figure
        if save_fig:
            try:
                G.draw()
                logging.info(f'Saved graph figure for {row_id}')
            except Exception as e:
                logging.warning(f'Could not save figure for {row_id}: {e}')

        # Generate YAML report
        report = GraphReport(path_to_graph_file=gexf_path, tool_schema_path=tool_schema_path, enable_logging=False)
        yaml_path = out_report_dir / f'{row_id}.yaml'
        report.report_args(yaml_path=str(yaml_path))
        logging.info(f'Wrote YAML report to {yaml_path}')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        datefmt='[%X]',
        handlers=[RichHandler()],
    )

    parser = argparse.ArgumentParser(description='Batch generate graphs and YAML reports from a dataframe.')
    parser.add_argument('--df', type=str, required=True, help='Path to the input dataframe (JSONL)')
    parser.add_argument(
        '--tool-schema', type=str, default='frankenstein/tools/tool_schema.jsonl', help='Path to the tool schema JSONL file'
    )
    parser.add_argument('--out-graph-dir', type=str, default='graphs/outputs', help='Directory to save GEXF files')
    parser.add_argument('--out-report-dir', type=str, default='graphs/outputs', help='Directory to save YAML reports')
    parser.add_argument('--limit', type=int, default=None, help='Limit the number of rows processed')
    parser.add_argument('--no-fig', action='store_true', help='Disable saving PNG figures of the graphs')
    args = parser.parse_args()

    batch_generate_graphs_and_reports(
        df_path=args.df,
        tool_schema_path=args.tool_schema,
        out_graph_dir=args.out_graph_dir,
        out_report_dir=args.out_report_dir,
        limit=args.limit,
        save_fig=not args.no_fig,
    )
