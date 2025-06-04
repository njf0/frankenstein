import inspect
import json

from frankenstein.tools import arithmetic, data_retrieval, utils


class FrankensteinAction:
    """Class for representing actions (a.k.a tools)."""

    def __init__(
        self,
        action: str | None = None,
        id: str | None = None,
        **kwargs,
    ):
        """Initialize an action.

        Parameters
        ----------
        action: str
            The action to perform.
        id: str
            Optional unique ID for tracking this action.
        kwargs: dict
            The arguments for the action.

        """
        self.id = id
        # Collect all functions from both modules
        tool_map = {}
        for module in (arithmetic, data_retrieval, utils):
            tool_map.update(dict(inspect.getmembers(module, inspect.isfunction)))
        self.tool_map = tool_map

        if isinstance(action, str) and action not in self.tool_map:
            raise ValueError(f'Action {action} is not supported.')

        self.action = action
        self.kwargs = kwargs
        self.result = None

    def __repr__(self):
        """Return the action as a string."""
        return f'Action(action={self.action}, kwargs={self.kwargs}, result={self.result}, id={self.id})'

    def set_action(
        self,
        action: str,
    ) -> None:
        """Set the action to be performed."""
        if action not in self.tool_map:
            raise ValueError(f'Action {action} is not supported.')
        self.action = action

    def set_kwargs(
        self,
        **kwargs,
    ) -> None:
        """Set the keyword arguments for the action."""
        if self.action is None:
            raise ValueError('Action must be specified before setting kwargs.')

        self.kwargs = {k: v for k, v in kwargs.items() if k in inspect.signature(self.tool_map[self.action]).parameters}

    def execute(
        self,
        error_handling: str = 'ignore',
    ):
        """Execute the action using the mapped tool."""
        if self.action is None:
            raise ValueError('Action must be specified with set_action() or during initialization.')

        if not self.kwargs:
            raise ValueError('Keyword arguments must be set with set_kwargs() before executing the action.')

        try:
            tool = self.tool_map[self.action]
            self.result = tool(**self.kwargs)
        except Exception:
            self.result = None
            if error_handling == 'raise':
                raise
            elif error_handling == 'ignore':
                self.result = None

        return self.result

    def to_dict(self):
        """Return the action as a dictionary."""
        return {
            'name': self.action,
            'arguments': self.kwargs,
            'result': self.result,
            'id': self.id,
        }

    def to_json(self):
        """Export the action as a JSON string."""
        return json.dumps(self.to_dict())


if __name__ == '__main__':
    # Example usage
    action = FrankensteinAction('add', values=[1, 2, 3])
    print(action.execute())  # Output: 6
    print(action.to_json())  # Output: {"action": "add", "kwargs": {"a": 1, "b": 2, "c": 3}, "results": 6}
