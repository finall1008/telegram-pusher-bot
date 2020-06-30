# Telegram Pusher Bot
[![Require: Python 3.8](https://img.shields.io/badge/Python-3.8-blue)](https://www.python.org/)
[![Require: python-telegram-bot >= 12.6.1](https://img.shields.io/badge/python--telegram--bot-%3E%3D%2012.6.1-blue)](https://github.com/python-telegram-bot/python-telegram-bot)

一个简单的机器人，可以帮助你通过简易的步骤快速提取从其他来源获得的消息中的链接，将他们标记后推送到频道、群组。

特别的，如果推送内容为 BiliBili 动态内容，本项目在推送时将通过来自 [telegram-bili-feed-helper](https://github.com/simonsmh/telegram-bili-feed-helper) 的代码将其解析，从而解决 Telegram 不能为此类内容生成实时预览的问题。

## 它能做什么？

维护者目前将此项目与 [RSSHub](https://github.com/DIYgod/RSSHub)、[RSSBot](https://github.com/iovxw/rssbot) 同时使用，实现从社交网站爬取指定信息，经过筛选、分类后推送到频道供他人查看。

[查看详情](docs/What_can_this_do.md)

## 部署

1. 通过 `git clone https://github.com/finall1008/telegram-pusher-bot` 获取项目文件
2. 向 @BotFather 申请一个机器人
3. [修改配置文件](docs/Edit_config.md)
4. `pip install -r requirements.txt`
5. `python main.py`
6. 将你的机器人以及其他可能需要的机器人或用户添加到**频道**中，开始使用。

## 使用

[如何使用？](docs/How_to.md)

## 已知问题

**需要在频道中使用**：由于 Telegram 官方的限制，除非在频道中使用，否则我们无法获取其他机器人发布的消息。以后我们会通过自动转发功能来绕过这一限制。

**自定义标签功能暂时不可用**：它依赖 ForceReply 功能，而此功能在频道中不可用，需要等待我们添加群组相关的支持。

## Licence

![GitHub](https://img.shields.io/github/license/finall1008/telegram-pusher-bot)

## Credit

BiliBili 动态解析相关：Copyright © 2020 Simon Shi simonsmh@gmail.com，已在源代码中注明贡献部分。

其他：Copyright © 2020 finall1008 & Sssssaltyfish.