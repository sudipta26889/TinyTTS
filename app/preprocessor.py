"""Text preprocessing for TTS conversion."""
import re
import inflect

# Initialize inflect engine
p = inflect.engine()


def strip_markdown(text: str) -> str:
    """Remove markdown formatting, keeping plain text content."""
    # Code blocks first (before other patterns can match inside them)
    text = re.sub(r'```[\s\S]*?```', '', text)

    # Horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Images (before links, as images use similar syntax)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # Links - keep text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # Headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text, flags=re.DOTALL)

    # Italic (asterisk)
    text = re.sub(r'\*(.+?)\*', r'\1', text, flags=re.DOTALL)

    # Italic (underscore)
    text = re.sub(r'_(.+?)_', r'\1', text, flags=re.DOTALL)

    # Strikethrough
    text = re.sub(r'~~(.+?)~~', r'\1', text, flags=re.DOTALL)

    # Inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # Blockquotes
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    return text


def convert_lists(text: str) -> str:
    """Convert bullet and numbered lists to sentences with pauses.

    Each list item becomes a separate sentence so TTS adds natural pauses.
    Handles ASCII bullets (-, *, +) and Unicode bullets (•, ◦, ▪, ▸, ►, ●, ○).
    """
    lines = text.split('\n')
    result_lines = []
    current_list_items = []

    # ASCII bullets: -, *, +
    # Unicode bullets: •◦▪▸►●○‣⁃
    bullet_pattern = re.compile(r'^[\s]*[-*+•◦▪▸►●○‣⁃]\s*(.*)$')
    number_pattern = re.compile(r'^[\s]*\d+[.)]\s+(.+)$')

    def flush_list():
        if current_list_items:
            for item in current_list_items:
                item = item.strip()
                if item:
                    if item[-1] not in '.!?':
                        item += '.'
                    result_lines.append(item)
            current_list_items.clear()

    for line in lines:
        bullet_match = bullet_pattern.match(line)
        number_match = number_pattern.match(line)

        if bullet_match:
            current_list_items.append(bullet_match.group(1))
        elif number_match:
            current_list_items.append(number_match.group(1))
        else:
            flush_list()
            result_lines.append(line)

    flush_list()
    return '\n'.join(result_lines)


def convert_tables(text: str) -> str:
    """Convert markdown tables to prose sentences.

    Example:
        | Item   | Price |
        |--------|-------|
        | Apple  | $2    |

    Becomes: "Item is Apple, Price is $2."
    """
    lines = text.split('\n')
    result_lines = []

    headers = []
    in_table = False
    table_prose = []

    separator_pattern = re.compile(r'^\|[\s\-:|]+\|$')

    def flush_table():
        nonlocal in_table, headers, table_prose
        if table_prose:
            result_lines.append(' '.join(table_prose))
        in_table = False
        headers = []
        table_prose = []

    for line in lines:
        stripped = line.strip()

        # Check if this is a table row (contains |)
        if '|' in stripped and stripped.startswith('|') and stripped.endswith('|'):
            # Parse cells from the row
            cells = [cell.strip() for cell in stripped.split('|')[1:-1]]

            if not in_table:
                # First row with | is the header row
                headers = cells
                in_table = True
            elif separator_pattern.match(stripped):
                # Skip separator row (|---|---|)
                continue
            else:
                # Data row - convert to prose
                pairs = []
                for header, value in zip(headers, cells):
                    if value:  # Skip empty values
                        pairs.append(f"{header} is {value}")
                if pairs:  # Only add row if there are non-empty pairs
                    table_prose.append(', '.join(pairs) + '.')
        else:
            # Non-table line
            flush_table()
            result_lines.append(line)

    # Flush any remaining table
    flush_table()

    return '\n'.join(result_lines)


# Common abbreviations dictionary
ABBREVIATIONS = {
    'Dr.': 'Doctor',
    'Mr.': 'Mister',
    'Mrs.': 'Missus',
    'Ms.': 'Miss',
    'Jr.': 'Junior',
    'Sr.': 'Senior',
    'Prof.': 'Professor',
    'etc.': 'et cetera',
    'e.g.': 'for example',
    'i.e.': 'that is',
    'vs.': 'versus',
    'St.': 'Saint',
    'Ave.': 'Avenue',
    'Blvd.': 'Boulevard',
}

# Units mapping
UNITS = {
    'km': 'kilometers',
    'kg': 'kilograms',
    'm': 'meters',
    'cm': 'centimeters',
    'mm': 'millimeters',
    'lb': 'pounds',
    'oz': 'ounces',
    'mi': 'miles',
    'ft': 'feet',
    'in': 'inches',
}


