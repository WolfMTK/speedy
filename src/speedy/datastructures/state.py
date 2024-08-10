from typing import Any

from speedy.types import StateType


class State:
    """ An object that can be used to store arbitrary state. """

    _state: StateType

    def __init__(self, state: StateType | None = None) -> None:
        if state is None:
            state = {}
        super().__setattr__('_state', state)

    def __setattr__(self, key: Any, value: Any) -> None:
        self._state[key] = value

    def __getattr__(self, key: Any) -> Any:
        try:
            return self._state[key]
        except KeyError as err:
            raise AttributeError from err

    def __delattr__(self, key: Any) -> None:
        try:
            del self._state[key]
        except KeyError as err:
            raise AttributeError from err
