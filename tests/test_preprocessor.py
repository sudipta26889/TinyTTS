import pytest
from app.preprocessor import strip_markdown, convert_lists, convert_tables, normalize_text, clean_whitespace, preprocess_for_tts


class TestStripMarkdown:
    def test_removes_headers(self):
        assert strip_markdown("# Heading") == "Heading"
        assert strip_markdown("## Sub Heading") == "Sub Heading"
        assert strip_markdown("### Deep Heading") == "Deep Heading"

    def test_removes_bold(self):
        assert strip_markdown("**bold text**") == "bold text"
        assert strip_markdown("word **bold** word") == "word bold word"

    def test_removes_italic(self):
        assert strip_markdown("*italic*") == "italic"
        assert strip_markdown("_italic_") == "italic"

    def test_removes_strikethrough(self):
        assert strip_markdown("~~deleted~~") == "deleted"

    def test_removes_inline_code(self):
        assert strip_markdown("`code`") == "code"

    def test_removes_code_blocks(self):
        text = "before\n```python\ncode here\n```\nafter"
        assert strip_markdown(text) == "before\n\nafter"

    def test_removes_horizontal_rules(self):
        assert strip_markdown("above\n---\nbelow") == "above\n\nbelow"
        assert strip_markdown("above\n***\nbelow") == "above\n\nbelow"
        assert strip_markdown("above\n___\nbelow") == "above\n\nbelow"

    def test_keeps_link_text(self):
        assert strip_markdown("[click here](http://url)") == "click here"

    def test_removes_images(self):
        assert strip_markdown("![alt](image.png)") == ""

    def test_removes_blockquotes(self):
        assert strip_markdown("> quoted text") == "quoted text"

    def test_removes_html_tags(self):
        assert strip_markdown("<em>text</em>") == "text"
        assert strip_markdown("<div>content</div>") == "content"

    def test_handles_multiline_bold(self):
        text = "**bold\ntext**"
        assert strip_markdown(text) == "bold\ntext"

    def test_handles_multiline_italic(self):
        text = "*italic\ntext*"
        assert strip_markdown(text) == "italic\ntext"


class TestConvertLists:
    def test_converts_bullet_list(self):
        text = "- Apple\n- Banana\n- Orange"
        assert convert_lists(text) == "Apple.\nBanana.\nOrange."

    def test_converts_asterisk_bullets(self):
        text = "* First\n* Second"
        assert convert_lists(text) == "First.\nSecond."

    def test_converts_plus_bullets(self):
        text = "+ One\n+ Two"
        assert convert_lists(text) == "One.\nTwo."

    def test_converts_numbered_list(self):
        text = "1. First\n2. Second\n3. Third"
        assert convert_lists(text) == "First.\nSecond.\nThird."

    def test_converts_numbered_with_parens(self):
        text = "1) First\n2) Second"
        assert convert_lists(text) == "First.\nSecond."

    def test_preserves_existing_punctuation(self):
        text = "- Already has period.\n- No period"
        assert convert_lists(text) == "Already has period.\nNo period."

    def test_skips_empty_items(self):
        text = "- First\n-\n- Third"
        assert convert_lists(text) == "First.\nThird."

    def test_handles_indented_bullets(self):
        text = "  - Indented\n  - Also indented"
        assert convert_lists(text) == "Indented.\nAlso indented."

    def test_preserves_non_list_text(self):
        text = "Normal paragraph.\n\n- List item\n\nAnother paragraph."
        result = convert_lists(text)
        assert "List item." in result
        assert "Normal paragraph." in result


class TestConvertTables:
    def test_simple_table(self):
        """Basic 2-column table converts to prose."""
        text = "| Item   | Price |\n|--------|-------|\n| Apple  | $2    |"
        result = convert_tables(text)
        assert result == "Item is Apple, Price is $2."

    def test_multi_row_table(self):
        """Table with multiple data rows."""
        text = "| Name  | Age |\n|-------|-----|\n| Alice | 30  |\n| Bob   | 25  |"
        result = convert_tables(text)
        assert result == "Name is Alice, Age is 30. Name is Bob, Age is 25."

    def test_no_table(self):
        """Text without tables passes through unchanged."""
        text = "Just regular text.\nNo tables here."
        result = convert_tables(text)
        assert result == text

    def test_table_with_surrounding_text(self):
        """Table embedded in regular text."""
        text = "Here is a table:\n\n| Item | Price |\n|------|-------|\n| Milk | $3    |\n\nThat was the table."
        result = convert_tables(text)
        assert "Here is a table:" in result
        assert "Item is Milk, Price is $3." in result
        assert "That was the table." in result

    def test_empty_cells(self):
        """Empty cell values should be skipped - don't output 'Header is ,'."""
        text = "| Item | Price | Note |\n|------|-------|------|\n| Apple | $2 |  |"
        result = convert_tables(text)
        # Should skip empty Note, not produce "Note is ," or "Note is "
        assert result == "Item is Apple, Price is $2."

    def test_single_column_table(self):
        """Single-column table converts to prose."""
        text = "| Item |\n|------|\n| Apple |\n| Banana |"
        result = convert_tables(text)
        assert result == "Item is Apple. Item is Banana."

    def test_fewer_data_cells(self):
        """Data row with fewer cells than headers - only pairs existing cells."""
        text = "| Item | Price | Stock |\n|------|-------|-------|\n| Apple | $2 |"
        result = convert_tables(text)
        # Should handle gracefully - zip stops at shortest list
        assert result == "Item is Apple, Price is $2."


