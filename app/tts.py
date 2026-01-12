import os
import re
import tempfile
import time
from typing import Optional, Callable
import openai
from pydub import AudioSegment
from app.config import Config
from app.chunker import chunk_text, split_into_sentences
from app.preprocessor import preprocess_for_tts

MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
MIN_SPEAKABLE_CHARS = 3  # Minimum alphanumeric characters for valid TTS input
MIN_SPEAKABLE_LETTERS = 2  # Minimum letters for readable words


class TTSError(Exception):
    """TTS processing error."""
    pass


class ValidationError(TTSError):
    """Raised when chunk validation fails before processing."""
    pass


def is_chunk_valid(chunk: str) -> bool:
    """Check if a chunk is valid for TTS processing."""
    if not chunk or not chunk.strip():
        return False
    # Must have minimum alphanumeric content
    alphanumeric = re.sub(r'[^a-zA-Z0-9]', '', chunk)
    if len(alphanumeric) < MIN_SPEAKABLE_CHARS:
        return False
    # Must have actual letters (not just numbers)
    letters = re.sub(r'[^a-zA-Z]', '', chunk)
    if len(letters) < MIN_SPEAKABLE_LETTERS:
        return False
    return True


def repair_chunks(chunks: list[str], max_chunk_size: int) -> list[str]:
    """Repair invalid chunks by merging or splitting.

    Strategy:
    1. Drop chunks with no speakable content
    2. Merge short chunks with adjacent chunks
    3. Split chunks that are too long
    4. Final filter for any remaining invalid chunks
    """
    if not chunks:
        return []

    repaired = []
    pending = None  # Chunk waiting to be merged

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        # Check if chunk has any speakable content
        if not is_chunk_valid(chunk):
            # Try to merge with pending if exists
            if pending:
                pending = pending + " " + chunk
            # Otherwise just drop it
            continue

        # Valid chunk - check if we need to merge with pending
        if pending:
            merged = pending + " " + chunk
            if len(merged) <= max_chunk_size:
                # Merge successful
                chunk = merged
                pending = None
            else:
                # Can't merge, flush pending first
                if is_chunk_valid(pending):
                    repaired.append(pending)
                pending = None

        # Check if chunk is too long
        if len(chunk) > max_chunk_size:
            # Split by sentences
            sentences = split_into_sentences(chunk)
            current = ""
            for sent in sentences:
                if not sent.strip():
                    continue
                if len(current) + len(sent) + 1 <= max_chunk_size:
                    current = (current + " " + sent).strip() if current else sent
                else:
                    if current and is_chunk_valid(current):
                        repaired.append(current)
                    current = sent
            if current:
                if is_chunk_valid(current):
                    repaired.append(current)
                else:
                    pending = current
        else:
            repaired.append(chunk)

    # Flush any remaining pending
    if pending and is_chunk_valid(pending):
        repaired.append(pending)

    return repaired


def validate_and_repair_chunks(chunks: list[str], max_chunk_size: int = None) -> list[str]:
    """Validate all chunks and repair any invalid ones.

    Two-pass approach:
    1. First pass: repair invalid chunks (merge/split)
    2. Second pass: final validation, drop any remaining invalid
    """
    if max_chunk_size is None:
        max_chunk_size = Config.INITIAL_CHUNK_SIZE

    # First pass: repair
    repaired = repair_chunks(chunks, max_chunk_size)

    # Second pass: final validation
    final_chunks = []
    for chunk in repaired:
        if is_chunk_valid(chunk):
            final_chunks.append(chunk)

    if not final_chunks:
        raise ValidationError("No valid chunks after repair. Input may not contain speakable text.")

    return final_chunks


def get_tts_client() -> openai.OpenAI:
    """Create OpenAI client configured for LiteLLM."""
    if not Config.LITELLM_API_KEY:
        raise TTSError("LITELLM_API_KEY not configured")

    return openai.OpenAI(
        api_key=Config.LITELLM_API_KEY,
        base_url=Config.LITELLM_BASE_URL
    )


