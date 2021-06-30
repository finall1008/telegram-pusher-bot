#! /usr/bin/env python3.8

import logging
import os
import sys

from importlib import import_module
from signal import SIGINT, SIGTERM, SIGABRT, signal
from functools import wraps
from telegram import Update
from telegram.ext import Updater, CallbackContext

from utils import (
    Config,
    timeout,
    WrapType,
    TimeLimitReached,
)
from markup import main_buttons
from interactive import handle  # DEBUG

# > For future use: multiprocessing demand
#import telegram.ext.updater
#from multiprocessing import JoinableQueue
#telegram.ext.updater.Queue = JoinableQueue
# <

submodules = {
    name: import_module(name)
    for name in [
        'commands',
        'auto_forward',
        'markup'
    ]
}

# >


@ wraps(Updater.idle)
def idle(self: Updater, stop_signals=(SIGINT, SIGTERM, SIGABRT)):
    for sig in stop_signals:
        signal(sig, self._signal_handler)

    self.is_idle = True

    while self.is_idle:
        command = input('>>> ')
        handle(command)


Updater.idle = idle
# <

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger('push_helper')


def error(update: Update, context: CallbackContext):
    logger.exception(f"更新 {update} 导致了错误: {error}")


if __name__ == "__main__":
    updater: Updater = Updater(
        token=Config.token, use_context=True, workers=len(os.sched_getaffinity(0))*2)

    for submodule in submodules.values():
        submodule.register(updater)

    dp = updater.dispatcher
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
