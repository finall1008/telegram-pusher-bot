from __future__ import annotations

import json
import weakref

from weakref import ReferenceType
from typing import *
from inspect import ismethod
from warnings import warn
from functools import reduce
from os import PathLike
from os.path import abspath
from collections.abc import Iterable as IterableType


__all__ = (
    'indent',
    'MetaConfig',
    'BaseConfig',
    'Config',
    'File',
    'User',
    'user_format',
    'ImplementWarning'
)

# For file-like type hint
File = Union[str, bytes, PathLike, int]

# For user
User = Union[int, str]


def indent(iterable: IterableType, indent: int = 4, breakline: str = '\n', stringfier: Callable[[Any], str] = str) -> str:
    return ''.join(map(lambda obj: breakline+indent*' '+stringfier(obj), iterable))


def user_format(user: Union[str, int, Any]):
    if isinstance(user, str):
        return user if user.startswith('@') else f"@{user}"
    else:
        return user


class ImplementWarning(UserWarning):
    pass


class MetaConfig(type):
    __configs: Dict[str, ReferenceType[MetaConfig]] = dict()

    @ classmethod
    def configs(mcls) -> Dict[str, ReferenceType[MetaConfig]]:
        return dict(mcls.__configs)

    def __new__(mcls, name, bases, namespace, **kwargs):
        namespace['_items_name'] = frozenset(
            name for name, value in namespace.items()
            if mcls.is_item(name, value)
        )
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        #cls.__init_subclass__(**kwargs)
        mcls.__configs[cls.__qualname__] = weakref.ref(cls)
        weakref.finalize(cls, lambda: mcls.__configs.pop(cls.__qualname__))
        return cls

    @ staticmethod
    def is_item(name: str, value: Any) -> bool:
        return not (
            name.startswith('__')
            or name.startswith('_')
            or ismethod(value)
            or isinstance(value, (classmethod, staticmethod))
        )

    def __str__(self, *args, **kwargs):
        return self.__str__(self, *args, **kwargs)

    def __repr__(self, *args, **kwargs):
        return self.__repr__(self, *args, **kwargs)

    def __iter__(self) -> Iterable[str]:
        for name in self._items_name:
            yield name

    def __len__(self) -> int:
        return len(self._items_name)

    def keys(self) -> FrozenSet[str]:
        return frozenset(self._items_name)

    def values(self) -> Iterable[Any]:
        for name in self:
            yield self[name]

    def items(self) -> Iterable[Tuple[str, Any]]:
        for name in self:
            yield name, self[name]

    def all_keys(self) -> Iterable[str]:
        for name, value in self.__dict__.items():
            if self.is_item(name, value):
                yield name

    def all_values(self) -> Iterable[Any]:
        for name, value in self.__dict__.items():
            if self.is_item(name, value):
                yield name, value

    def all_items(self) -> Iterable[Tuple[str, _T]]:
        for name, value in self.__dict__.items():
            if self.is_item(name, value):
                yield name, value

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        try:
            return self[key]
        except KeyError:
            if default:
                return default
            else:
                raise KeyError(f"{self.__qualname__} does not have an registered item named {name}")

    def __setattr__(self, name, value):
        original_type = type(self.__dict__.get(name, None))
        if name in self.keys() and not isinstance(value, original_type):
            try:
                value = original_type(value)
            except:
                raise ValueError(f"Trying to assign {value!r} to {self.__qualname__}.{name}, which is of type {original_type}")
        super().__setattr__(name, value)

    def __delattr__(self, name):
        raise AttributeError(f"Attribute {name!r} of class {self.__qualname__} is read-only")

    def __getitem__(self, key: str) -> Any:
        if not isinstance(key, str):
            raise TypeError(f"Config index must be str, not {type(key)}")
        elif key in self.keys():
            return self.__dict__[key]
        else:
            raise KeyError(f"{self.__qualname__} does not have an registered item named {key}")

    def __contains__(self, name: str) -> bool:
        return name in self._items_name


