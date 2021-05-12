import logging

from telegram.ext import (
    CommandHandler,
    CallbackContext,
    Filters,
    Updater,
    run_async,
)
from typing import List, Any, Callable, Sequence
from telegram import Update, Bot
from functools import partial, reduce

import utils

from utils import user_format


logger = logging.getLogger('push_helper')


def describe():
    return "将当前监视器群组在 config 中的的记录方式改为 ID"


def get_filter(bot: Bot):
    return (
        utils.get_filter(utils.Config.watchers)
        & Filters.user(
            user_id=reduce(
                frozenset.union, map(
                    frozenset, map(
                        partial(utils.get_admin, bot), utils.Config.watchers
                    )
                )
            )
        )
    )


def manipulated_if(seq: Sequence[Any], pred: Callable[[Any], Any], manip: Callable[[Any], Any]) -> Sequence[Any]:
    return type(seq)(manip(x) if pred(x) else x for x in seq)


def manipulated(seq: Sequence[Any], value: Any, manip: Callable[[Any], Any]) -> Sequence[Any]:
    return manipulated_if(seq, lambda x: x == value, manip)


def replaced_if(seq: Sequence[Any], pred: Callable[[Any], Any], new_value: Any) -> Sequence[Any]:
    return manipulated_if(seq, pred, lambda x: new_value)


def replaced(seq: Sequence[Any], value: Any, new_value: Any) -> Sequence[Any]:
    return manipulated_if(seq, lambda x: x == value, lambda x: new_value)


def run(update: Update, context: CallbackContext):
    chat = update.effective_message.chat
    watcher_name = chat.username

    utils.Config.watchers = replaced(
        utils.Config.watchers, user_format(watcher_name), chat.id)
    try:
        utils.Config.dump()
    except ValueError:
        pass

    update.effective_message.reply_text(
        text="成功: 已将此频道/群组的记录方式改为 ID",
        quote=True
    )
    logger.info(f"频道/群组 {watcher_name} 的记录方式改为了 ID: {chat.id}")


def register(updater: Updater):
    dp = updater.dispatcher
    bot = updater.bot

    dp.add_handler(CommandHandler(
        __name__, run, filters=get_filter(bot), run_async=True))
    # dp.add_handler(CommandHandler(__name__, run, filters=Filters.all)) # DEBUG
