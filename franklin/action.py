import inspect
import json

from franklin import tools


class FranklinAction:
    """Class for representing actions (a.k.a tools)."""

    def __init__(
        self,
        action: str,
        **kwargs,
    ):
        """Initialize an action.

        Parameters
        ----------
        action: str
            The action to perform.
        kwargs: dict
            The arguments for the action.

        """
        self.tool_map = dict(inspect.getmembers(tools, inspect.isfunction))

        if not isinstance(action, str):
            raise TypeError(f'Action must be a string, got {type(action)}.')

        if action not in self.tool_map:
            raise ValueError(f'Action {action} is not supported.')

        self.action = action
        self.kwargs = kwargs
        self.result = None

    def __repr__(self):
        """Return the action as a string."""
        return f'Action(action={self.action}, kwargs={self.kwargs})'

    def execute(
        self,
        error_handling: str = 'ignore',
    ):
        """Execute the action using the mapped tool."""
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
        }

    def to_json(self):
        """Export the action as a JSON string."""
        return json.dumps(self.to_dict())


if __name__ == '__main__':
    # Example usage
    action = FranklinAction('add', values=[1, 2, 3])
    print(action.execute())  # Output: 6
    print(action.to_json())  # Output: {"action": "add", "kwargs": {"a": 1, "b": 2, "c": 3}, "results": 6}
