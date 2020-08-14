from telegram.ext import run_async
from utils import (
    MetaConfig,
    timeout,
    WrapType,
)

import utils.push as push


def command(command: str, *args) -> None:
    if command == 'inspect':
        for name in args:
            try:
                config_ref = MetaConfig.configs()[name]
            except KeyError:
                if name == 'waiting_to_push':
                    print(push.waiting_to_push)
                else:
                    print(f"No config named {name!r}")
            else:
                print(repr(config_ref()))
    elif command == 'list':
        for ref in MetaConfig.configs().values():
            print(repr(ref()))
    else:
        print(f"/{command!r} is not a valid command, for now")


@ run_async
def handle(text: str) -> None:
    if text.startswith('/'):
        command(*text.lstrip('/').split(' '))
    else:
        print(text)
