import asyncio
import json
import logging
import os
import re
import sys
from functools import lru_cache
from io import BytesIO
from uuid import uuid4

import aiohttp
from PIL import Image
from telegram import (
    Bot,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputTextMessageContent,
    ParseMode,
    Update
)
from telegram.error import BadRequest, TimedOut
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater,
    ConversationHandler
)
from telegram.ext.dispatcher import run_async
from telegram.ext.filters import (Filters, MergedFilter)
from telegram.utils.helpers import escape_markdown

from bilifeed import send_bili_feed

from typing import Sequence
from mwt import mwt
from threading import Thread

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger("rssbot_push")


# Callback regexes
push_regex = r"push"
tag_regex = r"tag"
tag_custom_regex = r"tag custom"
target_regex = r"target"
select_regex = r"select"
return_regex = r"return"
sub_regex = r"sub"
custom_regex = r"custom"
link_regex = r"[a-zA-z]+://[^\s]*"
bili_regex = r"(?i)\w*\.?(?:bilibili\.com|(?:b23|acg)\.tv)\S+"
bili_v_regex = r"(www\.bilibili\.com|(b23|acg)\.tv)/(video/|)([aA][vV][0-9]*|[bB][vV][a-zA-Z0-9]*)"


# Helper functions
@ mwt(timeout=60*60)
def get_admin(bot: Bot, chat_id):
    return [admin.user.id for admin in bot.get_chat_administrators(chat_id)]


def odd_even(l: list) -> list:
    if not l:
        return l
    length = len(l)
    ret = [[l[2*i], l[2*i + 1]] for i in range(length//2)]
    if length % 2:
        ret.append([l[-1]])
    return ret


def nested_list_map(func, l: list) -> list:
    return [nested_list_map(func, elem) if isinstance(elem, list) else func(elem) for elem in l]


sourceCodeMarkup = InlineKeyboardMarkup.from_column([
    InlineKeyboardButton(
        text="源代码", url="https://github.com/finall1008/telegram-pusher-bot")
])


class Message:
    def __init__(self, url: str):
        self.url = url
        self.tag_indices = set()
        self.target_indices = set()
        self.customized_tags = list()

    def get_tags(self):
        return [tags[i] for i in self.tag_indices] + self.customized_tags

    def get_targets(self):
        return [targets[i] for i in self.target_indices]

    def __str__(self) -> str:
        return f"url: { self.url }\ntags: %s\ntargets: %s" % (" ".join(self.get_tags()), " ".join(self.get_targets()))

    def __repr__(self) -> str:
        return f"<Message:\n{ self.__str__() }\n>"

    @ run_async
    def push(self, targets_override: list = None, tags_additional: set = None):
        bot = Bot(token=TOKEN)
        sep = "\n\n"
        self_tags = self.get_tags()
        if tags_additional:
            self_tags_with_additional = set(self_tags).union(tags_additional)
            self_tags = list(self_tags_with_additional)
        if targets_override:
            self_targets = targets_override
        else:
            self_targets = self.get_targets()
        if not self_targets:
            logger.info(f"未提供目标：发送到默认目标")
            self_targets = [targets[0]]
        if not self_tags:
            # logger.warning(f"未提供分类") SaltyFish: Seems unnecessary
            sep = ""

        for target in self_targets:
            logger.info(f"将 {self.url} 推送至 {target}.")
            if not re.search(bili_regex, self.url) or re.search(bili_v_regex, self.url):
                bot.send_message(
                    target,
                    self.url + sep +
                    "  ".join(map(lambda tag: "#" + tag, self_tags))
                )
            else:
                send_bili_feed(
                    self.url,
                    sep + "  ".join([r"\#" + tag for tag in self_tags]),
                    bot,
                    target
                )


waitingToPush = {}


def tag_buttons(chat_type: str, message_id):
    def check_if_str(index, tag: str) -> str:
        if index in waitingToPush[message_id].tag_indices:
            return "[✓] " + tag
        else:
            return tag

    buttons_list = [
        InlineKeyboardButton(text=check_if_str(
            index, value), callback_data="tag "+str(index))
        for index, value in enumerate(tags)
    ]
    if not chat_type == "channel":
        buttons_list.append(InlineKeyboardButton(
            text="自定义", callback_data="tag custom"))
    if len(buttons_list) > 3:
        buttons_list = odd_even(buttons_list)
    else:
        buttons_list = [[button] for button in buttons_list]
    buttons_list.extend([
        [InlineKeyboardButton(text="目标", callback_data="target sub"), InlineKeyboardButton(
            text="返回", callback_data="return")]
    ])
    return InlineKeyboardMarkup(buttons_list)


def target_buttons(message_id):
    def check_if_str(index, target: str) -> str:
        if index in waitingToPush[message_id].target_indices:
            return "[✓] " + target
        else:
            return target

    buttons_list = [
        InlineKeyboardButton(text=check_if_str(
            index, value), callback_data="target "+str(index))
        for index, value in enumerate(targets)
    ]
    if len(buttons_list) > 3:
        buttons_list = odd_even(buttons_list)
    else:
        buttons_list = [[button] for button in buttons_list]
    buttons_list.extend([
        [InlineKeyboardButton(text="标签", callback_data="tag sub"), InlineKeyboardButton(
            text="返回", callback_data="return")]
    ])
    return InlineKeyboardMarkup(buttons_list)


def main_buttons(message_id):
    buttons_list = [
        [InlineKeyboardButton(text="", callback_data="select")]
    ]
    if message_id in waitingToPush:
        buttons_list[0][0].text = "移出队列"
        buttons_list.extend([[
            InlineKeyboardButton(text="标签", callback_data="tag sub"),
            InlineKeyboardButton(text="目标", callback_data="target sub")
        ], [InlineKeyboardButton(text="推送", callback_data="push")]])
    else:
        buttons_list[0][0].text = "加入队列"
    return InlineKeyboardMarkup(buttons_list)


@ run_async
def update_tag(update, context):
    callback = update.callback_query
    message = callback.message
    message_id = message.message_id
    data = callback.data
    chat_id = message.chat.id
    editor_bot = Bot(token=TOKEN)

    callback.answer()
    if not re.search(sub_regex, data) and not re.search(tag_custom_regex, data):
        tag_index = int(data[len(tag_regex):])
        try:
            waitingToPush[message_id].tag_indices.remove(tag_index)
        except:
            waitingToPush[message_id].tag_indices.add(tag_index)

    try:
        editor_bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=message_id,
            reply_markup=tag_buttons(update.effective_chat.type, message_id)
        )
    except:
        pass


@ run_async
def update_target(update, context):
    callback = update.callback_query
    message = callback.message
    message_id = message.message_id
    data = callback.data
    chat_id = message.chat.id
    editor_bot = Bot(token=TOKEN)

    callback.answer()
    if not re.search(sub_regex, data):
        target_index = int(data[len(target_regex):])
        try:
            waitingToPush[message_id].target_indices.remove(target_index)
        except:
            waitingToPush[message_id].target_indices.add(target_index)

    try:
        editor_bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=message_id, reply_markup=target_buttons(
                message_id)
        )
    except:
        pass


