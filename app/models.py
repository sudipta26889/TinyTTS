import uuid
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional
from app.database import get_connection


@dataclass
class Conversion:
    id: str
    created_at: datetime
    input_type: str
    original_filename: Optional[str]
    source_path: str
    content_preview: str
    content_length: int
    voice: str
    speed: float
    audio_path: str
    audio_duration: Optional[float]
    audio_size: int
    full_text: str

    @classmethod
    def create(cls, input_type: str, original_filename: Optional[str], source_path: str,
               full_text: str, voice: str, speed: float, audio_path: str,
               audio_duration: Optional[float], audio_size: int) -> "Conversion":
        conversion = cls(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            input_type=input_type,
            original_filename=original_filename,
            source_path=source_path,
            content_preview=full_text[:200],
            content_length=len(full_text),
            voice=voice,
            speed=speed,
            audio_path=audio_path,
            audio_duration=audio_duration,
            audio_size=audio_size,
            full_text=full_text
        )
        conversion.save()
        return conversion

    def save(self):
        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO conversions
                (id, created_at, input_type, original_filename, source_path, content_preview,
                 content_length, voice, speed, audio_path, audio_duration, audio_size, full_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (self.id, self.created_at.isoformat(), self.input_type, self.original_filename,
                  self.source_path, self.content_preview, self.content_length, self.voice,
                  self.speed, self.audio_path, self.audio_duration, self.audio_size, self.full_text))

    @classmethod
    def get_by_id(cls, id: str) -> Optional["Conversion"]:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM conversions WHERE id = ?", (id,)).fetchone()
            if row:
                return cls._from_row(row)
        return None

    @classmethod
    def get_all(cls, limit: int = 50, offset: int = 0) -> list["Conversion"]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM conversions ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            return [cls._from_row(row) for row in rows]

    @classmethod
    def search(cls, query: str, from_date: Optional[str] = None,
               to_date: Optional[str] = None, limit: int = 50, offset: int = 0) -> list["Conversion"]:
        with get_connection() as conn:
            sql = """
                SELECT c.* FROM conversions c
                JOIN conversions_fts fts ON c.rowid = fts.rowid
                WHERE conversions_fts MATCH ?
            """
            params = [query]

            if from_date:
                sql += " AND c.created_at >= ?"
                params.append(from_date)
            if to_date:
                sql += " AND c.created_at <= ?"
                params.append(to_date)

            sql += " ORDER BY c.created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(sql, params).fetchall()
            return [cls._from_row(row) for row in rows]

    @classmethod
    def get_oldest(cls) -> Optional["Conversion"]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM conversions ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            if row:
                return cls._from_row(row)
        return None

    def delete(self):
        with get_connection() as conn:
            conn.execute("DELETE FROM conversions WHERE id = ?", (self.id,))

    @classmethod
    def _from_row(cls, row) -> "Conversion":
        return cls(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            input_type=row["input_type"],
            original_filename=row["original_filename"],
            source_path=row["source_path"],
            content_preview=row["content_preview"],
            content_length=row["content_length"],
            voice=row["voice"],
            speed=row["speed"],
            audio_path=row["audio_path"],
            audio_duration=row["audio_duration"],
            audio_size=row["audio_size"],
            full_text=row["full_text"]
        )

    def to_dict(self, include_full_text: bool = False) -> dict:
        data = {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "input_type": self.input_type,
            "original_filename": self.original_filename,
            "content_preview": self.content_preview,
            "content_length": self.content_length,
            "voice": self.voice,
            "speed": self.speed,
            "audio_duration": self.audio_duration,
            "audio_size": self.audio_size
        }
        if include_full_text:
            data["full_text"] = self.full_text
        return data
