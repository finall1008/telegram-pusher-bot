import re
import os.path as path

from typing import (
    Optional,
    Union,
    Any,
    Dict,
    List,
    Callable,
    Protocol,
    TypeVar,
    Tuple,
)
from enum import Enum

from utils import Config, indent
from utils.push import Message


curdir = path.dirname(__file__)
config_name = "auto_select.json"
absolute_config_path = path.join(curdir, config_name)


AnyCallable = Callable[..., Any]
ArgT = TypeVar('ArgT')
RetT = TypeVar('RetT')

# Type-check only
class Handler(Protocol):
    def __call__(self, subject: ArgT, **kwargs) -> Tuple[bool, RetT]:
        raise NotImplementedError()


class Rule(dict):
    __handler_map: Dict[str, Handler] = {}

    @ classmethod
    def register(cls, _type: str, handler: Handler):
        cls.__handler_map[_type] = handler

    def __init__(self, type: str, **kwargs):
        dict.__init__(self, type=type, **kwargs)

    def exert(self, subject: ArgT) -> Tuple[bool, RetT]:
        handler = self.__handler_map[self.pop['type']]
        return handler(subject, **self)


# * Unfinished
# Each rule set is made up of several groups.
# The designed logic is to traverse each rule set, exerting every rule in the same group on the given subject until a rule returns False.
# In this scenario other rules in the same group would still be executed.
class AutoSelect(Config, config_file=absolute_config_path):
    rule_for_tags: Optional[List[List[Rule]]] = [] # A rule set
    rule_for_targets: Optional[List[List[Rule]]] = []

    @ classmethod
    def _check(self, _attr_name: str, _attr_value: Any):
        return (
            _attr_name,
            [
                [Rule(**value)]
                if isinstance(value, dict)
                else [Rule(**rule) for rule in value]
                for value in _attr_value
            ]
        )

    @ classmethod
    def exert(cls, message: Message) -> None:
        pass

    def __repr__(self):
        return "<AutoSelect:\nrule_for_tags:{}\nrule_for_targets:{}\n>".format(
            indent(self.rule_for_tags),
            indent(self.rule_for_targets)
        )