import re
import aiohttp
import asyncio

from itertools import compress, chain
from PIL import Image
from typing import Union, Optional, Tuple, Any, overload, Callable
from io import BytesIO
from functools import cached_property, partial, wraps
from bs4 import BeautifulSoup, Tag

# ! This part is unfinished for now

headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.87 Safari/537.36"
}

'''headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4221.4 Safari/537.36"
}'''
IMAGE_PIXEL_COUNT = 2500000


def _modify(image_url: str) -> str:
    return image_url.replace(r'=small', r'=large').replace(r'=medium', r'=large')

async def _get_resp(url: str, method: str, extra_headers = dict(), args = list(), kwargs = dict()) -> Tuple[int, Any]:
    extra_headers.update(headers)
    async with aiohttp.ClientSession(trust_env=True, headers=extra_headers) as session:
        async with session.get(url) as resp:
            return resp.status, await getattr(resp, method)(*args, **kwargs)

async def get_html(url: str, extra_headers = dict()) -> Tuple[int, str]:
    return await _get_resp(url, 'text', extra_headers)

async def get_data(url: str, extra_headers = dict()) -> Tuple[int, bytes]:
    return await _get_resp(url, 'read', extra_headers)

async def get_image(image_url_or_tag: Union[str, Tag]) -> Optional[Image.Image]:
    image_url = image_url_or_tag if isinstance(image_url_or_tag, str) else image_url_or_tag['src']
    print(image_url)
    image_url = url(_modify(image_url))
    try:
        status, data = await get_data(image_url)
    except aiohttp.InvalidURL:
        return None
    if 200 <= status < 300:
        try:
            return Image.open(BytesIO(data))
        except Image.UnidentifiedImageError:
            return None
    return None

@ overload
def url(string: str) -> str: ...

@ overload
def url(func: Callable[..., str]) -> Callable[..., str]: ...

def url(func_or_str):
    def urled(s: str):
        if s and not s.startswith(('http:', 'https:')):
            return f"https:{s}"

    if callable(func_or_str):
        @ wraps(func_or_str)
        def wrapped(*args, **kwargs):
            return urled(func_or_str(*args, **kwargs))
        return wrapped
    else:
        return urled(func_or_str)


class HTMLData:
    SEARCH_LIMIT: int = 20

    def __init__(self, html: str):
        super().__init__()
        self.__soup: BeautifulSoup = BeautifulSoup(html)
        self.__image_tags = (tag for tag in self.__soup.find_all('img', src=True, limit=self.SEARCH_LIMIT))
        self._find_meta = partial(self.soup.find, 'meta')
        self._find_n_get = lambda s: self.soup.find(s).get_text().strip()

    def __getattr__(self, name: str):
        return getattr(self.__soup, name)

    @ property
    def soup(self) -> BeautifulSoup:
        return self.__soup

    @ cached_property
    def info_title(self) -> str:
        ret = (
            self._find_meta(property='og:title')
            or self._find_meta(attrs={'name': 'twitter:title'})
        )
        if ret is None:
            ret = (
                self.__soup.title
                or self.__soup.find('h1')
                or self.__soup.find('h2')
            )
            ret = ret.string if ret is not None else str()
        else:
            ret = ret.get('content', '')
        return ret.strip()

    @ cached_property
    def info_site_name(self) -> str:
        if ret := self._find_meta(property='og:site_name'):
            return ret.get('content', '')
        else:
            return str()

    @ cached_property
    def info_description(self) -> str:
        ret = (
            self._find_meta(property='og:description')
            or self._find_meta(attrs={'name': 'description'})
            or self._find_meta(attrs={'name': 'twitter:description'})
        )
        if ret is None:
            ret = self.__soup.find('p')
            ret = ret.string if ret is not None else str()
        else:
            ret = ret.get('content', '')
        return ret.strip()

    @ cached_property
    @ url
    def info_image(self) -> str:
        if ret := self._find_meta(property='og:image'):
            return ret.get('content', '')
        elif ret := self.__soup.find('link', rel='image_src'):
            return ret.href
        elif ret := self._find_meta(attrs={'name': 'twitter:image'}):
            return ret.get('content', '')
        else:
            return str()

    @ cached_property
    @ url
    def info_url(self) -> str:
        if ret := self.__soup.find('link', rel='canonical'):
            return ret.get('href', '')
        elif ret:= self._find_meta(property='og:url'):
            return ret.get('content', '')
        else:
            return str()

    @ cached_property
    def info_type(self) -> str:
        if ret := self._find_meta(property='og:type'):
            return ret.get('content', '')
        else:
            return str()

    @ cached_property
    def _first_image(self) -> Tuple[str, Optional[Image.Image]]:
        for tag in self.__image_tags:
            u = tag['src']
            loop = asyncio.new_event_loop()
            image = loop.run_until_complete(get_image(u))
            loop.close()

            width, height = map(int, (tag.get('width', '0'), tag.get('height', '0')))
            if not (width and height) and (image is not None):
                width, height = image.size
            if width*height >= IMAGE_PIXEL_COUNT:
                return u, image
            else:
                continue
        return '', None

    @ cached_property
    def first_image(self) -> str:
        return self._first_image[0]

    @ cached_property
    def first_image_data(self) -> Optional[Image.Image]:
        return self._first_image[1]

    @ cached_property
    def _main_image(self) -> Tuple[str, Optional[Image.Image]]:
        def get_size(tag: Tag, image: Image.Image) -> int:
            width, height = map(int, (tag.get('width', '0'), tag.get('height', '0')))
            if not width*height:
                width, height = image.size
            return width * height

        first = self._first_image
        rest = list(self.__image_tags)
        loop = asyncio.new_event_loop()
        print(rest) # DEBUG
        images = loop.run_until_complete(asyncio.gather(*map(get_image, rest)))
        loop.close()
        return_tag, return_image = max(chain(zip(rest, images), first), key=lambda t: get_size(*t))
        return return_tag['src'], return_image

    @ cached_property
    def main_image(self) -> str:
        return self._main_image[0]

    @ cached_property
    def main_image_data(self) -> str:
        return self._main_image[1]
