import aiosqlite


SCHEMA_SQL="""
    CREATE TABLE IF NOT EXISTS projects(
        id TEXT PRIMARY KEY ,
        call_id INTEGER NOT NULL,
        name TEXT,
        client TEXT);

    CREATE TABLE IF NOT EXISTS obligations(
        id TEXT PRIMARY KEY,
        project_id INTEGER NOT NULL,
        description TEXT,
        deadline TIMESTAMP,
        FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE);

    CREATE TABLE IF NOT EXISTS documents(
        id TEXT PRIMARY KEY,
        type INTEGER NOT NULL,
        path TEXT NOT NULL);

    CREATE TABLE IF NOT EXISTS referinte(
        id TEXT PRIMARY KEY,
        obligation_id INTEGER NOT NULL,
        document_id INTEGER NOT NULL,
        page INTEGER,
        text TEXT,
        chapter TEXT,
        subchapter TEXT,
        FOREIGN KEY(obligation_id) REFERENCES obligations(id) ON DELETE CASCADE,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE);
    """

async def create_database_schema(con: aiosqlite.Connection) -> None:
    await con.executescript(SCHEMA_SQL)
    await con.commit()

async def setup_database()-> aiosqlite.Connection:
    con = await aiosqlite.connect('documents.db')
    await create_database_schema(con)
    return con