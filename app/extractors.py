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
    """
    import re

    # Step 0: Normalize ALL line-break characters to \n (PDF artifacts)
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')
    text = text.replace('\x0c', '\n')  # form feed
    text = text.replace('\x0b', '\n')  # vertical tab
    text = text.replace('\u2028', '\n')  # Unicode line separator
    text = text.replace('\u2029', '\n\n')  # Unicode paragraph separator

    # Step 1: Normalize paragraph breaks - mark them with a placeholder
    # Convert 2+ newlines to placeholder (these are real paragraph breaks)
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Normalize to exactly \n\n
    PARA_MARKER = '\x00PARA\x00'
    text = text.replace('\n\n', PARA_MARKER)

    # Step 2: Convert remaining single newlines to spaces (join lines within paragraph)
    text = re.sub(r'\n', ' ', text)

    # Step 3: Restore paragraph breaks
    text = text.replace(PARA_MARKER, '\n\n')

    # Step 4: Clean up multiple spaces
    text = re.sub(r'[ \t]+', ' ', text)

    # Step 5: Clean up spaces around paragraph breaks
    text = re.sub(r' *\n\n *', '\n\n', text)

    return text.strip()
