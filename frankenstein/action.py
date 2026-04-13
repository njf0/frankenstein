"""Action wrapper for executing Frankenstein tools with structured arguments."""

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
        action : str | None
            The action to perform.
        id : str | None
            Optional unique ID for tracking this action.
        **kwargs
            Keyword arguments for the selected tool.

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

    def __repr__(self) -> str:
        """Return a developer-facing representation of the action.

        Returns
        -------
        str
            String representation containing the action name, arguments, result,
            and optional identifier.

        """
        return f'Action(action={self.action}, kwargs={self.kwargs}, result={self.result}, id={self.id})'

    def set_action(
        self,
        action: str,
    ) -> None:
        """Set the action to be performed.

        Parameters
        ----------
        action : str
            Tool name to execute.

        """
        if action not in self.tool_map:
            raise ValueError(f'Action {action} is not supported.')
        self.action = action

    def set_kwargs(
        self,
        **kwargs,
    ) -> None:
        """Set the keyword arguments for the current action.

        Parameters
        ----------
        **kwargs
            Candidate keyword arguments for the selected action. Unexpected
            arguments are discarded.

        """
        if self.action is None:
            raise ValueError('Action must be specified before setting kwargs.')

        self.kwargs = {k: v for k, v in kwargs.items() if k in inspect.signature(self.tool_map[self.action]).parameters}

    def execute(
        self,
        error_handling: str = 'ignore',
    ):
        """Execute the action using the mapped tool.

        Parameters
        ----------
        error_handling : str
            How to handle errors during execution. Options are 'raise' or 'ignore'.
            If 'raise', exceptions will be raised; if 'ignore', the result will be set to None.

        Returns
        -------
        Any
            Tool result, or ``None`` if execution fails and errors are ignored.

        """
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

    def to_dict(self) -> dict:
        """Serialize the action to a dictionary.

        Returns
        -------
        dict
            Dictionary containing the tool name, arguments, result, and ID.

        """
        return {
            'name': self.action,
            'arguments': self.kwargs,
            'result': self.result,
            'id': self.id,
        }

    def to_json(self) -> str:
        """Serialize the action to a JSON string.

        Returns
        -------
        str
            JSON representation of :meth:`to_dict`.

        """
        return json.dumps(self.to_dict())


if __name__ == '__main__':
    # Example usage
    action = FrankensteinAction('add', values=[1, 2, 3])
    print(action.execute())  # Output: 6
    print(action.to_json())  # Output: {"action": "add", "kwargs": {"a": 1, "b": 2, "c": 3}, "results": 6}