def normalize_text(text: str) -> str:
    """Normalize text for TTS by converting numbers, symbols, and abbreviations to spoken form.

    Handles:
    - Currency: $100 -> "100 dollars", $5.99 -> "5 dollars and 99 cents"
    - Percentages: 50% -> "50 percent"
    - Ordinals: 1st -> "first", 2nd -> "second"
    - Abbreviations: Dr. -> "Doctor", etc. -> "et cetera"
    - Units: 10km -> "10 kilometers", 5kg -> "5 kilograms"
    """
    if not text:
        return text

    # Currency: $X or $X.XX
    def replace_currency(match):
        dollars = match.group(1)
        cents = match.group(2)
        if cents:
            cents_int = int(cents)
            dollar_word = "dollar" if int(dollars) == 1 else "dollars"
            cent_word = "cent" if cents_int == 1 else "cents"
            return f"{dollars} {dollar_word} and {cents_int} {cent_word}"
        else:
            dollar_word = "dollar" if int(dollars) == 1 else "dollars"
            return f"{dollars} {dollar_word}"

    text = re.sub(r'\$(\d+)(?:\.(\d{2}))?', replace_currency, text)

    # Percentages: X%
    text = re.sub(r'(\d+)%', r'\1 percent', text)

    # Ordinals: 1st, 2nd, 3rd, 4th, etc. -> first, second, third, fourth
    def replace_ordinal(match):
        num = int(match.group(1))
        return p.number_to_words(p.ordinal(num))

    text = re.sub(r'(\d+)(st|nd|rd|th)\b', replace_ordinal, text)

    # Units: 10km, 5kg, etc.
    def replace_unit(match):
        number = match.group(1)
        unit = match.group(2)
        unit_word = UNITS.get(unit, unit)
        return f"{number} {unit_word}"

    # Build pattern from units keys, sorted by length (longest first to match 'cm' before 'm')
    units_pattern = '|'.join(sorted(UNITS.keys(), key=len, reverse=True))
    text = re.sub(rf'(\d+)({units_pattern})\b', replace_unit, text)

    # Abbreviations - use word boundaries to avoid partial matches
    for abbr, expansion in ABBREVIATIONS.items():
        # Escape the period in abbreviation for regex
        pattern = re.escape(abbr)
        text = re.sub(pattern, expansion, text)

    # Dates: MM/DD/YYYY -> "Month DDth, YYYY"
    month_names = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]

    def replace_date(match):
        month = int(match.group(1))
        day = int(match.group(2))
        year = match.group(3)
        # Validate month is in valid range (1-12)
        if month < 1 or month > 12:
            return match.group(0)
        month_name = month_names[month - 1]
        day_ordinal = p.ordinal(day)
        return f"{month_name} {day_ordinal}, {year}"

    text = re.sub(r'(\d{1,2})/(\d{1,2})/(\d{4})', replace_date, text)

    return text


def remove_unspeakable(text: str) -> str:
    """Remove symbols and characters that TTS cannot pronounce."""
    # Remove geometric shapes, symbols, and other non-speakable Unicode
    # ○●◯◉■□▪▫▲△▼▽◆◇★☆♦♣♠♥✓✗✔✘→←↑↓⇒⇐⇔│├└┌┐┘┬┴─═║╔╗╚╝╠╣╬
    text = re.sub(r'[○●◯◉■□▪▫▲△▼▽◆◇★☆♦♣♠♥✓✗✔✘→←↑↓⇒⇐⇔│├└┌┐┘┬┴─═║╔╗╚╝╠╣╬•·©®™°±×÷≠≤≥∞∑∏√∫∂∆∇∈∉⊂⊃∪∩]', '', text)
    # Remove other common unspeakable characters
    text = re.sub(r'[🔹🔸🔷🔶📌📍🔗💡⚠️✨🎯📊📈📉]', '', text)
    return text


def clean_whitespace(text: str) -> str:
    """Collapse multiple whitespace while preserving paragraph boundaries.

    Single newlines within paragraphs are converted to spaces so TTS reads
    text naturally without pauses at line breaks.
    """
    # Normalize ALL line-break characters to \n (including PDF artifacts)
    # \r\n = Windows, \r = old Mac, \x0c = form feed, \x0b = vertical tab
    # \u2028 = Unicode line separator, \u2029 = Unicode paragraph separator
    text = text.replace('\r\n', '\n')
    text = text.replace('\r', '\n')
    text = text.replace('\x0c', '\n')
    text = text.replace('\x0b', '\n')
    text = text.replace('\u2028', '\n')
    text = text.replace('\u2029', '\n\n')

    # Normalize paragraph breaks to exactly \n\n
    text = re.sub(r'\n\s*\n', '\n\n', text)

    # Mark paragraph breaks with placeholder
    PARA_MARKER = '\x00PARA\x00'
    text = text.replace('\n\n', PARA_MARKER)

    # Convert remaining single newlines to spaces (join lines within paragraph)
    text = text.replace('\n', ' ')

    # Restore paragraph breaks
    text = text.replace(PARA_MARKER, '\n\n')

    # Collapse multiple spaces to single
    text = re.sub(r' {2,}', ' ', text)

    # Clean up spaces around paragraph breaks
    text = re.sub(r' *\n\n *', '\n\n', text)

    return text.strip()


def preprocess_for_tts(text: str) -> str:
    """Main preprocessing pipeline for TTS conversion.

    Pipeline order:
    1. convert_tables() - Convert markdown tables to prose
    2. strip_markdown() - Remove markdown formatting
    3. convert_lists() - Convert bullet/numbered lists
    4. normalize_text() - Expand abbreviations, numbers, symbols
    5. remove_unspeakable() - Remove symbols TTS cannot pronounce
    6. clean_whitespace() - Clean up whitespace
    """
    text = convert_tables(text)
    text = strip_markdown(text)
    text = convert_lists(text)
    text = normalize_text(text)
    text = remove_unspeakable(text)
    text = clean_whitespace(text)
    return text
