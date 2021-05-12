import asyncio
import logging

from bs4 import BeautifulSoup
from pixivpy_async import AppPixivAPI
from pixivpy_async.net import Net


class DownloadError(Exception):
    pass


class IllustInitError(Exception):
    pass


class LoginError(IllustInitError):
    pass


class GetInfoError(IllustInitError):
    pass

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger("push_helper")


class Illust:

    aapi = AppPixivAPI(env=True)

    def __init__(self, illust_id: int, refresh_token:str):
        async def init_appapi() -> bool:
            try:
                await self.aapi.login(refresh_token=refresh_token)
            except:
                return False
            self.aapi.set_accept_language("zh-CN")
            return True

        async def get_info() -> bool:
            try:
                json_result = await self.aapi.illust_detail(self.id)
            except:
                return False

            info = json_result.illust

            self.caption = str()
            if info.caption != "":
                soup = BeautifulSoup(info.caption, "html.parser")
                self.caption = "\n" + soup.get_text()

            self.title = info.title
            self.author = (info.user.name, info.user.id)

            self.tags = [(tag.name, tag.translated_name) for tag in info.tags]

            if info.page_count == 1:
                self.urls = [info.image_urls.large]
                self.original_urls = [info.meta_single_page.original_image_url]
            else:
                self.urls = [
                    page.image_urls.large for page in info.meta_pages]
                self.original_urls = [
                    page.image_urls.original for page in info.meta_pages]

            return True

        loop = asyncio.new_event_loop()
        login_result = loop.run_until_complete(init_appapi())
        loop.close()
        if not login_result:
            logger.exception("Pixiv 登录失败")
            raise LoginError
        logger.info("Pixiv 登录成功")

        self.id: int = illust_id

        self.__images: list = list()

        loop = asyncio.new_event_loop()
        get_info_result = loop.run_until_complete(get_info())
        loop.close()
        if not get_info_result:
            logger.exception("插画信息获取失败")
            raise GetInfoError

    def __str__(self):
        tags_text = str()
        for tag in self.tags:
            tags_text = tags_text + \
                f"<a href=\"https://www.pixiv.net/tags/{tag[0]}/artworks\">{tag[0]}</a>"
            if tag[1]:
                tags_text = tags_text + f" ({tag[1]})"
            tags_text = tags_text+", "

        return f"<b>标题：</b>{self.title}\n<b>作者：</b><a href=\"https://www.pixiv.net/users/{self.author[1]}\">{self.author[0]}</a>\n<b>简介：</b>{self.caption}\n<b>标签：</b>{tags_text}"

    async def __download_single_image(self, url: str, size_hint: str, page_hint: int):
        try:
            content, type = await self.aapi.down(url, "https://app-api.pixiv.net/")
        except:
            logger.exception(f"{self.id} {size_hint} 第 {page_hint} 张下载错误")
            raise DownloadError

        if type is not None and type.find("image") != -1:
            self.__images.append((page_hint, content))
        else:
            logger.exception(f"{self.id} {size_hint} 第 {page_hint} 张下载错误")
            raise DownloadError

        logger.info(f"成功下载 {self.id} {size_hint} 第 {page_hint} 张")

    def __download_images(self, original: bool = False):
        page = 0
        loop = asyncio.new_event_loop()

        if not original:
            urls = self.urls
            size_hint = "large"
        else:
            urls = self.original_urls
            size_hint = "original"

        tasks = list()
        for url in urls:
            tasks.append(self.__download_single_image(url, size_hint, page))
            page = page + 1

        try:
            loop.run_until_complete(asyncio.gather(*tasks, loop=loop))
        except DownloadError:
            pass
        finally:
            loop.close()

        logger.info(f"成功下载 {self.id} 全部 {size_hint} 图片")

    def download(self):
        self.__download_images()

    def download_original(self):
        self.__download_images(True)

    def get_downloaded_images(self):
        if not len(self.__images):
            return None

        self.__images.sort(key=lambda elem: elem[0])

        return [elem[1] for elem in self.__images[:9]]
