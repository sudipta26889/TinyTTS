import os
import markdown2
from PyPDF2 import PdfReader


def extract_text_from_file(filepath: str) -> str:
    """Extract text content from a file based on its extension.

    Args:
        filepath: Path to the file

    Returns:
        Extracted text content

    Raises:
        ValueError: If file type is not supported
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".txt":
        return extract_from_txt(filepath)
    elif ext == ".md":
        return extract_from_markdown(filepath)
    elif ext == ".pdf":
        return extract_from_pdf(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def extract_from_txt(filepath: str) -> str:
    """Extract text from a .txt file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return normalize_text(f.read())


def extract_from_markdown(filepath: str) -> str:
    """Extract text from a .md file, converting to plain text."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Convert markdown to HTML, then strip tags
    html = markdown2.markdown(content)
    # Simple tag stripping
    import re
    text = re.sub(r'<[^>]+>', '', html)
    return normalize_text(text)


def extract_from_pdf(filepath: str) -> str:
    """Extract text from a PDF file."""
    reader = PdfReader(filepath)
    text_parts = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)

    return normalize_text("\n\n".join(text_parts))


def normalize_text(text: str) -> str:
    """Normalize whitespace and clean up text.

    PDF extractors often put newlines after every line (every few words).
    This function joins lines within paragraphs while preserving actual
    paragraph breaks (double newlines).

    Handles PyPDF2's word-per-line format where words are separated by
    '\\n \\n' (newline-space-newline) and paragraphs by '\\n \\n \\n' or more.
    """
    import re

    # Step 0: Normalize ALL line-break characters to \n (PDF artifacts)
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')
    text = text.replace('\x0c', '\n')  # form feed
    text = text.replace('\x0b', '\n')  # vertical tab
    text = text.replace('\u2028', '\n')  # Unicode line separator
    text = text.replace('\u2029', '\n\n')  # Unicode paragraph separator

    # Step 1: Detect PyPDF2 word-per-line format
    # Pattern: words separated by '\n \n' (newline-space-newline)
    word_per_line_pattern = '\n \n'  # NOT raw string - need actual newlines
    if word_per_line_pattern in text:
        # Handle PyPDF2 word-per-line format
        # Paragraph breaks: '\n \n \n' or more (2+ spaces between newlines)
        # Word separators: '\n \n' (single space between newlines)
        PARA_MARKER = '\x00PARA\x00'

        # First, mark paragraph breaks (3+ newlines with spaces between)
        # Pattern: \n followed by ( \n) repeated 2+ times = paragraph break
        text = re.sub(r'\n( \n){2,}', PARA_MARKER, text)

        # Now convert remaining \n \n (word separators) to single space
        text = text.replace('\n \n', ' ')

        # Convert any remaining single newlines to spaces
        text = text.replace('\n', ' ')

        # Restore paragraph breaks
        text = text.replace(PARA_MARKER, '\n\n')

        # Step 2: Re-introduce paragraph breaks based on content structure
        # PyPDF2 loses structure - we need to restore it based on patterns

        # Add breaks before numbered sections (1. Purpose, 2. Product, etc.)
        # Match: space + digit(s) + period + space + Capital letter word
        # This catches "1. Purpose", "2. Product", "10. Section", "6.1 Subsection"
        text = re.sub(r' (\d+\.(?:\d+)?) ([A-Z][a-z]+)', r'\n\n\1 \2', text)

        # Add breaks before bullet points (●, ○, -, *, •)
        # Each bullet should start a new line for TTS pauses
        text = re.sub(r' ([●○•◦▪▸►]) ', r'\n\n\1 ', text)

    else:
        # Standard format: use traditional paragraph detection
        # Convert 2+ newlines (possibly with whitespace) to paragraph breaks
        text = re.sub(r'\n[ \t]*\n', '\n\n', text)
        PARA_MARKER = '\x00PARA\x00'
        text = text.replace('\n\n', PARA_MARKER)

        # Convert remaining single newlines to spaces
        text = text.replace('\n', ' ')

        # Restore paragraph breaks
        text = text.replace(PARA_MARKER, '\n\n')

    # Clean up multiple spaces
    text = re.sub(r'[ \t]+', ' ', text)

    # Clean up spaces around paragraph breaks
    text = re.sub(r' *\n\n *', '\n\n', text)

    return text.strip()