@ run_async
def update_return(update, context):
    callback = update.callback_query
    message = callback.message
    message_id = message.message_id
    chat_id = message.chat.id
    editor_bot = Bot(token=TOKEN)

    callback.answer()
    try:
        editor_bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=message_id, reply_markup=main_buttons(
                message_id)
        )
    except:
        pass


@ run_async
def update_message(update, context):
    callback = update.callback_query
    message_id = callback.message.message_id
    message = callback.message
    chat_id = message.chat.id
    text = callback.message.text
    editor_bot = Bot(token=TOKEN)
    callback.answer()
    try:
        waitingToPush.pop(message_id)
    except KeyError:
        try:
            waitingToPush[message_id] = Message(
                next(iter(callback.message.parse_entities(
                    ["url"]).keys())).url
            )
        except:
            try:
                waitingToPush[message_id] = Message(
                    next(iter(callback.message.parse_entities(
                        ["text_link"]).keys())).url
                )
            except:
                waitingToPush[message_id] = Message(
                    re.search(link_regex, text).group(0)
                )
                # print(waitingToPush)  # SaltyFish: For DEBUG

    try:
        editor_bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=message_id, reply_markup=main_buttons(
                message_id)
        )
    except:
        pass


# Finall: 等待自动转发/群组支持


custom_tag_msg = ()


@run_async
def custom_tag(update, context):
    message = update.callback_query.message
    if not update.effective_chat.CHANNEL:
        replied_msg = message.reply_text(text="👆从这里返回\n请输入自定义 Tag:", reply_markup=ForceReply(
            force_reply=True, selective=True))
        global custom_tag_msg
        custom_tag_msg = (replied_msg.message_id, message.message_id)
    else:
        message.reply_text(text="该功能在 Channel 中不可用，请考虑利用自动转发迁移到群组")


