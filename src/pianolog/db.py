import sqlite3
from pathlib import Path


class PianoLogDB:
    """
    A lightweight wrapper around the piano practice SQLite database.
    Handles schema creation and provides a clean connection interface.
    """

    def __init__(self, db_name: str = "piano.db"):
        # Resolve database path: project_root/database/<db_name>
        root = Path(__file__).resolve().parents[2]
        db_dir = root / "database"
        db_dir.mkdir(exist_ok=True)

        self.db_path = db_dir / db_name
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

        self._create_schema()

    # ---------------------------------------------------------
    # Schema creation
    # ---------------------------------------------------------
    def _create_schema(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS composers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT UNIQUE
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS pieces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name TEXT NOT NULL,
            normalized_name TEXT,
            composer_id INTEGER,
            opus TEXT,
            number TEXT,
            key TEXT,

            UNIQUE(canonical_name, composer_id),

            FOREIGN KEY (composer_id) REFERENCES composers(id)
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS piece_aliases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alias TEXT NOT NULL,
            normalized_alias TEXT,
            piece_id INTEGER,

            FOREIGN KEY (piece_id) REFERENCES pieces(id)
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            duration_min INTEGER,
            raw_text TEXT
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,

            type TEXT CHECK (
                type IN ('warmup', 'piece', 'improvisation', 'sight_reading')
            ),

            piece_id INTEGER,
            composer_id INTEGER,
            piece_name TEXT,
            composer_name TEXT,
            key TEXT,
            section TEXT,
            bars TEXT,

            exercise_name TEXT,
            tempo INTEGER,
            repetitions INTEGER,

            focus TEXT,
            notes TEXT,

            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (piece_id) REFERENCES pieces(id),
            FOREIGN KEY (composer_id) REFERENCES composers(id)
        )
        """)

        self.conn.commit()

    # ---------------------------------------------------------
    # Utility
    # ---------------------------------------------------------
    def close(self):
        self.conn.commit()
        self.conn.close()

    # ---------------------------------------------------------
    # Composer Helper
    # ---------------------------------------------------------
    def get_or_create_composer(self, name: str | None):
        if not name:
            return None

        norm = name.lower().strip()

        self.cursor.execute(
            "SELECT id FROM composers WHERE normalized_name = ?",
            (norm,)
        )
        row = self.cursor.fetchone()
        if row:
            return row[0]

        self.cursor.execute(
            "INSERT INTO composers (name, normalized_name) VALUES (?, ?)",
            (name, norm)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    # ---------------------------------------------------------
    # Piece Helper
    # ---------------------------------------------------------

    def get_or_create_piece(self, piece_name: str | None, composer_id: int | None):
        if not piece_name:
            return None

        norm = piece_name.lower().strip()

        self.cursor.execute("""
            SELECT id FROM pieces
            WHERE normalized_name = ? AND composer_id IS ?
        """, (norm, composer_id))
        row = self.cursor.fetchone()
        if row:
            return row[0]

        self.cursor.execute("""
            INSERT INTO pieces (canonical_name, normalized_name, composer_id)
            VALUES (?, ?, ?)
        """, (piece_name, norm, composer_id))

        self.conn.commit()
        return self.cursor.lastrowid

    # ---------------------------------------------------------
    # Log session method
    # ---------------------------------------------------------

    def log_session(self, session: dict):
        # Insert session
        self.cursor.execute(
            "INSERT INTO sessions (date, duration_min, raw_text) VALUES (?, ?, ?)",
            (session["date"], session["duration_min"], session["raw_text"])
        )
        session_id = self.cursor.lastrowid

        # Insert activities
        for act in session["activities"]:
            composer_id = self.get_or_create_composer(act.get("composer_name"))
            piece_id = self.get_or_create_piece(act.get("piece_name"), composer_id)

            self.cursor.execute("""
                INSERT INTO activities (
                    session_id, type,
                    piece_id, composer_id,
                    piece_name, composer_name,
                    key, section, bars,
                    exercise_name, tempo, repetitions,
                    focus, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                act.get("type"),

                piece_id,
                composer_id,

                act.get("piece_name"),
                act.get("composer_name"),

                act.get("key"),
                act.get("section"),
                act.get("bars"),

                act.get("exercise_name"),
                act.get("tempo"),
                act.get("repetitions"),

                act.get("focus"),
                act.get("notes"),
            ))

        self.conn.commit()
