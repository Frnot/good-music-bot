import os
import aiosqlite
import asyncio
import sys
import logging
from typing import TypeVar, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase

T = TypeVar('T')
log = logging.getLogger(__name__)


db_file = 'data.db'


async def load() -> None:
    global engine
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}",echo=True)

    # async_sessionmaker: a factory for new AsyncSession objects.
    # expire_on_commit - don't expire objects after transaction commit
    global async_session
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    log.info("Initializing database")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database loaded")


def close():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(engine.dispose())
    loop.stop()
    log.info("Closed database connection.")


async def insert_row(entry) -> None:
    async with async_session() as session:
        async with session.begin():
            session.add(entry)


async def delete_row(entry_type, id) -> None:
    async with async_session() as session:
        async with session.begin():
            result = await session.get(entry_type, id)
            if result:
                await session.delete(result)


async def query(entry_type: T, id) -> T:
    async with async_session() as session:
        return await session.get(entry_type, id)


async def query_all(entry_type: T) -> List[T]:
    async with async_session() as session:
        return (await session.scalars(select(entry_type))).all()



class Base(AsyncAttrs, DeclarativeBase):
    pass
