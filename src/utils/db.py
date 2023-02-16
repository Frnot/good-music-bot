import os
import aiosqlite
import asyncio
import sys
import logging
log = logging.getLogger(__name__)



db_file = 'data.db'
init_tables = {
    "cmd_prefix":"CREATE TABLE IF NOT EXISTS 'cmd_prefix' (guild_id INT PRIMARY KEY, prefix TEXT);",
    "banlist":"CREATE TABLE IF NOT EXISTS 'banlist' (user_id INT PRIMARY KEY);",
}
# TODO: handle changing the table definitions. avoid "UNIQUE constraint failed errors"


### "Constructor"
async def load():
    global conn

    log.info("Initializing database")
    if os.path.exists(db_file):
        conn = await connect()
        await reload_tables(conn)
    else:
        log.info("Creating new database")
        conn = await new_db()
    log.info("Database loaded")


def close():
    with asyncio.new_event_loop() as loop:
        loop.run_until_complete(conn.close())
    log.info("Closed database connection.")


async def new_db():
    conn = await connect()

    log.info("Setting up database tables")
    for key, value in init_tables.items():
        log.debug(f"Creating database table {key}")
        await conn.execute(value)

    await conn.commit()
    return conn


async def connect():
    try:
        conn = await aiosqlite.connect(db_file)
    except Exception as e:
        print(e)
        sys.exit("Database connect error")
    return conn


async def reload_tables(conn):
    log.info("Updating database tables")
    for key, value in init_tables.items():
        log.debug(f"Updating database table {key}")
        await conn.execute(value)
    
    await conn.commit()


async def select(column, table, key, search_value):
    """SELECT {column} FROM {table} WHERE {key}={search_value}"""
    sql = f"SELECT {column} FROM {table} WHERE {key}={search_value}"
    log.debug(f"Sending query: '{sql}' to database")

    try:
        cursor = await conn.execute(sql)
    except Exception as e:
        log.error(f"SQL query 'select' failed: {e}")
        raise e

    result = await cursor.fetchone()
    log.debug(f"Query result: {result}")

    if result is None:
        return result
    else:
        return result[0]


async def select_all(table):
    sql = f"SELECT * FROM {table}"
    log.debug(f"Sending query: '{sql}' to database")

    try:
        cursor = await conn.execute(sql)
    except Exception as e:
        log.error(f"SQL query 'select' failed: {e}")
        raise e
    
    result = await cursor.fetchall()
    log.debug(f"Query result: {result}")

    return result


# Will always send SQL update. a little inefficient
async def upsert(table, data):
    columns = ', '.join(str(row[0]) for row in data)
    param = ', '.join('?'*len(data))
    payload = [row[1] for row in data]
    payload_string = ', '.join(str(word) for word in payload)

    sql1 = f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({param})"
    sql2 = f"UPDATE {table} SET ({columns}) = ({param})"

    log.debug(f"Sending query: '{sql1}, ({payload_string})' to database")
    try:
        await conn.execute(sql1, payload)
        await conn.commit()
    except Exception as e:
        log.error(f"SQL query 'insert' failed: {e}")
        raise e

    log.debug(f"Sending query: '{sql2}, ({payload_string})' to database")
    try:
        await conn.execute(sql2, payload)
        await conn.commit()
    except Exception as e:
        log.error(f"SQL query 'update' failed: {e}")
        raise e


async def insert(table, data):
    """Data format: [[key_name, key_value], [column_name, column_value]]
    Produces a query: INSERT INTO {table} key_name, column_name VALUES ?, ?  (key_value, column_value)"""

    sql = f"INSERT INTO {table} ({', '.join(str(row[0]) for row in data)}) VALUES ({', '.join('?'*len(data))})"
    payload = [row[1] for row in data]

    log.debug(f"Sending query: '{sql}, ({', '.join(str(word) for word in payload)})' to database")
    try:
        await conn.execute(sql, payload)
        await conn.commit()
    except Exception as e:
        log.error(f"SQL query 'insert' failed: {e}")
        raise e


async def update(table, data):
    sql = f"UPDATE {table} SET ({', '.join(str(row[0]) for row in data)}) = ({', '.join('?'*len(data))}) WHERE {data[0][0]} = ?"
    payload = [row[1] for row in data]
    payload.append(data[0][1])

    log.debug(f"Sending query: '{sql}, ({', '.join(str(word) for word in payload)})' to database")
    try:
        await conn.execute(sql, payload)
        await conn.commit()
    except Exception as e:
        log.error(f"SQL query 'update' failed: {e}")
        raise e


async def delete(table, data):
    sql = f"DELETE FROM {table} WHERE {data[0]} = {data[1]}"
    log.debug(f"Sending query: '{sql}' to database")
    try:
        await conn.execute(sql)
        await conn.commit()
    except Exception as e:
        log.error(f"SQL query 'delete' failed: {e}")
        raise e
