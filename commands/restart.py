from telegram.ext import CommandHandler, CallbackContext, Filters, Updater
from telegram import Bot, Update
import utils
import os
import sys
import logging
from threading import Thread
from functools import partial, reduce


logger = logging.getLogger('push_helper')


def get_filter(bot: Bot):
    return (
        utils.get_filter(utils.Config.watchers)
        & Filters.user(
            user_id=reduce(
                frozenset.union, map(
                    frozenset, map(
                        partial(utils.get_admin, bot), utils.Config.watchers
                    )
                )
            )
        )
    )


def describe():
    return "远程重启 Bot"


def register(updater: Updater):
    def run(update: Update, context: CallbackContext):
        #print(context) # DEBUG
        def stop_and_restart():
            updater.stop()
            os.execl(sys.executable, sys.executable, *sys.argv,
                     "--restart", str(update.effective_chat.id))

        update.effective_message.reply_text(text="正在重启bot...")
        logger.info(f"正在重启 Bot")
        Thread(target=stop_and_restart).start()

    dp = updater.dispatcher
    bot = updater.bot

    dp.add_handler(CommandHandler(__name__, run, filters=get_filter(bot)))
    # dp.add_handler(CommandHandler(__name__, run, filters=Filters.all)) # DEBUG
