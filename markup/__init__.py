import re
import time
import logging

from telegram import (
    Bot,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    CallbackQuery,
    Message,
)
from telegram.ext import (
    CallbackContext,
    Updater,
    CallbackQueryHandler,
    Filters,
    MessageHandler,
    Updater,
    run_async,
)
from telegram.error import BadRequest
from typing import Dict, Callable
from functools import wraps
from queue import Queue, Empty

from utils import Config, get_filter, timeout, TimeLimitReached, WrapType

import utils
import utils.push as push
import utils.regexes as regex

from .auto_select import *


logger = logging.getLogger('push_helper')


def parse_url(message: Message):
    text = message.text

    try:
        ret = message.parse_entities(["url"]).values().__iter__().__next__()
    except StopIteration:
        try:
            ret = message.parse_entities(
                ["text_link"]).keys().__iter__().__next__().url
        except (StopIteration, AttributeError):
            try:
                ret = re.search(regex.link, text).group(0)
            except AttributeError:
                ret = text

    return ret


def into_push_list(f: Callable):

    @ wraps(f)
    def wrapped(update: Update, context: CallbackContext):
        message = update.callback_query.message
        message_id = message.message_id

        if message_id not in push.waiting_to_push:
            push.waiting_to_push[message_id] = push.Message(parse_url(message))
        # print(push.waiting_to_push)  # SaltyFish: For DEBUG
        return f(update, context)

    return wrapped


def get_reply(message: Message, update_queue: Queue, timeout: float) -> Message:
    now = time.perf_counter
    deadline = now() + timeout
    while now() <= deadline:
        try:
            update = update_queue.get(block=True, timeout=deadline-now())
        except Empty:
            continue
        update_queue.task_done()
        if update.message and update.message.reply_to_message == message:
            return update.message
        else:
            update_queue.put_nowait(update)
    raise TimeLimitReached(f"Reached given time limit {timeout}s")


def no(*args, **kwargs):
    pass


def exception_not_modified(exc: BadRequest):
    return re.search("Message is not modified", exc.message)


def text_selected(text: str) -> str:
    return f"[✓] {text}"


def tag_buttons(message_id: int):
    def check_if_str(index: int, tag: str) -> str:
        if index in push.waiting_to_push[message_id].tag_indices:
            return text_selected(tag)
        else:
            return tag

    buttons_list = [
        InlineKeyboardButton(
            text=check_if_str(index, value),
            callback_data=regex.tag+str(index)
        )
        for index, value in enumerate(Config.tags)
    ] + [
        InlineKeyboardButton(
            text=text_selected(customized_tag),
            callback_data=regex.tag+regex.custom+str(index)
        )
        for index, customized_tag in enumerate(push.waiting_to_push[message_id].customized_tags)
    ] + [
        InlineKeyboardButton(text="自定义", callback_data=regex.tag+regex.custom)
    ]
    if len(buttons_list) > 3:
        buttons_list = utils.odd_even(buttons_list)
    else:
        buttons_list = [[button] for button in buttons_list]

    buttons_list.extend([
        [
            InlineKeyboardButton(
                text="> 目标", callback_data=regex.target+regex.sub),
            InlineKeyboardButton(text="返回", callback_data=regex.ret)
        ]
    ])
    return InlineKeyboardMarkup(buttons_list)


def target_buttons(message_id: int):
    def check_if_str(index: int, target: str) -> str:
        if index in push.waiting_to_push[message_id].target_indices:
            return text_selected(target)
        else:
            return target

    buttons_list = [
        InlineKeyboardButton(
            text=check_if_str(index, value),
            callback_data=regex.target+str(index)
        )
        for index, value in enumerate(map(str, Config.targets))
    ]
    if len(buttons_list) > 3:
        buttons_list = utils.odd_even(buttons_list)
    else:
        buttons_list = [[button] for button in buttons_list]

    buttons_list.extend([
        [
            InlineKeyboardButton(
                text="< 标签", callback_data=regex.tag+regex.sub),
            InlineKeyboardButton(text="返回", callback_data=regex.ret)
        ]
    ])
    return InlineKeyboardMarkup(buttons_list)


def main_buttons(message_id: int):
    buttons_list = [
        [InlineKeyboardButton(text="", callback_data=regex.select)]
    ]
    if message_id in push.waiting_to_push:
        buttons_list[0][0].text = "移出队列"
        buttons_list.extend([
            [
                InlineKeyboardButton(
                    text="标签", callback_data=regex.tag+regex.sub),
                InlineKeyboardButton(
                    text="目标", callback_data=regex.target+regex.sub)
            ],
            [
                InlineKeyboardButton(text="推送", callback_data=regex.push)
            ]
        ])
    else:
        buttons_list[0][0].text = "加入队列"
    return InlineKeyboardMarkup(buttons_list)


