import re
import logging
import time
import asyncio
import async_timeout

from telegram import (
    Bot,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputTextMessageContent,
    ParseMode,
    Update,
    CallbackQuery,
    Message,
    User,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    CallbackContext,
    Updater,
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
    run_async,
    Dispatcher,
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


# custom_request: Dict[str, int] = {}
logger = logging.getLogger('push_helper')


def parse_url(message: Message):
    message_id = message.message_id
    text = message.text

    try:
        ret = next(iter(message.parse_entities(["url"]).values()))
    except:
        try:
            ret = next(iter(message.parse_entities(["text_link"]).keys())).url
        except:
            try:
                ret = re.search(regex.link, text).group(0)
            except:
                ret = text

    return ret


def into_push_list(f: Callable):

    @ wraps(f)
    def wrapped(update: Update, context: CallbackContext):
        message = update.callback_query.message
        message_id = message.message_id
        text = message.text

        if message_id not in push.waiting_to_push:
            push.waiting_to_push[message_id] = push.Message(parse_url(message))
        #print(push.waiting_to_push)  # SaltyFish: For DEBUG
        return f(update, context)

    return wrapped


@ timeout(15)
def get_reply(message: Message, update_queue: Queue) -> Message:
    while True:
        try:
            update = update_queue.get(block=True)
        except Exception:
            continue
        else:
            update_queue.task_done()
            update_queue.put_nowait(update)
            if update.message and update.message.reply_to_message == message:
                return update.message


# ! Failed on asynchronizing this function. Waiting for @Finall to solve this all.
#async def get_reply(message: Message, update_queue: Queue, _timeout: float = 5) -> Message:
#    async def get_update():
#        try:
#            update = update_queue.get(block=False)
#        except:
#            update = None
#        else:
#            update_queue.put(update)
#        return update
#
#    async def foo(): # 不可以被 wait_for 正常取消
#        while True: # 根源?
#            update = await get_update()
#            if update == None:
#                continue
#            if update.message and update.message.reply_to_message == message:
#                return update.message
#
#    async def bar(): # 可以被 wait_for 正常取消
#        await asyncio.sleep(10)
#        return Message()
#
#    # try:
#    return await bar()
#    # except asyncio.CancelledError: 似乎没必要
#    #     raise


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
            InlineKeyboardButton(text="> 目标", callback_data=regex.target+regex.sub),
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
            InlineKeyboardButton(text="< 标签", callback_data=regex.tag+regex.sub),
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
                InlineKeyboardButton(text="标签", callback_data=regex.tag+regex.sub),
                InlineKeyboardButton(text="目标", callback_data=regex.target+regex.sub)
            ],
            [
                InlineKeyboardButton(text="推送", callback_data=regex.push)
            ]
        ])
    else:
        buttons_list[0][0].text = "加入队列"
    return InlineKeyboardMarkup(buttons_list)


@ run_async
@ into_push_list
def update_tag(update: Updater, context: CallbackContext):
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
        # * Nice Try (?)
        #try:
        #    # loop = asyncio.new_event_loop()
        #    replied_msg = asyncio.run(asyncio.wait_for(get_reply(original_message, context.update_queue), timeout=10))
        #    # loop.close()
        #except asyncio.TimeoutError:
        #    logger.exception(f"错误: 自定义回复超时")
        #else:
        #    push.waiting_to_push[message_id].customized_tags.append(replied_msg.text)
        #    replied_msg.delete()
        #finally:
        #    original_message.delete()
        try:
            replied_message = get_reply(original_message, context.update_queue)
        except TimeLimitReached:
            logger.exception(f"错误: 自定义回复超时")
        else:
            push.waiting_to_push[message_id].customized_tags.append(replied_message.text)
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
    except Exception as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass


@ run_async
@ into_push_list
def update_target(update: Updater, context: CallbackContext):
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
            push.waiting_to_push[message_id].target_indices.remove(target_index)
        except KeyError:
            push.waiting_to_push[message_id].target_indices.add(target_index)

    try:
        message.edit_reply_markup(
            reply_markup=target_buttons(message_id)
        )
    except Exception as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass


@ run_async
@ into_push_list
def update_return(update: Updater, context: CallbackContext):
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
    except Exception as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass


@ run_async
#@ into_push_list
def update_message(update: Updater, context: CallbackContext):
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
    except Exception as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass



# Finall: 等待自动转发/群组支持
# SaltyFish: 实现于另一模块当中


# Saltyfish: 不同的实现方式
#@run_async
#def custom_tag(update: Updater, context: CallbackContext):
#    message = update.callback_query.message
#    if not update.effective_chat.CHANNEL:
#        replied_msg = message.reply_text(text="👆从这里返回\n请输入自定义 Tag:", reply_markup=ForceReply(
#            force_reply=True, selective=True))
#        global custom_tag_msg
#        custom_tag_msg = (replied_msg.message_id, message.message_id)
#    else:
#        message.reply_text(text="该功能在 Channel 中不可用，请考虑利用自动转发迁移到群组")
#
#@run_async
#def custom_tag_reply(update: Updater, context: CallbackContext):
#    global custom_tag_msg
#    message_id = update.effective_message.message_id
#    if not message_id == custom_tag_msg[0]:
#        return
#    else:
#        push.waiting_to_push[custom_tag_msg[1]].customized_tags.append(
#            update.effective_message.text)
#    update.effective_message.reply_text(text="已添加")
#    custom_tag_msg = ()


@ run_async
@ into_push_list
def push_single(update: Updater, context: CallbackContext):
    callback = update.callback_query
    message = callback.message
    message_id = message.message_id
    editor_bot = Bot(token=Config.token)
    #try:
    #message_to_push = push.waiting_to_push[message_id]
    #except:
    #    logger.exception(f"尝试推送不在队列中的消息")
    #    return
    message_to_push = push.waiting_to_push[message_id] # SaltyFish: 新的炫酷装饰器保证了它会在列表内

    message_to_push.push()
    update.callback_query.answer(f"开始推送单条消息, id: {message_id}")
    push.waiting_to_push.pop(message_id)
    try:
        message.edit_reply_markup(
            reply_markup=main_buttons(message_id)
        )
    except Exception as exc:
        if exception_not_modified(exc) is None:
            logger.exception(f"错误: 无法编辑Markup")
        else:
            pass


@ run_async
def add_keyboard(update: Updater, context: CallbackContext):
    message = update.effective_message
    message_id = message.message_id
    chat_id = message.chat.id
    editor_bot = Bot(token=Config.token)
    try:
        message.edit_reply_markup(
            reply_markup=main_buttons(message_id)
        )
    except Exception as exc:
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
    dp.add_handler(MessageHandler(filter_user & ~ filter_command & ~ filter_reply, add_keyboard))
    #dp.add_handler(MessageHandler(Filters.all, add_keyboard))
    dp.add_handler(CallbackQueryHandler(update_tag, pattern=regex.tag))
    dp.add_handler(CallbackQueryHandler(update_target, pattern=regex.target))
    dp.add_handler(CallbackQueryHandler(update_return, pattern=regex.ret))
    dp.add_handler(CallbackQueryHandler(update_message, pattern=regex.select))
    dp.add_handler(CallbackQueryHandler(push_single, pattern=regex.push))
