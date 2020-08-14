import logging

from telegram import Update, Bot
from telegram.ext import (
    Updater,
    CallbackContext,
    CommandHandler,
    Filters,
    run_async,
)
from functools import partial, reduce

import utils
import utils.push as push

from markup import main_buttons


logger = logging.getLogger('push_helper')


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


def describe():
    return "推送所有已选中内容至各自目标"


@ run_async
def run(update: Update, context: CallbackContext):
    editor_bot = Bot(token=utils.Config.token)

    if not push.waiting_to_push :
        update.effective_message.reply_text(text="推送队列为空", quote=True)
        return

    waiting_to_push = dict(push.waiting_to_push)
    push.waiting_to_push.clear() # SaltyFish: My fault.
    logger.info(f"推送全部内容")
    update.effective_message.reply_text(text="开始推送队列中全部内容", quote=True)
    targets_additional, tags_additional = list(), list()
    for arg in context.args:
        if arg[0] == "@":
            targets_additional.append(arg)
        else:
            tags_additional.append(arg)
    for message_id, message in waiting_to_push.items():
        message.push(targets_additional, tags_additional)
        editor_bot.edit_message_reply_markup(
            chat_id=update.effective_chat.id,
            message_id=message_id,
            reply_markup=main_buttons(message_id)
        )


def register(updater: Updater):
    dp = updater.dispatcher
    bot = updater.bot

    dp.add_handler(CommandHandler(__name__, run, filters=get_filter(bot)))