class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_currency(self):
        """Currency amounts should be converted to spoken form."""
        assert normalize_text("$100") == "100 dollars"
        assert normalize_text("$5.99") == "5 dollars and 99 cents"
        assert normalize_text("The price is $100") == "The price is 100 dollars"
        assert normalize_text("$1") == "1 dollar"
        assert normalize_text("$0.01") == "0 dollars and 1 cent"

    def test_percentages(self):
        """Percentages should be converted to spoken form."""
        assert normalize_text("50%") == "50 percent"
        assert normalize_text("100%") == "100 percent"
        assert normalize_text("The score was 85%") == "The score was 85 percent"

    def test_ordinals(self):
        """Ordinal numbers should be converted to words."""
        assert normalize_text("1st") == "first"
        assert normalize_text("2nd") == "second"
        assert normalize_text("3rd") == "third"
        assert normalize_text("4th") == "fourth"
        assert normalize_text("21st place") == "twenty-first place"

    def test_abbreviations(self):
        """Common abbreviations should be expanded."""
        assert normalize_text("Dr.") == "Doctor"
        assert normalize_text("etc.") == "et cetera"
        assert normalize_text("Mr. Smith") == "Mister Smith"
        assert normalize_text("Mrs. Jones") == "Missus Jones"
        assert normalize_text("e.g.") == "for example"
        assert normalize_text("i.e.") == "that is"

    def test_units(self):
        """Units should be converted to spoken form."""
        assert normalize_text("10km") == "10 kilometers"
        assert normalize_text("5kg") == "5 kilograms"
        assert normalize_text("100m") == "100 meters"
        assert normalize_text("15cm") == "15 centimeters"
        assert normalize_text("20mm") == "20 millimeters"
        assert normalize_text("3lb") == "3 pounds"
        assert normalize_text("8oz") == "8 ounces"
        assert normalize_text("5mi") == "5 miles"
        assert normalize_text("6ft") == "6 feet"
        assert normalize_text("12in") == "12 inches"

    def test_dates(self):
        """Dates in MM/DD/YYYY format should be converted to spoken form."""
        assert normalize_text("01/15/2024") == "January 15th, 2024"
        assert normalize_text("12/25/2023") == "December 25th, 2023"
        assert normalize_text("The meeting is on 01/15/2024") == "The meeting is on January 15th, 2024"

    def test_no_change(self):
        """Regular text should pass through unchanged."""
        assert normalize_text("Hello world") == "Hello world"
        assert normalize_text("This is a test.") == "This is a test."
        assert normalize_text("") == ""

    def test_invalid_date_month(self):
        """Invalid month values should leave date unchanged."""
        # Month 13 is invalid (only 1-12 are valid) - should not crash
        assert normalize_text("13/01/2024") == "13/01/2024"
        # Month 0 is invalid - should not return "December" via negative indexing
        assert normalize_text("00/15/2024") == "00/15/2024"


class TestCleanWhitespace:
    """Tests for clean_whitespace function."""

    def test_multiple_newlines(self):
        """3+ newlines should collapse to double newlines (paragraph boundary)."""
        assert clean_whitespace("a\n\n\nb") == "a\n\nb"
        assert clean_whitespace("a\n\n\n\nb") == "a\n\nb"

    def test_preserves_paragraph_boundary(self):
        """Double newlines (paragraph boundaries) should be preserved."""
        assert clean_whitespace("a\n\nb") == "a\n\nb"

    def test_multiple_spaces(self):
        """Multiple spaces should collapse to single space."""
        assert clean_whitespace("a    b") == "a b"

    def test_leading_trailing(self):
        """Leading and trailing whitespace should be stripped."""
        assert clean_whitespace("  text  ") == "text"

    def test_mixed(self):
        """Mixed whitespace issues should all be cleaned."""
        assert clean_whitespace("  a  \n\n  b  ") == "a\n\nb"


class TestPreprocessForTts:
    """Tests for preprocess_for_tts main pipeline."""

    def test_full_pipeline(self):
        """Full markdown document should be converted to clean TTS text."""
        input_text = """# Welcome

Here is a **table**:

| Item | Price |
|------|-------|
| Apple | $5 |

Shopping list:
- Milk
- Bread

Visit [our site](http://example.com) for 50% off!
"""
        result = preprocess_for_tts(input_text)
        # Should have no markdown formatting
        assert "#" not in result
        assert "**" not in result
        assert "|" not in result
        assert "[" not in result
        # Should have converted values
        assert "5 dollars" in result
        assert "50 percent" in result
        # Should have clean whitespace (no 3+ newlines, paragraphs preserved)
        assert "\n\n\n" not in result

    def test_pipeline_order(self):
        """Verify correct processing order: tables -> markdown -> lists -> normalize -> whitespace."""
        # This tests that tables are processed before markdown stripping
        # If order is wrong, the | characters in table would be left behind
        input_text = "| Item | Price |\n|------|-------|\n| **Bold** | $10 |"
        result = preprocess_for_tts(input_text)
        # Table should be converted to prose, then bold stripped, then currency normalized
        assert "Item is Bold" in result
        assert "10 dollars" in result
        assert "|" not in result
        assert "**" not in result