@ into_push_list
def update_tag(update: Update, context: CallbackContext):
    callback: CallbackQuery = update.callback_query
    message = callback.message
    message_id = message.message_id
    data = callback.data
    chat_id = message.chat.id
    username = callback.from_user.username
    editor_bot = Bot(token=Config.token)

    def self_define():
        original_message = editor_bot.send_message(
            chat_id=chat_id,
            text=f"@{username}\n请回复自定义tag:",
            disable_notification=True,
            reply_to_message_id=message_id,
            reply_markup=ForceReply(selective=True)
        )
        try:
            replied_message = get_reply(
                original_message, context.update_queue, timeout=5)
        except TimeLimitReached:
            logger.exception(f"错误: 自定义回复超时")
        else:
            push.waiting_to_push[message_id].customized_tags.append(
                replied_message.text)
            replied_message.delete()
        finally:
            original_message.delete()

    callback.answer()
    if not re.search(regex.sub, data):
        if not re.search(regex.custom, data):
            tag_index = int(data[len(regex.tag):])
            try:
                push.waiting_to_push[message_id].tag_indices.remove(tag_index)
            except KeyError:
                push.waiting_to_push[message_id].tag_indices.add(tag_index)

        else:
            try:
                tag_index = int(data[len(regex.tag+regex.custom):])
            except ValueError:
                self_define()
            else:
                push.waiting_to_push[message_id].customized_tags.pop(tag_index)

    try:
        message.edit_reply_markup(
            reply_markup=tag_buttons(message_id)
        )
    except BadRequest as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass


@ into_push_list
def update_target(update: Update, context: CallbackContext):
    callback = update.callback_query
    message = callback.message
    message_id = message.message_id
    data = callback.data
    chat_id = message.chat.id
    editor_bot = Bot(token=Config.token)

    callback.answer()
    if not re.search(regex.sub, data):
        target_index = int(data[len(regex.target):])
        try:
            push.waiting_to_push[message_id].target_indices.remove(
                target_index)
        except KeyError:
            push.waiting_to_push[message_id].target_indices.add(target_index)

    try:
        message.edit_reply_markup(
            reply_markup=target_buttons(message_id)
        )
    except BadRequest as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass


@ into_push_list
def update_return(update: Update, context: CallbackContext):
    callback = update.callback_query
    message = callback.message
    message_id = message.message_id
    chat_id = message.chat.id
    editor_bot = Bot(token=Config.token)

    callback.answer()
    try:
        message.edit_reply_markup(
            reply_markup=main_buttons(message_id)
        )
    except BadRequest as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass


# @ into_push_list
def update_message(update: Update, context: CallbackContext):
    callback = update.callback_query
    message = callback.message
    message_id = message.message_id
    chat_id = message.chat.id
    text = message.text
    editor_bot = Bot(token=Config.token)

    callback.answer()
    if message_id in push.waiting_to_push:
        push.waiting_to_push.pop(message_id)
    else:
        into_push_list(no)(update, context)
    try:
        message.edit_reply_markup(
            reply_markup=main_buttons(message_id)
        )
    except BadRequest as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass


@ into_push_list
def push_single(update: Update, context: CallbackContext):
    callback = update.callback_query
    message = callback.message
    message_id = message.message_id
    editor_bot = Bot(token=Config.token)
    # try:
    #message_to_push = push.waiting_to_push[message_id]
    # except:
    #    logger.exception(f"尝试推送不在队列中的消息")
    #    return
    # SaltyFish: 新的炫酷装饰器保证了它会在列表内
    message_to_push = push.waiting_to_push[message_id]

    message_to_push.push()
    update.callback_query.answer(f"开始推送单条消息, id: {message_id}")
    push.waiting_to_push.pop(message_id)
    try:
        message.edit_reply_markup(
            reply_markup=main_buttons(message_id)
        )
    except BadRequest as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass


def add_keyboard(update: Update, context: CallbackContext):
    message = update.effective_message
    message_id = message.message_id
    chat_id = message.chat.id
    editor_bot = Bot(token=Config.token)
    try:
        message.edit_reply_markup(
            reply_markup=main_buttons(message_id)
        )
    except BadRequest as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass
    else:
        logger.info(f"成功添加按钮到 {message_id}")


def register(updater: Updater):
    filter_user = (
        get_filter(Config.watchers)
        & ~ Filters.user([updater.bot.id])
    )
    filter_command = Filters.command
    filter_reply = Filters.reply

    dp = updater.dispatcher
    dp.add_handler(MessageHandler(filter_user & filter_command, no))
    dp.add_handler(MessageHandler(
        filter_user & ~ filter_command & ~ filter_reply, add_keyboard))
    #dp.add_handler(MessageHandler(Filters.all, add_keyboard))
    dp.add_handler(CallbackQueryHandler(update_tag, pattern=regex.tag))
    dp.add_handler(CallbackQueryHandler(update_target, pattern=regex.target))
    dp.add_handler(CallbackQueryHandler(update_return, pattern=regex.ret))
    dp.add_handler(CallbackQueryHandler(update_message, pattern=regex.select))
    dp.add_handler(CallbackQueryHandler(push_single, pattern=regex.push))
