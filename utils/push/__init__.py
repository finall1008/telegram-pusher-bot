import re
import logging

from typing import Dict, Set, List, Optional
from telegram import Bot
from telegram.ext.dispatcher import run_async

import utils
import utils.regexes as regex
from utils import Config
from .bilifeed import send_bili_feed
from .pixiv_parser import PixivParser


logger = logging.getLogger("push_helper")


class Message():
    def __init__(self, url: str):
        self.url: str = url
        self.tag_indices: Set[int] = set()
        self.target_indices: Set[int] = set()
        self.customized_tags: List[str] = list()
        self.customized_targets: List[utils.User] = list()

    def get_tags(self):
        return [Config.tags[i] for i in self.tag_indices] + self.customized_tags

    def get_targets(self):
        return [Config.targets[i] for i in self.target_indices] + self.customized_targets

    def __str__(self) -> str:
        return "url: {}\ntags: {}\ntargets: {}".format(
            self.url,
            " ".join(self.get_tags()),
            " ".join(map(str, self.get_targets()))
        )

    def __repr__(self) -> str:
        return f"<Message:\n{ self.__str__() }\n>"

    def push(self, targets_additional: Optional[List[utils.User]] = None, tags_additional: Optional[List[str]] = None):
        bot = Bot(token=Config.token)
        sep = "\n\n"
        self_tags = self.get_tags()
        if tags_additional:
            self_tags += tags_additional
        if targets_additional:
            self_targets = self.get_targets() + targets_additional
        else:
            self_targets = self.get_targets()
        if not self_targets:
            self_targets = [Config.targets[0]]
        if not self_tags:
            sep = ""

        for target in self_targets:
            if not re.search(regex.bili, self.url) and not re.search(regex.pixiv, self.url):
                bot.send_message(
                    target,
                    self.url + sep +
                    "  ".join(map(lambda tag: "#" + tag, self_tags))
                )
            elif re.search(regex.pixiv, self.url):
                PixivParser.send(
                    self.url,
                    sep + "  ".join(["#" + tag for tag in self_tags]),
                    bot,
                    target
                )
            else:
                send_bili_feed(
                    self.url,
                    sep + "  ".join([r"\#" + tag for tag in self_tags]),
                    bot,
                    target
                )
            logger.info("将 {} 推送至 {}".format(self.url, target))


waiting_to_push: Dict[int, Message] = {}
