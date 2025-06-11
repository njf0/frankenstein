import json
import logging
import string
from collections import defaultdict, deque
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from rich.logging import RichHandler

from frankenstein.action import FrankensteinAction  # ← make sure import path is correct


class FrankensteinGraph(nx.DiGraph):
    """Directed acyclic graph of FrankensteinAction tool calls + optional structured-question origin nodes."""

    def __init__(
        self,
        row: pd.Series,
    ):
        # Expect a pandas Series row as input
        super().__init__()
        slot_values = row.get('metadata', {}).get('slot_values', {})
        question_structure = [{k: v} for k, v in slot_values.items()]
        question = row['question']
        messages = row['messages']

        self.actions: dict[str, FrankensteinAction] = {}
        self.value_provenance: dict[str, List[str]] = {}  # value → list[producer_id]
        self.question_nodes: dict[tuple[str, str], str] = {}  # (key,val) → node_id
        self.question = question  # Store the NLQ if provided

        self._add_origin_root(question_structure or [])
        self._build_graph(messages)

    # ---------- helpers --------------------------------------------------
    @staticmethod
    def _norm(val) -> List[str]:
        """Return a list of string representations for matching."""
        if isinstance(val, list):
            return [str(v) for v in val]
        if isinstance(val, dict):
            return [str(v) for v in val.values()]
        if val is not None:
            return [str(val)]
        return []

    @staticmethod
    def _format_args(args: dict) -> str:
        """Format function arguments as a string for logging and display."""
        if not args:
            return ''
        return ', '.join([f"{k}='{v}'" for k, v in args.items()])

    # ---------- origin / question node -----------------------------------
    def _add_origin_root(self, structures: List[Dict[str, Any]]):
        self.origin_node_id = 'question_root'
        flat_pairs = [(k, str(v)) for d in structures for k, v in d.items()]
        self.origin_values = set(flat_pairs)

        # Add one root node
        self.add_node(
            self.origin_node_id,
            label=self.question,
            type='question_param',
            values=dict(flat_pairs),  # optional metadata
        )
        logging.info(f'🌟 Added question root node with slot values: {dict(flat_pairs)}')

    # ---------- tree layout ----------------------------------------------
    def compute_tree_layout(
        self,
        root: str = 'question_root',
    ) -> Dict[str, tuple[float, float]]:
        """Compute a layered tree layout for the graph, starting from the given root node.

        Parameters
        ----------
        root : str
            The node ID to start the layout from. Default is 'question_root'.

        Returns
        -------
        Dict[str, tuple[float, float]]
            A dictionary mapping node IDs to their (x, y) positions in the layout.

        """
        # Improved: Layered layout for all weakly connected components

        G = self
        pos = {}
        y_gap = 2.0
        x_gap = 3.0
        y_offset = 0.0

        # Find all weakly connected components
        components = list(nx.weakly_connected_components(G))
        for comp in components:
            # Find roots (nodes with no in-edges in this component)
            roots = [n for n in comp if G.in_degree(n) == 0]
            if not roots:
                roots = [next(iter(comp))]  # fallback: pick any node

            # BFS from all roots in this component
            layer_nodes = defaultdict(list)
            visited = set()
            queue = deque()
            for r in roots:
                queue.append((r, 0))
                visited.add(r)
            while queue:
                node, level = queue.popleft()
                layer_nodes[level].append(node)
                for child in G.successors(node):
                    if child in comp and child not in visited:
                        visited.add(child)
                        queue.append((child, level + 1))

            # Assign positions for this component
            max_level = max(layer_nodes.keys(), default=0)
            for level in sorted(layer_nodes):
                nodes = layer_nodes[level]
                n = len(nodes)
                for i, node in enumerate(nodes):
                    x = (i - (n - 1) / 2) * x_gap
                    y = y_offset - level * y_gap
                    pos[node] = (x, y)
            # Stack components vertically
            y_offset -= (max_level + 2) * y_gap

        return pos

    # ---------- build graph ----------------------------------------------
    def _build_graph(
        self,
        messages: List[Dict[str, Any]],
    ) -> None:
        """Build the Frankenstein tool-call graph from the provided messages.

        Parameters
        ----------
        messages : List[Dict[str, Any]]
            A list of message dictionaries containing tool calls and results.

        """
        logging.info('🧩 Starting graph build process.')
        # Prepare for NLQ-argument heuristic
        self._pending: dict[str, Dict[str, Any]] = {}
        self._search_results_by_node = {}
        self._country_codes_by_node = {}
        self._question_words = set()
        if self.question:
            q = self.question.lower().translate(str.maketrans('', '', string.punctuation))
            self._question_words = set(q.split())
            logging.info(f'🔍 Extracted question words: {self._question_words}')

        # Pass 1: create nodes
        self._create_nodes(messages)
        # Pass 2: add edges
        self._add_edges()

        # --- Report on provenance and pending after graph build -------------
        if self._pending:
            logging.info(f'🗂️ Pending tool calls left after graph build: {list(self._pending.keys())}')
        else:
            logging.info('✅ No pending tool calls left after graph build.')

        unused_provenance = {
            k: v for k, v in self.value_provenance.items() if len(v) > 0 and not any(self.has_node(n) for n in v)
        }
        if unused_provenance:
            logging.info(f'🧾 Unused provenance values (not mapped to any node): {unused_provenance}')
        else:
            logging.info('✅ All provenance values mapped to nodes.')

        logging.debug(f'📚 Full value_provenance mapping: {self.value_provenance}')

    def _create_nodes(
        self,
        messages: List[Dict[str, Any]],
    ) -> None:
        """Pass 1: Create FrankensteinAction objects and graph nodes.

        This method processes the messages and creates nodes for each tool call and its result.
        It also tracks provenance for values produced by tool calls, and adds special nodes for errors and warnings.

        Nodes are added based on the following heuristics:
        1. Each tool call result is added as a node, with its arguments and result.
        2. Provenance is tracked for each output value, mapping values to the producing node.
        3. If a tool call result starts with 'Error:', an edge is added from the node to a generic error node.
        4. If a tool call result starts with 'Warning:', an edge is added from the node to a generic warning node.
        5. Special cases:
           5a. For 'search_for_indicator_codes', propagate indicator names and ids for provenance.
           5b. For 'get_country_codes_in_region', track all country codes for provenance.

        Parameters
        ----------
        messages : List[Dict[str, Any]]
            A list of message dictionaries containing tool calls and results.

        """
        self._error_node_id = None
        self._warning_node_id = None
        for m in messages:
            role = m.get('role')
            logging.info(f'👤 Processing message with role: {role}')
            if role == 'assistant' and m.get('tool_calls'):
                # 1. Register pending tool calls (assistant proposes tool calls)
                for call in m['tool_calls']:
                    call_id = call['id']
                    name = call['function']['name']
                    args = call['function']['arguments']
                    self._pending[call_id] = {'name': name, 'args': args}
                    logging.info(f'🛠️  Registered pending tool call with id {call_id}: {name}({args})')
            elif role == 'tool':
                call_id = m['tool_call_id']
                content = m['content']
                try:
                    result = json.loads(content)
                except Exception:
                    result = content

                # 3. Check if the result is an error or warning
                is_error = isinstance(result, str) and result.strip().startswith('Error:')
                is_warning = isinstance(result, str) and result.strip().startswith('Warning:')

                if call_id in self._pending:
                    info = self._pending.pop(call_id)
                    # 1. Add node for each tool call result
                    action = FrankensteinAction(id=call_id, action=info['name'], **info['args'])
                    action.result = result
                    self.actions[call_id] = action
                    # Use formatted args for logging
                    formatted_args = self._format_args(action.kwargs)
                    self.add_node(call_id, label=action.action, args=action.kwargs, result=action.result)
                    logging.info(f'🧱 Added node for action with id {call_id}:')
                    logging.info(f'    🔗 Name: {action.action}')
                    logging.info(f'    🔍 Args: {action.kwargs}')
                    logging.info(f'    ➡️ Result: {action.result}')
                    # 2. Track provenance for each output value
                    for v in self._norm(result):
                        self.value_provenance.setdefault(v, []).append(call_id)
                        logging.info(f"🧬 Provenance: output '{v}' produced by {call_id}")

                    # 5a. Special case: propagate indicator names/ids for search_for_indicator_codes
                    if action.action == 'search_for_indicator_codes' and isinstance(result, list):
                        for item in result:
                            if isinstance(item, dict):
                                name = item.get('name')
                                id_ = item.get('id')
                                if name:
                                    self.value_provenance.setdefault(name, []).append(call_id)
                                if id_:
                                    self.value_provenance.setdefault(id_, []).append(call_id)
                        self._search_results_by_node[call_id] = result
                        logging.info(f'🔗 Stored search_for_indicator_codes result for node {call_id}')
                    # 5b. Special case: track all get_country_codes_in_region results
                    if action.action == 'get_country_codes_in_region' and isinstance(result, list):
                        for code in result:
                            if isinstance(code, dict):
                                code_str = str(code.get('id') or code.get('code') or code.get('country_code') or code)
                            else:
                                code_str = str(code)
                            self._country_codes_by_node.setdefault(code_str, []).append(call_id)
                        logging.info(f'🌏 Tracked country codes for node {call_id}: {result}')

                    # 3. Add error node and edge if needed
                    if is_error:
                        if self._error_node_id is None:
                            self._error_node_id = '__error__'
                            self.add_node(self._error_node_id, label='Error', type='error')
                        self.add_edge(call_id, self._error_node_id, label='error')
                        logging.info(f'🚨 Added edge from {call_id} to error node')
                    # 4. Add warning node and edge if needed
                    elif is_warning:
                        if self._warning_node_id is None:
                            self._warning_node_id = '__warning__'
                            self.add_node(self._warning_node_id, label='Warning', type='warning')
                        self.add_edge(call_id, self._warning_node_id, label='warning')
                        logging.info(f'⚠️ Added edge from {call_id} to warning node')

    def _add_edges(
        self,
    ) -> None:
        """Pass 2: Add edges between nodes.

        This method processes the actions and connects them based on their arguments and results,
        using heuristics to conditionally connect nodes of different labels.

        Edges are added based on the following conditions:
        1. Origin node matches action arguments (e.g., slot_values).
            a. Adds edge if `get_indicator_code_from_name` has an `indicator_name` argument matching `property_original`.
            b. Adds edge if `get_country_code_from_name` has a `country_name` argument matching `subject_name`.
        2. A produced value matches an argument in a subsequent action.
        3. A word or phrase from the NLQ matches keywords in `search_for_indicator_codes`.
        4. A `get_indicator_code_from_name` argument matches any `indicator_name` produced from `search_for_indicator_codes`.
        5. An `indicator_code` argument in a `retrieve_value` call matches any `indicator_code` produced from `search_for_indicator_codes`.
        6. If a node's result is an error or warning, add an edge to the generic error/warning node (if not already present).

        """
        for tgt_id, action in self.actions.items():
            formatted_args = self._format_args(action.kwargs)
            tgt_label = f'{action.action}({formatted_args})'
            logging.info(f'➡️  Processing edges for node: {tgt_label}')
            for arg_key, arg_val in action.kwargs.items():
                # --- NEW: For lists, preserve index for each value ---
                normed_vals = self._norm(arg_val)
                # For lists, we want to match each value in order, and allow multiple edges for repeated values.
                used_src_ids = set()
                for idx, val in enumerate(normed_vals):
                    # 1. Heuristic: origin node matches action arguments
                    if (arg_key, val) in self.origin_values:
                        self.add_edge(self.origin_node_id, tgt_id, label=f'{arg_key}={val}')
                        logging.info(f'🌱 Question({self.origin_node_id}) --[{arg_key}="{val}"]--> {tgt_label}')
                        continue

                    # 1a. Heuristic: slot_values match for get_indicator_code_from_name
                    if (
                        action.action == 'get_indicator_code_from_name'
                        and arg_key == 'indicator_name'
                        and ('property_original', val) in self.origin_values
                    ):
                        self.add_edge(self.origin_node_id, tgt_id, label=f'property_original={val}')
                        logging.info(f'🌱 Question({self.origin_node_id}) --[property_original="{val}"]--> {tgt_label}')
                        continue

                    # 1b. Heuristic: subject_name match for get_country_code_from_name
                    if (
                        action.action == 'get_country_code_from_name'
                        and arg_key == 'country_name'
                        and ('subject_name', val) in self.origin_values
                    ):
                        self.add_edge(self.origin_node_id, tgt_id, label=f'subject_name={val}')
                        logging.info(f'🌱 Question({self.origin_node_id}) --[subject_name="{val}"]--> {tgt_label}')
                        continue

                    # 2. Heuristic: produced value matches argument in subsequent action
                    # --- MODIFIED: allow multiple edges for repeated values ---
                    src_ids = self.value_provenance.get(val, [])
                    # Only consider src_ids that are not tgt_id and not already used for this argument position
                    for src_id in reversed(src_ids):
                        if src_id != tgt_id and src_id not in used_src_ids:
                            src_action = self.actions[src_id]
                            src_label = f'{src_action.action}({self._format_args(src_action.kwargs)})'
                            logging.info(f'🔄 {src_label} --[{arg_key}="{val}"]--> {tgt_label}')
                            self.add_edge(src_id, tgt_id, label=f'{arg_key}={val}')
                            used_src_ids.add(src_id)
                            break
                    # If no unused src_id is found, do nothing (prevents duplicate edges from same src to same tgt for same value)

            # 3. Heuristic: check for NLQ keywords in search_for_indicator_codes and get_indicator_code_from_name
            if self.question:
                # For search_for_indicator_codes: check keywords
                if action.action == 'search_for_indicator_codes' and 'keywords' in action.kwargs:
                    keywords = action.kwargs['keywords']
                    if isinstance(keywords, str):
                        keywords = [keywords]
                    keyword_words = set()
                    for kw in keywords:
                        kw_clean = str(kw).lower().translate(str.maketrans('', '', string.punctuation))
                        keyword_words.update(kw_clean.split())
                    overlap = self._question_words & keyword_words
                    if overlap:
                        self.add_edge(self.origin_node_id, tgt_id, label=f'NLQ→keywords: {"/".join(sorted(overlap))}')
                        logging.info(
                            f'💡 Question({self.origin_node_id}) --[keywords="{"/".join(sorted(overlap))}"]--> {tgt_label}'
                        )
                # For get_indicator_code_from_name: check indicator_name for phrases from NLQ
                if action.action == 'get_indicator_code_from_name' and 'indicator_name' in action.kwargs:
                    indicator_name = (
                        str(action.kwargs['indicator_name']).lower().translate(str.maketrans('', '', string.punctuation))
                    )
                    overlap = set()
                    indicator_words = set(indicator_name.split())
                    overlap |= self._question_words & indicator_words
                    q_tokens = self.question.lower().translate(str.maketrans('', '', string.punctuation)).split()
                    for n in range(2, min(6, len(q_tokens) + 1)):
                        for i in range(len(q_tokens) - n + 1):
                            phrase = ' '.join(q_tokens[i : i + n])
                            if phrase in indicator_name:
                                overlap.add(phrase)
                    if overlap:
                        self.add_edge(self.origin_node_id, tgt_id, label=f'keywords="{"/".join(sorted(overlap))}"')
                        logging.info(
                            f'💡 Question({self.origin_node_id}) --[keywords="{"/".join(sorted(overlap))}"]--> {tgt_label}'
                        )

            # 4. Heuristic: search_for_indicator_codes results match get_indicator_code_from_name
            if action.action == 'get_indicator_code_from_name' and 'indicator_name' in action.kwargs:
                indicator_name = str(action.kwargs['indicator_name']).strip().lower()
                for src_id, search_results in self._search_results_by_node.items():
                    if not isinstance(search_results, list):
                        continue
                    for item in search_results:
                        if not isinstance(item, dict):
                            continue
                        candidate = str(item.get('indicator_name', '')).strip().lower()
                        if indicator_name == candidate and src_id != tgt_id:
                            src_action = self.actions[src_id]
                            src_label = f'{src_action.action}({src_action.kwargs})'
                            logging.info(f'🔗 {src_label} --[indicator_name="{candidate}"]--> {tgt_label}')
                            self.add_edge(src_id, tgt_id, label='indicator_name match')
                            break

            # 5. Heuristic: retrieve_value with indicator_code matches search_for_indicator_codes
            if action.action == 'retrieve_value' and 'indicator_code' in action.kwargs:
                indicator_code = str(action.kwargs['indicator_code']).strip().lower()
                for code, src_ids in self._country_codes_by_node.items():
                    if indicator_code == code:
                        for src_id in src_ids:
                            if src_id != tgt_id:
                                src_action = self.actions[src_id]
                                src_label = f'{src_action.action}({src_action.kwargs})'
                                logging.info(f'🔗 {src_label} --[indicator_code="{code}"]--> {tgt_label}')
                                self.add_edge(src_id, tgt_id, label='indicator_code match')
                                break

            # 6. Add error/warning edge if not already present (for completeness)
            result = getattr(action, 'result', None)
            if isinstance(result, str):
                if result.strip().startswith('Error:') and self._error_node_id:
                    if not self.has_edge(tgt_id, self._error_node_id):
                        self.add_edge(tgt_id, self._error_node_id, label='error')
                        logging.info(f'🚨 (edges) Added edge from {tgt_id} to error node')
                elif result.strip().startswith('Warning:') and self._warning_node_id:
                    if not self.has_edge(tgt_id, self._warning_node_id):
                        self.add_edge(tgt_id, self._warning_node_id, label='warning')
                        logging.info(f'⚠️ (edges) Added edge from {tgt_id} to warning node')

    # ---------- visual helper --------------------------------------------
    def draw_pretty(self, pos='tree'):
        pos = self.compute_tree_layout() if pos == 'tree' else nx.shell_layout(self)

        # Compute bounds for all node positions
        xs = [x for x, y in pos.values()]
        ys = [y for x, y in pos.values()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Padding for the plot area
        pad_x = 2.5
        pad_y = 1.5

        fig, ax = plt.subplots(figsize=(14, 8))
        ax.set_aspect('equal')
        ax.axis('off')

        # Set axis limits to fit all nodes with padding
        ax.set_xlim(min_x - pad_x, max_x + pad_x)
        ax.set_ylim(min_y - pad_y, max_y + pad_y)

        # Styling config
        box_width = 2.6
        box_height = 1.0
        font_size = 4
        padding = 0.1

        for node, (x, y) in pos.items():
            data = self.nodes[node]
            is_q = data.get('type') == 'question_param'

            # Build label content
            if is_q:
                label = data['label']
                lines = [label]
            else:
                fn = data.get('label', '')
                args = data.get('args', {})
                result = data.get('result', '')
                arg_lines = [self._format_args(args)] if args else []
                lines = [f'{fn}', *arg_lines, f'→ {result}']

            # Draw box
            box = FancyBboxPatch(
                (x - box_width / 2, y - box_height / 2),
                box_width,
                box_height,
                boxstyle='round,pad=0.02',
                edgecolor='black',
                facecolor='#e0f0ff' if not is_q else '#f5f5dc',
                linewidth=1.5,
            )
            ax.add_patch(box)

            # Draw multiline text
            for i, line in enumerate(lines):
                fontsize = font_size + 1 if i == 0 and not is_q else font_size
                weight = 'bold' if i == 0 and not is_q else 'normal'
                ax.text(
                    x, y + 0.25 - i * 0.25, line, ha='center', va='center', fontsize=fontsize, weight=weight, family='monospace'
                )

        # Draw edges
        for src, tgt, data in self.edges(data=True):
            x0, y0 = pos[src]
            x1, y1 = pos[tgt]
            ax.annotate('', xy=(x1, y1), xytext=(x0, y0), arrowprops={'arrowstyle': '->', 'lw': 1, 'color': 'gray'})

            # Optional edge label
            label = data.get('label')
            if label:
                mid_x = (x0 + x1) / 2
                mid_y = (y0 + y1) / 2
                ax.text(mid_x, mid_y + 0.1, label, fontsize=font_size - 1, color='darkgray', ha='center')

        plt.title('Frankenstein Tool Call Graph', fontsize=12)
        plt.tight_layout()
        plt.show()

    def draw(self, layout='tree'):
        def fmt(name, args=None, node_data=None):
            if args is None:
                return name
            short = self._format_args(args)
            # Always get result from node_data if available
            result = ''
            if node_data is not None:
                result_val = node_data.get('result', '')
                if isinstance(result_val, list):
                    result = ', '.join(str(r)[:17] + '…' if len(str(r)) > 20 else str(r) for r in result_val)
                elif isinstance(result_val, dict):
                    result = ', '.join(f'{k}={str(v)[:17]}…' if len(str(v)) > 20 else f'{k}={v}' for k, v in result_val.items())
                else:
                    result = str(result_val)[:17] + '…' if len(str(result_val)) > 20 else str(result_val)
            # Always show three lines: name, args, result
            return f'{name}\n{short}\n{result}'

        labels = {}
        for n, d in self.nodes(data=True):
            if d.get('type') == 'question_param':
                labels[n] = d['label']
            else:
                labels[n] = fmt(d['label'], d.get('args'), d)

        pos = self.compute_tree_layout() if layout == 'tree' else nx.random_layout(self)
        plt.figure(figsize=(13, 8))
        nx.draw(self, pos, node_size=3000, node_color='lightblue', with_labels=False, arrows=True, edge_color='gray')
        nx.draw_networkx_labels(self, pos, labels, font_size=8)
        nx.draw_networkx_edge_labels(self, pos, edge_labels=nx.get_edge_attributes(self, 'label'), font_size=7)
        plt.title('Frankenstein Tool-Call Graph')
        plt.axis('off')
        # plt.tight_layout()
        plt.show()


if __name__ == '__main__':
    FORMAT = '%(message)s'
    logging.basicConfig(level=logging.DEBUG, format=FORMAT, datefmt='[%X]', handlers=[RichHandler()])

    df = pd.read_json('eval/runs/gpt-4o-mini_answerable-full.jsonl', orient='records', lines=True)

    G = FrankensteinGraph(df.iloc[3])
    G.draw(layout='shell')
