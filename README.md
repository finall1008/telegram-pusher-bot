# Telegram Pusher Bot
[![Require: Python 3.8](https://img.shields.io/badge/Python-3.8-blue)](https://www.python.org/)
[![Require: python-telegram-bot >= 12.8](https://img.shields.io/badge/python--telegram--bot-%3E%3D%2012.6.1-blue)](https://github.com/python-telegram-bot/python-telegram-bot)

一个简单的 Bot ，可以帮助你通过简易的步骤快速提取从其他来源获得的消息中的链接，将他们标记后推送到频道、群组。

特别的，如果推送内容为 BiliBili 动态内容，本项目在推送时将通过来自 [telegram-bili-feed-helper](https://github.com/simonsmh/telegram-bili-feed-helper) 的代码将其解析，从而解决 Telegram 不能为此类内容生成实时预览的问题。

## 它能做什么？

维护者目前将此项目与 [RSSHub](https://github.com/DIYgod/RSSHub)、[RSSBot](https://github.com/iovxw/rssbot) 同时使用，实现从社交网站爬取指定信息，经过筛选、分类后推送到频道供他人查看。

[查看详情](docs/What_can_this_do.md)

## 部署

1. 通过 `git clone https://github.com/finall1008/telegram-pusher-bot` 获取项目文件
2. 向 @BotFather 申请一个 Bot 
3. [修改配置文件](docs/Edit_config.md)
4. `pip install -r requirements.txt`
5. 将本 Bot 和其他 Bot 、用户加入监视器**群组**，并确保本 Bot 为管理员。
6. `python main.py`

## 使用

[如何使用？](docs/How_to.md)

## 关于最近的更新

在最近的更新中，本项目添加了一些功能，且**工作流有较大变化**。请参考[如何使用](docs/How_to.md)。

## 参与项目

请参见[关于为本项目添加新模块的说明](docs/Create_modules.md)。

## Licence

![GitHub](https://img.shields.io/github/license/finall1008/telegram-pusher-bot)

## Credit

BiliBili 动态解析相关：Copyright © 2020 Simon Shi simonsmh@gmail.com，已在源代码中注明贡献部分。

其他：Copyright © 2020 finall1008 & Sssssaltyfish.