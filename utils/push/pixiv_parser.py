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
)
from pixivpy_async import AppPixivAPI
import logging
import re
from utils import BaseConfig
from io import BytesIO

from .pixiv_illust import Illust, IllustInitError

logger = logging.getLogger("push_helper")


class PixivParser:
    status = False
    aapi = AppPixivAPI()
    id_regex = r"[1-9]\d*"

    class Config(BaseConfig, config_file="push_config.json"):
        pixiv_refresh_token: str = str()

        @classmethod
        def _check(cls, _attr_name: str, _attr_value: Any) -> Tuple[str, Any]:
            if _attr_name == "pixiv_refresh_token" and _attr_value == "":
                logger.exception(f"非法的 refresh_token。如果您不知道这是什么，请查看文档")
            else:
                return _attr_name, _attr_value

    @classmethod
    def send(self, url: str, classification: str, bot: Bot, target):

        def origin_link_button(_id: int) -> InlineKeyboardMarkup:
            return InlineKeyboardMarkup([[InlineKeyboardButton(text="原链接", url=f"https://www.pixiv.net/artworks/{_id}")]])

        illust_id = int(re.search(pattern=self.id_regex, string=url).group(0))

        try:
            illust = Illust(illust_id, self.Config.pixiv_refresh_token)
        except IllustInitError:
            return

        illust.download()

        images = illust.get_downloaded_images()

        if len(images) > 1:
            bot.send_media_group(chat_id=target, media=[
                InputMediaPhoto(BytesIO(image)) for image in images])
            bot.send_message(text=str(illust), chat_id=target,
                             reply_markup=origin_link_button(illust_id),
                             disable_web_page_preview=True,
                             parse_mode=ParseMode.HTML)
        else:
            print(str(illust))
            bot.send_photo(photo=BytesIO(images[0]), chat_id=target,
                           caption=str(illust),
                           reply_markup=origin_link_button(illust_id),
                           parse_mode=ParseMode.HTML)

        logger.info(f"Pixiv: 成功推送 {illust.id}")
