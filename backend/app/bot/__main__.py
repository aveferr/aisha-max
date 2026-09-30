import asyncio
import logging
import signal

from app.assistant.factory import get_parser
from app.bot.client import MaxClient
from app.bot.dispatcher import BotDispatcher
from app.bot.workers import run_polling, run_reminders
from app.core.config import get_settings
from app.core.db import SessionFactory, engine
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.max_bot_token:
        logger.error("MAX_BOT_TOKEN не задан — бот не запущен (API работает без него)")
        return

    client = MaxClient(
        settings.max_bot_token, settings.max_api_url, ca_bundle=settings.max_ca_bundle
    )
    dispatcher = BotDispatcher(client, SessionFactory, get_parser(), settings)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))

    logger.info("Бот запущен")
    workers = [
        asyncio.create_task(run_polling(client, dispatcher, stop)),
        asyncio.create_task(run_reminders(client, SessionFactory, settings, stop)),
    ]
    try:
        await stop.wait()
    finally:
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        await client.aclose()
        await engine.dispose()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
