import asyncio

from app.core.config import get_settings
from app.core.db import SessionFactory, engine
from app.core.logging import configure_logging
from app.seed.loader import seed_demo_events, seed_reference_data


async def main() -> None:
    configure_logging()
    async with SessionFactory() as session:
        await seed_reference_data(session)
        if get_settings().seed_demo_data:
            await seed_demo_events(session)
        await session.commit()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
