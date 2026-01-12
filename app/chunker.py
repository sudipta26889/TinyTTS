import re
from typing import Generator
from app.config import Config

# Minimum characters for a valid chunk (skip chunks with just punctuation/whitespace)
MIN_CHUNK_CHARS = 3


def is_valid_chunk(text: str) -> bool:
    """Check if chunk has enough actual content to be worth converting."""
    stripped = text.strip()
    if not stripped:
        return False
    # Must have at least some alphanumeric content
    alphanumeric = re.sub(r'[^a-zA-Z0-9]', '', stripped)
    return len(alphanumeric) >= MIN_CHUNK_CHARS


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, preserving sentence boundaries."""
    # Split on sentence-ending punctuation followed by space or end
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def split_into_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs."""
    paragraphs = re.split(r'\n\s*\n', text)
    return [p.strip() for p in paragraphs if p.strip()]


def chunk_text(text: str, max_chunk_size: int = None) -> Generator[str, None, None]:
    """Split text into chunks suitable for TTS processing.

    Preserves paragraph and sentence boundaries where possible.
    Filters out empty or invalid chunks.

    Args:
        text: The text to chunk
        max_chunk_size: Maximum characters per chunk (defaults to config)

    Yields:
        Valid text chunks only
    """
    if max_chunk_size is None:
        max_chunk_size = Config.INITIAL_CHUNK_SIZE

    paragraphs = split_into_paragraphs(text)

    for paragraph in paragraphs:
        # Skip invalid paragraphs
        if not is_valid_chunk(paragraph):
            continue

        if len(paragraph) <= max_chunk_size:
            yield paragraph
            continue

        # Paragraph too long, split by sentences
        sentences = split_into_sentences(paragraph)
        current_chunk = ""

        for sentence in sentences:
            if len(sentence) > max_chunk_size:
                # Sentence too long, yield current chunk and split sentence
                if current_chunk and is_valid_chunk(current_chunk):
                    yield current_chunk
                    current_chunk = ""

                # Split long sentence by max_chunk_size
                for i in range(0, len(sentence), max_chunk_size):
                    part = sentence[i:i + max_chunk_size]
                    if is_valid_chunk(part):
                        yield part
            elif len(current_chunk) + len(sentence) + 1 <= max_chunk_size:
                # Add sentence to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                # Current chunk full, yield and start new
                if current_chunk and is_valid_chunk(current_chunk):
                    yield current_chunk
                current_chunk = sentence

        if current_chunk and is_valid_chunk(current_chunk):
            yield current_chunk


def count_chunks(text: str, chunk_size: int = None) -> int:
    """Count how many chunks the text will be split into."""
    return len(list(chunk_text(text, chunk_size)))
