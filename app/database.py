import sqlite3
import os
from contextlib import contextmanager
from app.config import Config


def get_db_path():
    return os.path.join(Config.DATA_DIR, "tinytts.db")


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversions (
                id TEXT PRIMARY KEY,
                created_at DATETIME NOT NULL,
                input_type TEXT NOT NULL,
                original_filename TEXT,
                source_path TEXT NOT NULL,
                content_preview TEXT NOT NULL,
                content_length INTEGER NOT NULL,
                voice TEXT NOT NULL,
                speed REAL NOT NULL,
                audio_path TEXT NOT NULL,
                audio_duration REAL,
                audio_size INTEGER NOT NULL,
                full_text TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_created_at ON conversions(created_at);
        """)
        # Create FTS table if not exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='conversions_fts'"
        )
        if not cursor.fetchone():
            conn.executescript("""
                CREATE VIRTUAL TABLE conversions_fts USING fts5(
                    full_text, content_preview, original_filename, content='conversions', content_rowid='rowid'
                );

                CREATE TRIGGER conversions_ai AFTER INSERT ON conversions BEGIN
                    INSERT INTO conversions_fts(rowid, full_text, content_preview, original_filename)
                    VALUES (NEW.rowid, NEW.full_text, NEW.content_preview, NEW.original_filename);
                END;

                CREATE TRIGGER conversions_ad AFTER DELETE ON conversions BEGIN
                    INSERT INTO conversions_fts(conversions_fts, rowid, full_text, content_preview, original_filename)
                    VALUES('delete', OLD.rowid, OLD.full_text, OLD.content_preview, OLD.original_filename);
                END;

                CREATE TRIGGER conversions_au AFTER UPDATE ON conversions BEGIN
                    INSERT INTO conversions_fts(conversions_fts, rowid, full_text, content_preview, original_filename)
                    VALUES('delete', OLD.rowid, OLD.full_text, OLD.content_preview, OLD.original_filename);
                    INSERT INTO conversions_fts(rowid, full_text, content_preview, original_filename)
                    VALUES (NEW.rowid, NEW.full_text, NEW.content_preview, NEW.original_filename);
                END;
            """)


@contextmanager
def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
