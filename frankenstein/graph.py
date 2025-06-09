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
        question = row.get('question', None)
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

    def compute_tree_layout(
        self,
        root: str = 'question_root',
    ) -> Dict[str, tuple[float, float]]:
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
    def _build_graph(self, messages: List[Dict[str, Any]]):
        logging.info('🧩 Starting graph build process.')
        pending: dict[str, Dict[str, Any]] = {}

        # Prepare for NLQ-argument heuristic
        question_words = set()
        if self.question:
            q = self.question.lower().translate(str.maketrans('', '', string.punctuation))
            question_words = set(q.split())
            logging.info(f'🔍 Extracted question words: {question_words}')

        # Track search_for_indicator_codes results for later matching
        search_results_by_node = {}
        # Track get_country_codes_in_region results for robust country code provenance
        country_codes_by_node = {}

        # pass 1: create FrankensteinAction objects and graph nodes ----------
        logging.info('⚙️  Pass 1: Creating FrankensteinAction objects and graph nodes.')
        for m in messages:
            role = m.get('role')
            logging.info(f'👤 Processing message with role: {role}')

            # assistant proposes tool calls
            if role == 'assistant' and m.get('tool_calls'):
                for call in m['tool_calls']:
                    call_id = call['id']
                    name = call['function']['name']
                    args = call['function']['arguments']
                    pending[call_id] = {'name': name, 'args': args}
                    logging.info(f'🛠️  Registered pending tool call with id {call_id}: {name}({args})')

            # tool returns a result
            elif role == 'tool':
                call_id = m['tool_call_id']
                content = m['content']
                try:
                    result = json.loads(content)
                except Exception:
                    result = content

                if call_id in pending:
                    info = pending.pop(call_id)
                    action = FrankensteinAction(id=call_id, action=info['name'], **info['args'])
                    action.result = result

                    # store
                    self.actions[call_id] = action
                    self.add_node(call_id, label=action.action, args=action.kwargs, result=action.result)
                    logging.info(f'🧱 Added node for action with id {call_id}: {action.action}({action.kwargs})')

                    # provenance for result values (general)
                    for v in self._norm(result):
                        self.value_provenance.setdefault(v, []).append(call_id)
                        logging.info(f"🧬 Provenance: output '{v}' produced by {call_id}")

                    # special case: semantic propagation from search_for_indicator_codes
                    if action.action == 'search_for_indicator_codes' and isinstance(result, list):
                        for item in result:
                            if isinstance(item, dict):
                                name = item.get('name')
                                id_ = item.get('id')
                                if name:
                                    self.value_provenance.setdefault(name, []).append(call_id)
                                if id_:
                                    self.value_provenance.setdefault(id_, []).append(call_id)
                        search_results_by_node[call_id] = result
                        logging.info(f'🔗 Stored search_for_indicator_codes result for node {call_id}')

                    # robust: track all get_country_codes_in_region results
                    if action.action == 'get_country_codes_in_region' and isinstance(result, list):
                        for code in result:
                            if isinstance(code, dict):
                                code_str = str(code.get('id') or code.get('code') or code.get('country_code') or code)
                            else:
                                code_str = str(code)
                            country_codes_by_node.setdefault(code_str, []).append(call_id)
                        logging.info(f'🌏 Tracked country codes for node {call_id}: {result}')

        # pass 2: add edges (origins → tool inputs or outputs → inputs) ------
        logging.info('🔗 Pass 2: Adding edges between nodes.')
        for tgt_id, action in self.actions.items():
            tgt_label = f'{action.action}({action.kwargs})'
            logging.info(f'➡️  Processing edges for node: {tgt_label}')
            for arg_key, arg_val in action.kwargs.items():
                for val in self._norm(arg_val):
                    # 1️⃣ origin node match
                    if (arg_key, val) in self.origin_values:
                        self.add_edge(self.origin_node_id, tgt_id, label=f'{arg_key}={val}')
                        logging.info(f'🌱 Structured NLQ({self.origin_node_id}) --[{arg_key}="{val}"]--> {tgt_label}')
                        continue

                    # 1b️⃣ slot_values original indicator name match for get_indicator_code_from_name
                    # If the argument to get_indicator_code_from_name matches the original indicator name in slot_values, add an edge
                    if (
                        action.action == 'get_indicator_code_from_name'
                        and arg_key == 'indicator_name'
                        and 'property_original' in self.origin_values
                        and val == list(self.origin_values)[0][1]  # property_original value
                    ):
                        self.add_edge(self.origin_node_id, tgt_id, label=f'property_original={val}')
                        logging.info(f'🌱 Structured NLQ({self.origin_node_id}) --[property_original="{val}"]--> {tgt_label}')
                        continue

                    # 2️⃣ produced value match (general)
                    for src_id in reversed(self.value_provenance.get(val, [])):
                        if src_id != tgt_id:
                            src_action = self.actions[src_id]
                            src_label = f'{src_action.action}({src_action.kwargs})'
                            logging.info(f'🔄 {src_label} --[{arg_key}="{val}"]--> {tgt_label}')
                            self.add_edge(src_id, tgt_id, label=f'{arg_key}={val}')
                            break

            # 3️⃣ Heuristic: NLQ word in search_for_indicator_codes argument
            if (
                self.question
                and action.action in ('search_for_indicator_codes', 'get_indicator_code_from_name')
                and 'keywords' in action.kwargs
            ):
                keywords = action.kwargs['keywords']
                if isinstance(keywords, str):
                    keywords = [keywords]
                keyword_words = set()
                for kw in keywords:
                    kw_clean = str(kw).lower().translate(str.maketrans('', '', string.punctuation))
                    keyword_words.update(kw_clean.split())
                overlap = question_words & keyword_words
                if overlap:
                    self.add_edge(self.origin_node_id, tgt_id, label=f'NLQ→keywords: {"/".join(sorted(overlap))}')
                    logging.info(
                        f'💡 Structured NLQ({self.origin_node_id}) --[NLQ→keywords: {"/".join(sorted(overlap))}]--> {tgt_label}'
                    )

            # 4️⃣ Heuristic: get_indicator_code_from_name argument matches indicator_name from search_for_indicator_codes
            if action.action == 'get_indicator_code_from_name' and 'indicator_name' in action.kwargs:
                indicator_name = str(action.kwargs['indicator_name']).strip().lower()
                for src_id, search_results in search_results_by_node.items():
                    if not isinstance(search_results, list):
                        continue
                    for item in search_results:
                        if not isinstance(item, dict):
                            continue
                        candidate = str(item.get('indicator_name', '')).strip().lower()
                        if indicator_name == candidate and src_id != tgt_id:
                            src_action = self.actions[src_id]
                            src_label = f'{src_action.action}({src_action.kwargs})'
                            logging.info(f'🔗 {src_label} --[indicator_name match]--> {tgt_label}')
                            self.add_edge(src_id, tgt_id, label='indicator_name match')
                            break

        # --- Report on provenance and pending after graph build -------------
        if pending:
            logging.info(f'🗂️ Pending tool calls left after graph build: {list(pending.keys())}')
        else:
            logging.info('✅ No pending tool calls left after graph build.')

        unused_provenance = {
            k: v for k, v in self.value_provenance.items() if len(v) > 0 and not any(self.has_node(n) for n in v)
        }
        if unused_provenance:
            logging.info(f'🧾 Unused provenance values (not mapped to any node): {unused_provenance}')
        else:
            logging.info('✅ All provenance values mapped to nodes.')

        # Optionally, show all provenance mapping for debugging
        logging.debug(f'📚 Full value_provenance mapping: {self.value_provenance}')

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
                arg_lines = [f'{k} = {v}' for k, v in args.items()]
                lines = [f'{fn}'] + arg_lines + [f'→ {result}']

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
            ax.annotate('', xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle='->', lw=1, color='gray'))

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
        def fmt(name, args=None):
            if args is None:
                return name
            short = ', '.join(f'{k}={str(v)[:17]}…' if len(str(v)) > 20 else f'{k}={v}' for k, v in args.items())
            # also get result and display it
            if 'result' in args:
                result = args['result']
                if isinstance(result, list):
                    result = ', '.join(str(r)[:17] + '…' if len(str(r)) > 20 else str(r) for r in result)
                elif isinstance(result, dict):
                    result = ', '.join(f'{k}={str(v)[:17]}…' if len(str(v)) > 20 else f'{k}={v}' for k, v in result.items())
                else:
                    result = str(result)[:17] + '…' if len(str(result)) > 20 else str(result)
            else:
                result = ''
            return f'{name}\n{short}\n{result}'

        labels = {}
        for n, d in self.nodes(data=True):
            if d.get('type') == 'question_param':
                labels[n] = d['label']
            else:
                labels[n] = fmt(d['label'], d.get('args'))

        pos = self.compute_tree_layout() if layout == 'tree' else nx.shell_layout(self)
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

    graph = FrankensteinGraph(df.iloc[1])
    graph.draw('shell')