class BaseConfig(metaclass=MetaConfig):
    __registered: Dict[str, Dict[MetaConfig, FrozenSet[str]]] = {}

    def __str__(cls, **kwargs):
        return json.dumps(cls.json(), **kwargs)

    def __repr__(cls):
        return cls.__str__(cls)

    @ classmethod
    def json(cls) -> Dict[str, Any]:
        return {
            name: value
            for name, value in cls.items()
        }

    @ classmethod
    def _from_json(cls, json_obj: Optional[Dict[str, Any]]):
        if json_obj is None:
            return
        for name, value in cls.items():
            try:
                setattr(cls, *cls._check(name, json_obj[name]))
            except KeyError as keyerr:
                try:
                    hint_types = cls.__annotations__[name].__args__
                except Exception:
                    hint_types = ()
                if type(None) in hint_types:
                    setattr(cls, *cls._check(name, value))
                else:
                    raise LookupError(f"{name!r} is not in the given config.") from keyerr

    @ classmethod
    def from_json(cls, json_obj: Optional[Dict[str, Any]]):
        cls._from_json(json_obj)

    @ classmethod
    def from_file(cls, path: File):
        new_path = abspath(str(path))
        registered = cls.__registered

        try:
            path_dict = registered[new_path]
        except KeyError:
            path_dict = registered[new_path] = dict()
        try:
            old_path = abspath(str(cls.__dict__[f'_config_file']))
        except KeyError:
            path_dict[cls] = cls.keys()
        else:
            if old_path == new_path:
                pass
            else:
                intersect = reduce(frozenset.union, map(lambda fs: cls.keys().intersect(fs), registered[new_path].values()), frozenset())
                if not intersect:
                    path_dict[cls] = registered[old_path].pop(cls)
                    if not registered[old_path]:
                        registered.pop(old_path)
                else:
                    raise ValueError(
                        f"Referring to existed config item{'s' if len(intersect) > 1 else ''} "
                        f"{' '.join(map(repr, intersect))} in class {name}."
                    )

        with open(path, 'a+'):
            pass
        with open(path, 'r', encoding='utf8') as file:
            try:
                data = json.load(file)
            except:
                data =  None
        cls.from_json(data)
        cls._config_file = path
        cls.dump(data=data)

    @ classmethod
    def dump(cls, path: Optional[File] = None, *, data: Dict[str, Any] = None):
        if path is None:
            try:
                path = cls._config_file
            except:
                raise ValueError(f"No file path given while {cls.__qualname__!r} is not initiated with a config file.")
        if data is None:
            with open(path, 'r') as file:
                try:
                    data = json.load(file)
                except json.JSONDecodeError:
                    data = {}
        data.update(cls.json())
        with open(path, 'w', encoding='utf8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)

    @ classmethod
    def _check(cls, _attr_name: str, _attr_value: Any) -> Tuple[str, Any]:
        warn(f"Implement _check as classmethod in subclass {cls.__qualname__!r}", ImplementWarning)
        return _attr_name, _attr_value

    @ classmethod
    def reload(cls, config_name: Optional[File] = None):
        cls.from_file(config_name if config_name else cls._config_file)

    @ classmethod # To be clearer
    def __init_subclass__(
            cls, /,
            config_file: Optional[File] = None,
            config_json: Optional[Dict[str, Any]] = None,
            **kwargs):

        super().__init_subclass__()
        if not (config_file is None or config_json is None):
            raise ValueError("only one of the parameters shall be specified.")
        elif config_file is not None:
            cls.from_file(config_file)
        elif config_json is not None:
            cls.from_json(config_json)


class Config(BaseConfig, config_file="push_config.json"):
    tags: Optional[Tuple[str]] = ()
    targets: Tuple[User] = ()
    token: str = ''
    watchers: Tuple[User] = ()
    forward: Dict[User, List[User]] = {}

    def __repr__(cls):
        return (
            "<Config:\n"
            "tags:{}\n"
            "targets:{}\n"
            "token:{}\n"
            "watchers:{}\n"
            "forward:{}\n"
            ">"
        ).format(
            indent(cls.tags),
            indent(cls.targets),
            cls.token,
            indent(cls.watchers),
            indent(cls.forward.items(), stringfier=lambda t: f"from: {t[0]!s} to:{indent(t[1], indent=8)}")
        )

    def __str__(cls):
        return super().__str__(cls, ensure_ascii=False, indent=4)

    @ classmethod
    def _check(cls, _attr_name: str, _attr_value: Any) -> Tuple[str, Any]:
        if _attr_name in ('targets', 'watchers'):
            return _attr_name, tuple(user_format(user) for user in _attr_value)
        elif _attr_name == 'forward':
            return _attr_name, {user_format(_from): [user_format(to) for to in tos] for _from, tos in _attr_value.items()}
        else:
            return _attr_name, _attr_value
