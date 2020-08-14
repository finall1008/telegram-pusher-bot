from telegram import Update
from telegram.ext import (
    Updater,
    CallbackContext,
    run_async,
    CommandHandler,
)
from utils import Config
from pkgutil import walk_packages
from types import ModuleType
from typing import Dict

from utils import get_filter


submodules: Dict[str, ModuleType] = {
    module_name: loader.find_module(module_name).load_module(module_name)
    for loader, module_name, is_package in walk_packages(__path__)
}


def describe():
    return "列出所有的指令, 需注意列出的指令在当前的环境内不一定可用"


@ run_async
def run(update: Update, context: CallbackContext):
    update.effective_message.reply_text(
        text="所有指令如下:\n"
            + "\n".join(
                [f"/{command}: {description}"
                for command, description in commands_list]
            ),
        quote=True
    )


commands_list = tuple(
    (name, module.describe())
    for name, module in submodules.items()
) + (
    (__name__, describe()),
)


def register(updater: Updater):
    for module in submodules.values():
        module.register(updater)

    dp = updater.dispatcher
    dp.add_handler(CommandHandler(__name__, run, filters=get_filter(Config.watchers)))
    # dp.add_handler(CommandHandler(__name__, run, filters=Filters.all)) # DEBUG

    updater.bot.set_my_commands(commands_list) # * Unavailable until all commands are implemented (or at least their describe methods return a string with len > 3)