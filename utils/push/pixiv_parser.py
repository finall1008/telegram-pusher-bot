from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Bot,
    ParseMode,
    InputMediaPhoto
)
from typing import (
    Any,
    Tuple,
    Optional,
)
from telegram.ext.dispatcher import run_async
from telegram.error import NetworkError
from pixivpy_async import AppPixivAPI
import os
from os.path import join, getsize
import json
import sys
import logging
import asyncio
import re
from bs4 import BeautifulSoup
from utils import BaseConfig

logger = logging.getLogger("push_helper")


class PixivParser:
    status = False
    aapi = AppPixivAPI()
    id_regex = r"[1-9]\d*"

    class Config(BaseConfig, config_file="push_config.json"):
        pixiv_username: str = str()
        pixiv_password: str = str()
        download_path: Optional[str] = str()

        @classmethod
        def _check(cls, _attr_name: str, _attr_value: Any) -> Tuple[str, Any]:
            if _attr_name == "download_path" and _attr_value == "":
                logger.info(f"未提供下载路径, 使用 {os.path.dirname(__file__)}/PixivDownload")
                try:
                    os.mkdir(f"{os.path.dirname(__file__)}/PixivDownload")
                except FileExistsError:
                    pass
                except BaseException as exc:
                    logger.exception("下载路径不可用")
                    #sys.exit(1)
                    raise exc
                return _attr_name, os.path.dirname(__file__) + "/PixivDownload"
            else:
                return _attr_name, _attr_value

    @classmethod
    @run_async
    def send(self, url: str, classification: str, bot: Bot, target):
        async def init_appapi(aapi: AppPixivAPI):
            try:
                await aapi.login(username=self.Config.pixiv_username, password=self.Config.pixiv_password)
            except:
                logger.exception("Pixiv 登陆失败")
                return False
            logger.info("成功登录 Pixiv")
            aapi.set_accept_language("zh-CN")
            return True

        def origin_link(_id: int):
            return InlineKeyboardMarkup([[InlineKeyboardButton(text="原链接", url=f"https://www.pixiv.net/artworks/{_id}")]])

        def parse_tags_text(tags: list) -> str:
            text = str()
            for tag in tags:
                if tag.translated_name:
                    translated_name = f"({tag.translated_name})"
                else:
                    translated_name = ""
                text = text + \
                    f"<a href=\"https://www.pixiv.net/tags/{tag.name}/artworks\">{tag.name}{translated_name}</a> "
            return text

        async def download_single_pic(url: str, _id: int, size: str, page: int, aapi: AppPixivAPI):
            url_basename = os.path.basename(url)
            extension = os.path.splitext(url_basename)[1]
            name = f"{_id}_p{page}_{size}{extension}"
            try:
                os.mkdir(f"{self.Config.download_path}/{_id}")
            except FileExistsError:
                pass
            await aapi.download(url, path=self.Config.download_path + "/" + str(_id), name=name)
            logger.info(f"成功下载 {name}")

        def download_pic(urls: list, _id: int, size: str, aapi: AppPixivAPI):
            page = 0
            loop = asyncio.new_event_loop()
            tasks = list()
            for url in urls:
                tasks.append(download_single_pic(url, _id, size, page, aapi))
                # download_single_pic(url, _id, size, page, aapi)
                page = page + 1
            loop.run_until_complete(asyncio.gather(*tasks, loop=loop))
            loop.close()
            logger.info(f"成功下载 {_id} 全部图片")

        async def parse_illust_info_msg(illust_id: int, aapi: AppPixivAPI):
            json_result = await aapi.illust_detail(illust_id)
            info = json_result.illust
            caption = str()
            if info.caption != "":
                soup = BeautifulSoup(info.caption, "html.parser")
                caption = "\n" + soup.get_text()
            msg_text = f"<b>标题：</b>{info.title}\n<b>作者：</b><a href=\"https://www.pixiv.net/users/{info.user.id}\">{info.user.name}</a>{caption}\n<b>标签：</b>{parse_tags_text(info.tags)}{classification}"
            logger.info(msg_text)

            if info.page_count == 1:
                illust_urls = [info.image_urls.large]
            else:
                illust_urls = [page.image_urls.large for page in info.meta_pages]
            return illust_urls, illust_id, msg_text

        loop = asyncio.new_event_loop()
        login_result = loop.run_until_complete(init_appapi(self.aapi))
        loop.close()
        if not login_result:
            return

        illust_id = int(re.search(pattern=self.id_regex, string=url).group(0))

        loop = asyncio.new_event_loop()
        illust_urls, illust_id, msg_text = loop.run_until_complete(
            parse_illust_info_msg(illust_id, self.aapi))
        loop.close()
        download_pic(illust_urls, illust_id, "large", self.aapi)
        file_dirs = [self.Config.download_path+f"/{illust_id}/" +
                     filename for filename in os.listdir(self.Config.download_path+f"/{illust_id}")]
        if len(file_dirs) == 1:
            bot.send_photo(chat_id=target,
                           photo=open(file_dirs[0], 'rb'),
                           caption=msg_text,
                           reply_markup=origin_link(illust_id),
                           parse_mode=ParseMode.HTML)
        else:
            tmp_sub_file_group = list()
            tmp_size = 0
            sub_file_groups = list()
            for file_dir in file_dirs:
                if tmp_size + os.path.getsize(file_dir) <= 5242880 and len(tmp_sub_file_group) + 1 <= 10:
                    tmp_sub_file_group.append(InputMediaPhoto(media=open(file_dir, 'rb'),
                                                              caption=msg_text,
                                                              parse_mode=ParseMode.HTML))
                else:
                    sub_file_groups.append(tmp_sub_file_group)
                    tmp_sub_file_group = [InputMediaPhoto(media=open(file_dir, 'rb'),
                                                          caption=msg_text,
                                                          parse_mode=ParseMode.HTML)]
                    tmp_size = os.path.getsize(file_dir)
            sub_file_groups.append(tmp_sub_file_group)
            for sub_file_group in sub_file_groups:
                bot.send_media_group(chat_id=target, media=sub_file_group)
            bot.send_text(chat_id=target,
                          text=msg_text,
                          reply_markup=origin_link(illust_id),
                          disable_web_page_preview=True,
                          parse_mode=ParseMode.HTML)