def convert_chunk(client: openai.OpenAI, text: str, voice: str,
                  speed: float, output_path: str) -> bool:
    """Convert a single text chunk to audio with retry logic.

    Returns:
        True if successful, False otherwise
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = client.audio.speech.create(
                model=Config.TTS_MODEL,
                input=text,
                voice=voice,
                speed=speed
            )
            response.stream_to_file(output_path)

            # Validate the output file
            if not os.path.exists(output_path):
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                return False

            file_size = os.path.getsize(output_path)
            if file_size < 100:  # Too small to be valid audio
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                return False

            # Check for valid MP3/ID3 header
            with open(output_path, 'rb') as f:
                header = f.read(3)
                # Valid MP3 starts with ID3 tag or MP3 frame sync
                if header != b'ID3' and header[:2] != b'\xff\xfb':
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                    return False

            return True
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            return False

    return False


def convert_chunk_adaptive(client: openai.OpenAI, text: str, voice: str,
                           speed: float, output_path: str) -> tuple[bool, int]:
    """Convert text chunk with adaptive chunk size reduction on failure.

    Returns:
        Tuple of (success, chunk_size_used)
    """
    chunk_sizes = [
        Config.INITIAL_CHUNK_SIZE,
        2000,
        1000,
        Config.MIN_CHUNK_SIZE
    ]

    for size in chunk_sizes:
        if len(text) <= size:
            if convert_chunk(client, text, voice, speed, output_path):
                return True, size

        # Text is larger than this size, try chunking at this size
        chunks = list(chunk_text(text, size))
        if len(chunks) == 1:
            if convert_chunk(client, text, voice, speed, output_path):
                return True, size
            continue

        # Multiple chunks at this size - this shouldn't happen in single chunk conversion
        # Fall through to try smaller size
        continue

    return False, 0


def convert_text_to_speech(
    text: str,
    voice: str,
    speed: float,
    output_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> float:
    """Convert text to speech with adaptive chunking.

    Args:
        text: Full text to convert
        voice: Voice to use
        speed: Speed multiplier
        output_path: Path to save final audio
        progress_callback: Optional callback(current_chunk, total_chunks)

    Returns:
        Duration of audio in seconds

    Raises:
        TTSError: If conversion fails
        ValidationError: If chunks fail validation before processing
    """
    # Step 1: Preprocess text
    text = preprocess_for_tts(text)

    # Step 2: Generate initial chunks
    chunks = list(chunk_text(text))

    if not chunks:
        raise TTSError("No text to convert after preprocessing")

    # Step 3: Validate and REPAIR all chunks BEFORE any GPU processing
    # This ensures no invalid chunks reach the TTS API
    chunks = validate_and_repair_chunks(chunks, Config.INITIAL_CHUNK_SIZE)
    total_chunks = len(chunks)

    if total_chunks == 0:
        raise TTSError("No valid chunks to convert")

    # Step 4: Now safe to start TTS processing - all chunks are validated
    client = get_tts_client()

    temp_files = []
    successful_chunk_size = Config.INITIAL_CHUNK_SIZE

    try:
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i + 1, total_chunks)

            # Create temp file for this chunk
            temp_fd, temp_path = tempfile.mkstemp(suffix=".mp3")
            os.close(temp_fd)
            temp_files.append(temp_path)

            # Try conversion with adaptive sizing
            success = False
            chunk_sizes = [successful_chunk_size, 2000, 1000, Config.MIN_CHUNK_SIZE]

            for size in chunk_sizes:
                if len(chunk) <= size:
                    if convert_chunk(client, chunk, voice, speed, temp_path):
                        success = True
                        successful_chunk_size = size
                        break
                else:
                    # Need to sub-chunk
                    sub_chunks = list(chunk_text(chunk, size))
                    sub_success = True
                    sub_segments = []

                    for sub_chunk in sub_chunks:
                        sub_fd, sub_path = tempfile.mkstemp(suffix=".mp3")
                        os.close(sub_fd)

                        if convert_chunk(client, sub_chunk, voice, speed, sub_path):
                            sub_segments.append(AudioSegment.from_mp3(sub_path))
                            os.remove(sub_path)
                        else:
                            os.remove(sub_path)
                            sub_success = False
                            break

                    if sub_success and sub_segments:
                        combined = sub_segments[0]
                        for seg in sub_segments[1:]:
                            combined += seg
                        combined.export(temp_path, format="mp3")
                        success = True
                        successful_chunk_size = size
                        break

            if not success:
                raise TTSError(f"Failed to convert chunk {i + 1}/{total_chunks}")

        # Concatenate all chunks
        if len(temp_files) == 1:
            os.rename(temp_files[0], output_path)
            temp_files = []
        else:
            combined = AudioSegment.from_mp3(temp_files[0])
            for temp_file in temp_files[1:]:
                combined += AudioSegment.from_mp3(temp_file)
            combined.export(output_path, format="mp3")

        # Get duration
        final_audio = AudioSegment.from_mp3(output_path)
        return len(final_audio) / 1000.0  # Convert ms to seconds

    finally:
        # Clean up temp files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
