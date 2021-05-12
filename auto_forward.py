import logging

from telegram import (
    Bot,
    Message,
    Update,
    ParseMode
)
from telegram.ext import (
    Updater,
    CallbackContext,
    run_async,
    Filters,
    MessageHandler
)

from utils import Config, user_format, get_filter
from utils.push import Message as Msg
from markup import main_buttons, parse_url


logger = logging.getLogger('push_helper')


def auto_forward(update: Update, context: CallbackContext):
    bot = Bot(token=Config.token)

    if update.message == None:
        message = update.channel_post
    else:
        message = update.message
    from_chat = update.effective_chat

    use_push_all = False
    try:
        to_chat_ids = Config.forward[user_format(from_chat.username)]
    except KeyError:
        try:
            to_chat_ids = Config.forward[user_format(from_chat.id)]
        except KeyError:
            try:
                to_chat_ids = Config.forward[user_format(
                    from_chat.username) + ":push"]
            except KeyError:
                to_chat_ids = Config.forward[str(
                    user_format(from_chat.id)) + ":push"]
            use_push_all = True
    for to_chat_id in to_chat_ids:
        if isinstance(to_chat_id, str):
            split_result = to_chat_id.split(":")
            if len(split_result) == 2 or use_push_all:
                try:
                    to_chat = [int(split_result[0])]
                except ValueError:
                    to_chat = [user_format(split_result[0])]
                Msg(parse_url(message)).push(targets_additional=to_chat)
                continue
        if use_push_all:
            Msg(parse_url(message)).push(
                targets_additional=[user_format(to_chat_id)])
        else:
            message: Message = bot.send_message(
                user_format(to_chat_id),
                text=message.text_html_urled or message.caption_html_urled,
                parse_mode=ParseMode.HTML,
                disable_notification=True,
                # reply_markup=main_buttons(message.message_id)
            )
    message.edit_reply_markup(
        reply_markup=main_buttons(message.message_id)
    )


def register(updater: Updater):
    dp = updater.dispatcher
    from_chat_list = list()
    for from_chat in Config.forward.keys():
        if len(from_chat.split(":")) == 2:
            from_chat_list.append(from_chat.split(":")[0])
        else:
            from_chat_list.append(from_chat)
    dp.add_handler(MessageHandler(get_filter(
        from_chat_list), auto_forward, run_async=True))


if __name__ == "__main__":
    updater = Updater(token=Config.token, use_context=True)
    register(updater)
    updater.start_polling()
    logger.info(f"Bot @{updater.bot.get_me().username} 已启动: 仅自动转发")
    updater.idle()
