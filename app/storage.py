import os
from app.config import Config
from app.models import Conversion


def get_storage_usage_bytes() -> int:
    """Calculate total storage used by audio and source files."""
    total = 0
    data_dir = Config.DATA_DIR

    for subdir in ["audio", "sources"]:
        dir_path = os.path.join(data_dir, subdir)
        if os.path.exists(dir_path):
            for filename in os.listdir(dir_path):
                filepath = os.path.join(dir_path, filename)
                if os.path.isfile(filepath):
                    total += os.path.getsize(filepath)

    return total


def get_storage_usage_gb() -> float:
    """Get storage usage in GB."""
    return get_storage_usage_bytes() / (1024 ** 3)


def cleanup_if_needed(required_bytes: int = 0) -> int:
    """Delete oldest entries until storage is under limit.

    Args:
        required_bytes: Additional bytes needed for new file

    Returns:
        Number of entries deleted
    """
    max_bytes = Config.MAX_STORAGE_GB * (1024 ** 3)
    deleted_count = 0

    while get_storage_usage_bytes() + required_bytes > max_bytes:
        oldest = Conversion.get_oldest()
        if not oldest:
            break

        # Delete files
        if os.path.exists(oldest.audio_path):
            os.remove(oldest.audio_path)
        if os.path.exists(oldest.source_path):
            os.remove(oldest.source_path)

        # Delete database record
        oldest.delete()
        deleted_count += 1

    return deleted_count


def delete_conversion_files(conversion: Conversion):
    """Delete files associated with a conversion."""
    if os.path.exists(conversion.audio_path):
        os.remove(conversion.audio_path)
    if os.path.exists(conversion.source_path):
        os.remove(conversion.source_path)
