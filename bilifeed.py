# 此文件中几乎所有代码来自 telegram-bili-feed-helper by @simonsmh，本人仅作微小修改。
# 感谢贡献。


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
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    InputTextMessageContent,
    ParseMode,
)
from telegram.error import BadRequest, TimedOut
from telegram.ext.dispatcher import run_async
from telegram.utils.helpers import escape_markdown

from feedparser import feedparser, headers


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger("rssbot_push")


# >
def origin_link(content):
    return InlineKeyboardMarkup([[InlineKeyboardButton(text="原链接", url=content)]])


@ lru_cache(maxsize=16)
def captions(f):
    def parser_helper(content):
        charegex = r"\W"
        content = re.sub(
            r"\\#([^#]+)\\#?",
            lambda x: f"\\#{re.sub(charegex, '', x.group(1))} ",
            content,
        )
        return content

    captions = f"{f.user_markdown}:\n"
    if f.content_markdown:
        captions += f.content_markdown
    if f.comment_markdown:
        captions += f"\n\\-\\-\\-\\-\\-\\-\n{f.comment_markdown}"
    return parser_helper(captions)


async def get_media(f, url, size=1280, compression=True):
    def compress(inpil):
        pil = Image.open(inpil)
        pil.thumbnail((size, size), Image.LANCZOS)
        pil.save(outpil := BytesIO(), "PNG", optimize=True)
        return outpil

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, headers={"Referer": f.url}) as resp:
            media = BytesIO(await resp.read())
            mediatype = resp.headers["Content-Type"]
    if compression:
        if mediatype in ["image/jpeg", "image/png"]:
            logger.info(f"压缩: {url} {mediatype}")
            media = compress(media)
    media.seek(0)
    return media
# <


# > 这个函数是 telegram-bili-feed-helper/main.py 中 parse 函数的改写。
@ run_async
def send_bili_feed(url: str, classification: str, bot: Bot, target):
    async def callback(f, caption):
        if f.mediathumb:
            mediathumb = await get_media(f, f.mediathumb, size=320)
        if f.mediaraws:
            tasks = [get_media(f, img) for img in f.mediaurls]
            media = await asyncio.gather(*tasks)
            logger.info(f"上传中: {f.url}")
        else:
            if f.mediatype == "image":
                media = [i if ".gif" in i else i +
                         "@1280w.jpg" for i in f.mediaurls]
            else:
                media = f.mediaurls
        if f.mediatype == "video":
            bot.send_video(
                target,
                media[0],
                caption=(captions(f) + classification),
                parse_mode=ParseMode.MARKDOWN_V2,
                # quote=False,
                reply_markup=origin_link(f.url),
                supports_streaming=True,
                thumb=mediathumb,
                timeout=120,
            )
        elif f.mediatype == "audio":
            bot.send_audio(
                target,
                media[0],
                caption=(captions(f) + classification),
                duration=f.mediaduration,
                parse_mode=ParseMode.MARKDOWN_V2,
                performer=f.user,
                # quote=False,
                reply_markup=origin_link(f.url),
                thumb=mediathumb,
                timeout=120,
                title=f.mediatitle,
            )
        elif len(f.mediaurls) == 1:
            if ".gif" in f.mediaurls[0]:
                bot.send_animation(
                    target,
                    media[0],
                    caption=(captions(f) + classification),
                    parse_mode=ParseMode.MARKDOWN_V2,
                    # quote=False,
                    reply_markup=origin_link(f.url),
                    timeout=60,
                )
            else:
                bot.send_photo(
                    target,
                    media[0],
                    caption=(captions(f) + classification),
                    parse_mode=ParseMode.MARKDOWN_V2,
                    # quote=False,
                    reply_markup=origin_link(f.url),
                    timeout=60,
                )
        else:
            media = [
                InputMediaPhoto(
                    img, caption=(captions(f) + classification), parse_mode=ParseMode.MARKDOWN_V2
                )
                for img in media
            ]
            bot.send_media_group(target, media, timeout=120)
            bot.send_message(
                target,
                (captions(f) + classification),
                disable_web_page_preview=True,
                parse_mode=ParseMode.MARKDOWN_V2,
                # quote=False,
                reply_markup=origin_link(f.url),
            )

    async def parse_queue(url):
        f = await feedparser(url, video=False)
        if not f:
            logger.warning(f"解析错误！")
            return
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="原链接", url=f.url)]]
        )
        if f.mediaurls:
            try:
                await callback(f, captions(f))
            except (TimedOut, BadRequest) as err:
                logger.exception(err)
                logger.info(f"{err} -> 下载中: {f.url}")
                f.mediaraws = True
                await callback(f, captions(f))
        else:
            bot.send_message(
                target,
                (captions(f) + classification),
                disable_web_page_preview=True,
                parse_mode=ParseMode.MARKDOWN_V2,
                # quote=False,
                reply_markup=reply_markup,
            )

    loop = asyncio.new_event_loop()
    tasks = [parse_queue(url)]
    loop.run_until_complete(asyncio.gather(*tasks, loop=loop))
    loop.close()
# <