@run_async
def custom_tag_reply(update, context):
    global custom_tag_msg
    message_id = update.effective_message.message_id
    if not message_id == custom_tag_msg[0]:
        return
    else:
        waitingToPush[custom_tag_msg[1]].customized_tags.append(
            update.effective_message.text)
    update.effective_message.reply_text(text="已添加")
    custom_tag_msg = ()


@run_async
def push_single(update, context):
    message_id = update.callback_query.message.message_id
    try:
        message = waitingToPush[message_id]
    except:
        logger.exception(f"尝试推送不在队列中的消息")
        return
    message.push()
    update.callback_query.answer(
        f"开始推送 {message_id}")
    waitingToPush.pop(message_id)
    Bot(token=TOKEN).edit_message_reply_markup(
        chat_id=update.callback_query.message.chat.id, message_id=message_id, reply_markup=main_buttons(
            message_id)
    )


@ run_async
def self_define(update, context):
    pass  # SaltyFish: Waiting for group support


@ run_async
def add_keyboard(update, context):
    message = update.effective_message
    message_id = message.message_id
    chat_id = message.chat.id
    editor_bot = Bot(token=TOKEN)
    try:
        editor_bot.edit_message_reply_markup(
            chat_id=chat_id, message_id=message_id, reply_markup=main_buttons(
                message_id)
        )
    except:
        pass
    logger.info(f"成功添加按钮到 {message_id}")


@ run_async
def error(update, context):
    logger.exception(f"更新 {context} 导致了错误: {error}")


@ run_async
def start(update, context):
    update.effective_message.reply_text(
        text="爷活着",
        reply_markup=sourceCodeMarkup
    )


@ run_async
def check_commands(update, context):
    update.effective_message.reply_text(
        text="所有command如下:\n"
        + "\n".join([f"/{command}: {description}" for command,
                     description in commands]),
        quote=True
    )


def restart(update, context):
    def stop_and_restart():
        updater.stop()
        os.execl(sys.executable, sys.executable, *sys.argv,
                 "--restart", str(update.effective_chat.id))

    update.effective_message.reply_text(text="正在重启bot...")
    logger.info(f"正在重启 Bot")
    Thread(target=stop_and_restart).start()


@ run_async
def push(update, context, args: list = None):
    chat = update.effective_chat
    chat_id = chat.id
    editor_bot = Bot(token=TOKEN)

    if chat.CHANNEL or update.effective_user.id in get_admin(update.bot, chat_id):
        waitingToPushCurrent = dict(waitingToPush)
        waitingToPush.clear()
        # print(waitingToPushCurrent) # Finall: For debug
        pushed_message_id = list(waitingToPushCurrent.keys())
        logger.info(f"推送全部内容")
        update.effective_message.reply_text(text="开始推送队列中全部内容", quote=True)
        targets_override = list()
        tags_additional = set()
        for arg in args:
            if arg[0] == "@":
                targets_override.append(arg)
            else:
                tags_additional.add(arg)
        for message in waitingToPushCurrent.values():
            message.push(targets_override, tags_additional)
        del waitingToPushCurrent
        for message_id in pushed_message_id:
            editor_bot.edit_message_reply_markup(
                chat_id=update.effective_chat.id, message_id=message_id, reply_markup=main_buttons(
                    message_id)
            )
    else:
        update.ceffective_message.reply_text(text="需要以管理员权限执行此命令", quote=True)


@ run_async
def check(update, context):
    bot = Bot(token=TOKEN)
    chat = update.effective_chat
    chat_id = chat.id
    command_message_id = update.effective_message.message_id

    if chat.CHANNEL or update.effective_user.id in get_admin(update.bot, chat_id):
        for message_id, message in waitingToPush.items():
            bot.send_message(
                chat_id=chat_id,
                text=str(message),
                reply_to_message_id=message_id,
                disable_web_page_preview=True
            )
        bot.send_message(
            chat_id=chat_id,
            text=f"目前的推送列表内共有 {len(waitingToPush)} 条消息",
            reply_to_message_id=command_message_id
        )

        logger.info(f"确认推送内容")
    else:
        update.effective_message.reply_text(text="需要以管理员权限执行此命令")


@ run_async
def log_by_id(update, context):
    chat = update.effective_message.chat
    watcher_name = chat.username

    if not (chat.CHANNEL or update.effective_user.id in get_admin(update.bot, chat.id)):
        update.effective_message.reply_text(text="需要以管理员权限执行此命令", quote=True)
        return
    else:
        pass

    try:
        config["watchers_name"].remove(f"@{watcher_name.lstrip('@')}")
    except:
        update.effective_message.reply_text(
            text="失败: 此频道/群组已经以ID形式记录, 无需再次执行此命令", quote=True)
        logger.exception(f"频道/群组 {chat.id} 已经以ID形式记录")
        return
    try:
        if chat.id not in config["watchers_id"]:
            config["watchers_id"].append(chat.id)
    except:
        config["watchers_id"] = [chat.id]
    with open("push_config.json", "w", encoding="utf8") as file:
        json.dump(config, file, ensure_ascii=False, indent=4)
    update.effective_message.reply_text(
        text="成功: 已将此频道/群组的记录方式改为 ID", quote=True)

    logger.info(f"频道/群组 {chat.username} 的记录方式改为了 ID: {chat.id}")


