import os
import re
import tempfile
import time
from typing import Optional, Callable
import openai
from pydub import AudioSegment
from app.config import Config
from app.chunker import chunk_text
from app.preprocessor import preprocess_for_tts

MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds
MIN_SPEAKABLE_CHARS = 3  # Minimum alphanumeric characters for valid TTS input


class TTSError(Exception):
    """TTS processing error."""
    pass


class ValidationError(TTSError):
    """Raised when chunk validation fails before processing."""
    pass


def validate_chunk_content(chunk: str, chunk_index: int, total: int) -> tuple[bool, str]:
    """Validate a chunk has enough speakable content for TTS.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not chunk or not chunk.strip():
        return False, f"Chunk {chunk_index}/{total} is empty"

    # Check for minimum alphanumeric content
    alphanumeric = re.sub(r'[^a-zA-Z0-9]', '', chunk)
    if len(alphanumeric) < MIN_SPEAKABLE_CHARS:
        return False, f"Chunk {chunk_index}/{total} has insufficient speakable content: '{chunk[:50]}...'"

    # Check chunk isn't just numbers/punctuation
    letters = re.sub(r'[^a-zA-Z]', '', chunk)
    if len(letters) < 2:
        return False, f"Chunk {chunk_index}/{total} has no readable words: '{chunk[:50]}...'"

    return True, ""


def validate_all_chunks(chunks: list[str]) -> list[str]:
    """Validate all chunks before processing. Raises ValidationError if any fail.

    Returns:
        List of valid chunks (filtered)
    """
    valid_chunks = []
    errors = []

    for i, chunk in enumerate(chunks, 1):
        is_valid, error = validate_chunk_content(chunk, i, len(chunks))
        if is_valid:
            valid_chunks.append(chunk)
        else:
            errors.append(error)

    if not valid_chunks:
        raise ValidationError(f"No valid chunks to convert. Issues found:\n" + "\n".join(errors[:5]))

    return valid_chunks


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

    # Step 2: Generate chunks
    chunks = list(chunk_text(text))

    if not chunks:
        raise TTSError("No text to convert after preprocessing")

    # Step 3: Validate ALL chunks BEFORE any GPU processing
    chunks = validate_all_chunks(chunks)
    total_chunks = len(chunks)

    if total_chunks == 0:
        raise TTSError("No valid chunks to convert")

    # Step 4: Now safe to start TTS processing
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
