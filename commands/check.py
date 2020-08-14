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
    return "检查所有已选中内容"


@ run_async
def run(update: Update, context: CallbackContext):
    bot = Bot(token=utils.Config.token)
    chat = update.effective_chat
    chat_id = chat.id
    command_message_id = update.effective_message.message_id

    for message_id, message in push.waiting_to_push.items():
        bot.send_message(
            chat_id=chat_id,
            text=str(message),
            reply_to_message_id=message_id,
            disable_web_page_preview=True
        )
    bot.send_message(
        chat_id=chat_id,
        text=f"目前的推送列表内共有 {len(push.waiting_to_push)} 条消息",
        reply_to_message_id=command_message_id
    )
    logger.info(f"确认推送内容")


def register(updater: Updater):
    dp = updater.dispatcher
    bot = updater.bot

    dp.add_handler(CommandHandler(__name__, run, filters=get_filter(bot)))
    # dp.add_handler(CommandHandler(__name__, run, filters=Filters.all)) # DEBUG
