import json
from typing import Any, Dict, List

import networkx as nx

from frankenstein.action import FrankensteinAction  # ← make sure import path is correct


class FrankensteinGraph(nx.DiGraph):
    """Directed acyclic graph of FrankensteinAction tool calls + optional structured-question origin nodes."""

    def __init__(self, messages: List[Dict[str, Any]], question_structure: List[Dict[str, Any]] | None = None):
        super().__init__()
        self.actions: dict[str, FrankensteinAction] = {}
        self.value_provenance: dict[str, List[str]] = {}  # value → list[producer_id]
        self.question_nodes: dict[tuple[str, str], str] = {}  # (key,val) → node_id

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
            label='Structured NLQ',
            type='question_param',
            values=dict(flat_pairs),  # optional metadata
        )

    # ---------- build graph ----------------------------------------------
    def _build_graph(self, messages: List[Dict[str, Any]]):
        pending: dict[str, Dict[str, Any]] = {}

        # pass 1: create FrankensteinAction objects and graph nodes ----------
        for m in messages:
            role = m.get('role')

            # assistant proposes tool calls
            if role == 'assistant' and m.get('tool_calls'):
                for call in m['tool_calls']:
                    call_id = call['id']
                    name = call['function']['name']
                    args = call['function']['arguments']
                    pending[call_id] = {'name': name, 'args': args}

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

                    # provenance for result values (general)
                    for v in self._norm(result):
                        self.value_provenance.setdefault(v, []).append(call_id)

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

        # pass 2: add edges (origins → tool inputs or outputs → inputs) ------
        for tgt_id, action in self.actions.items():
            for arg_key, arg_val in action.kwargs.items():
                for val in self._norm(arg_val):
                    # 1️⃣ origin node match
                    q_node = self.question_nodes.get((arg_key, val))
                    if (arg_key, val) in self.origin_values:
                        self.add_edge(self.origin_node_id, tgt_id, label=f'{arg_key}={val}')
                        continue

                    # 2️⃣ produced value match
                    for src_id in reversed(self.value_provenance.get(val, [])):
                        if src_id != tgt_id:
                            self.add_edge(src_id, tgt_id, label=f'{arg_key}={val}')
                            break

    # ---------- visual helper --------------------------------------------
    def draw(self):
        import matplotlib.pyplot as plt

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

        try:
            pos = nx.bfs_layout(self, 'question_root')
        except nx.exception.NetworkXError:
            pos = nx.shell_layout(self)
        plt.figure(figsize=(13, 8))
        nx.draw(self, pos, node_size=3000, node_color='lightblue', with_labels=False, arrows=True, edge_color='gray')
        nx.draw_networkx_labels(self, pos, labels, font_size=8)
        nx.draw_networkx_edge_labels(self, pos, edge_labels=nx.get_edge_attributes(self, 'label'), font_size=7)
        plt.title('Frankenstein Tool-Call Graph')
        plt.axis('off')
        plt.tight_layout()
        plt.show()


if __name__ == '__main__':
    with open('eval/dumps/2025-06-04 14:38:15.json') as f:
        trace = json.load(f)

    # Structured form of NLQ (your input to seed the graph)
    question_structure = [{'region': 'Melanesia'}, {'year': 2004}]

    G = FrankensteinGraph(trace, question_structure)
    G.draw()
