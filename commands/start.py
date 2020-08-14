import logging

from telegram import (
    Update,
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Updater,
    CallbackContext,
    CommandHandler,
    CallbackQueryHandler,
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


def do_you_have_time_markup(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup.from_button(
        InlineKeyboardButton(
            f"请问 {username} 先生您有时间吗",
            callback_data="have_time"
        )
    )


def vtb_suggestion_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup.from_column([
        InlineKeyboardButton("神楽めあ", url="https://space.bilibili.com/349991143/"),
        InlineKeyboardButton("湊あくあ", url="https://space.bilibili.com/375504219/"),
        InlineKeyboardButton("夏色まつり", url="https://space.bilibili.com/336731767")
    ])


def suggest_vtb(update: Update, context: CallbackContext):
    bot = Bot(token=utils.Config.token)
    bot.edit_message_text("请了解一下我们的推：", chat_id=update.effective_chat.id, message_id=update.effective_message.message_id)
    bot.edit_message_reply_markup(chat_id=update.effective_chat.id, message_id=update.effective_message.message_id, reply_markup=vtb_suggestion_markup())


def describe():
    return "用来叫醒 Bot, 实际上并没有什么用处" # DEBUG


@ run_async
def run(update: Update, context: CallbackContext):
    command_message = update.effective_message

    command_message.reply_text(
        text="爷还活着, 大概吧",
        reply_markup=do_you_have_time_markup(f"@{update.effective_user.username}"),
        quote=True
    )


def register(updater: Updater):
    dp = updater.dispatcher
    bot = updater.bot

    dp.add_handler(CommandHandler(__name__, run, filters=get_filter(bot)))
    dp.add_handler(CallbackQueryHandler(suggest_vtb, pattern="have_time"))
    # dp.add_handler(CommandHandler(__name__, run, filters=Filters.all)) # DEBUG
