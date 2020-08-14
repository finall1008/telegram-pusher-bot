import json

from typing import (
    Union,
    Final,
    Dict,
    Type,
    Callable,
    List,
    Optional,
    Iterable,
    Any,
    Tuple,
    Optional,
    FrozenSet
)
from functools import wraps, reduce, partial, lru_cache
from inspect import ismethod
from mwt import mwt
from telegram import Bot
from telegram.ext import Filters
from collections.abc import Iterable as IterableType

from .timeout_wrapper import *
from .config import *


__all__ = (
    (
        'File',
        'User',
        'get_admin',
        'odd_even',
        'nested_list_map',
        'user_format',
        'get_filter',
        'AbstractConfig',
        'Config',
    )
    + timeout_wrapper.__all__
    + config.__all__
)


# Helper functions
@ mwt(timeout=60*60)
def get_admin(bot: Bot, chat_id: int) -> List[int]:
    return [
        admin.user.id
        for admin in bot.get_chat_administrators(chat_id)
    ]


def odd_even(l: list) -> list:
    if not l: return l
    length = len(l)
    ret = [[l[2*i], l[2*i + 1]] for i in range(length//2)]
    if length % 2: ret.append([l[-1]])
    return ret


def nested_list_map(func, l: list) -> list:
    return [nested_list_map(func, elem) if isinstance(elem, list) else func(elem) for elem in l]


def get_filter(users: Iterable[User]):
    username, chat_id = set(), set()
    for user in users:
        if isinstance(user, str):
            username.add(user)
        elif isinstance(user, int):
            chat_id.add(user)
    return Filters.chat(username=username, allow_empty=True) & Filters.chat(chat_id=chat_id, allow_empty=True)