@ run_async
def bot_command_handler(update, context):
    message = update.effective_message
    text = message.text

    if text[0] == "/":
        command = text.split(" ")[0][1:]
        args = text.split(" ")[1:]
        if command == "push":
            push(update=update, context=context, args=args)
        elif command == "check":
            check(update=update, context=context)
        elif command == "log_by_id":
            log_by_id(update=update, context=context)
        elif command == "commands":
            check_commands(update=update, context=context)
        else:
            return
    else:
        raise Exception(f"非法指令")


if __name__ == "__main__":

    with open('push_config.json', 'r') as file:
        config = json.load(file)

    try:
        TOKEN = config["token"]
    except:
        logger.exception(f"非法的 token")
        sys.exit(1)
    try:
        tags = config["tags"]
    except:
        logger.exception(f"非法的 tags")
        sys.exit(1)
    try:
        targets = [
            f"@{target.lstrip('@')}" for target in config["targets"] if isinstance(target, str)]
        config["targets"] = targets
    except:
        logger.exception(f"非法的 targets")
        sys.exit(1)
    try:
        watchers_id = [
            watcher_id for watcher_id in config["watchers_id"] if isinstance(watcher_id, int)]
        watchers_name = [
            f"@{watcher_name.lstrip('@')}" for watcher_name in config["watchers_name"] if isinstance(watcher_name, str)]
        config["watchers_id"], config["watchers_name"] = watchers_id, watchers_name
    except:
        logger.exception(f"非法的 watchers")
        sys.exit(1)

    with open('push_config.json', 'w', encoding='utf8') as write_back:
        json.dump(config, write_back, ensure_ascii=False, indent=4)

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    try:
        filter_user = Filters.chat(username=watchers_name) and Filters.chat(
            chat_id=watchers_id) and ~ Filters.user([updater.bot.id])
    except:
        if not len(watchers_name):
            filter_user = Filters.chat(
                chat_id=watchers_id) and ~ Filters.user([updater.bot.id])
        else:
            filter_user = Filters.chat(
                username=watchers_name) and ~ Filters.user([updater.bot.id])
    filter_command = Filters.command
    filter_reply = Filters.reply

    dp.add_handler(CommandHandler("start", start, filters=Filters.private))
    dp.add_handler(CommandHandler("restart", restart, filters=Filters.private))

    commands = [
        ("start", "检查bot是否在线以及获得目前的状态信息"),
        ("restart", "简单的远程一键重启"),
        ("push", "推送所有已选中内容至各自目标"),
        ("check", "检查所有已选中内容"),
        ("log_by_id", "将当前监察群组在config中的的记录方式改为ID"),
        ("commands", "列出所有的command, 需注意列出的选项在当前的环境内不一定可用")
    ]
    updater.bot.set_my_commands(commands)  # SaltyFish: Checking

    dp.add_handler(MessageHandler(
        filter_user and filter_command, bot_command_handler))
    dp.add_handler(MessageHandler(
        filter_user and ~ filter_command, add_keyboard))
    dp.add_handler(MessageHandler(
        filter_user and ~ filter_command and filter_reply, custom_tag_reply
    ))

    dp.add_handler(CallbackQueryHandler(update_tag, pattern=tag_regex))
    dp.add_handler(CallbackQueryHandler(update_target, pattern=target_regex))
    dp.add_handler(CallbackQueryHandler(update_return, pattern=return_regex))
    dp.add_handler(CallbackQueryHandler(update_message, pattern=select_regex))
    dp.add_handler(CallbackQueryHandler(push_single, pattern=push_regex))
    dp.add_handler(CallbackQueryHandler(custom_tag, pattern=tag_custom_regex))
    dp.add_error_handler(error)

    updater.start_polling()
    logger.info(f"Bot @{updater.bot.get_me().username} 已启动")
    try:
        if sys.argv[-2] != "--restart":
            raise Exception()
    except:
        pass
    else:
        updater.bot.send_message(chat_id=int(sys.argv[-1]), text="重启完毕")
    updater.idle()
