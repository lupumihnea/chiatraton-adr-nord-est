import sqlite3


def create_database_schema(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS projects(
        id INTEGER PRIMARY KEY ,
        call_id INTEGER NOT NULL,
        time_ending TIMESTAMP NOT NULL,
        name TEXT);

    CREATE TABLE IF NOT EXISTS obligations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        description TEXT,
        deadline TIMESTAMP,
        importance INTEGER,
        FOREIGN KEY(project_id) REFERENCES project(id) ON DELETE CASCADE);

    CREATE TABLE IF NOT EXISTS documents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type INTEGER NOT NULL,
        path TEXT);

    CREATE TABLE IF NOT EXISTS references(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        obligation_id INTEGER NOT NULL,
        document_id INTEGER NOT NULL,
        page INTEGER,
        text TEXT,
        chapter TEXT,
        subchapter TEXT,
        FOREIGN KEY(obligation_id) REFERENCES obligation(id) ON DELETE CASCADE,
        FOREIGN KEY(document_id) REFERENCES document(id) ON DELETE CASCADE);
    """)

def setup_database():
    con = sqlite3.connect('documents.db')
    create_database_schema(con)
    return con