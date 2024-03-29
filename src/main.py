import logging
import os
import sys
import time

import aiohttp
from dotenv import load_dotenv

import bot_main
from modules import admin_commands
from utils import logger

debug = True
quiet = False


for arg in sys.argv:
    if arg == '-q':
        print("Quiet mode enabled")
        quiet = True


# Start the logging system
logger.init(debug, quiet)
log = logging.getLogger(__name__)


# Get token from .env file
load_dotenv()
token = os.getenv("TOKEN")
assert token is not None, "No token in .env file"


attempts = 5

while attempts > 0:
    attempts -= 1
    try:
        # Run the Bot
        log.info("Starting bot")
        bot_main.run_bot(token)

    except aiohttp.ClientConnectionError:
        log.info("Failed to connect, retrying")
        time.sleep(5)
        continue

    finally:
        # Stop logging queue listener and flush queue
        logger.stop()

        # If shutting down because of restart, execute main with the same arguments
        if admin_commands.restart:
            print("Restarting...")

            if sys.platform.startswith('linux'):
                argv = [sys.executable, __file__] + sys.argv[1:]
            else:
                argv = [f"\"{sys.executable}\"", f"\"{__file__}\""] + sys.argv[1:]

            try:
                print(f"Running command: 'os.execv({sys.executable}, {argv})'")
                os.execv(sys.executable, argv)
            except Exception as e:
                print(e)
                logger.start()
                log.error(f"Command: 'os.execv({sys.executable}, {argv})' failed.")
                log.error(e)
                log.fatal("Cannot restart. exiting.")
                logger.stop()
        break
