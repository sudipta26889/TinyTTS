# PDF Extraction with PyMuPDF4LLM Design

**Date:** 2025-01-13
**Status:** Implemented

## Problem

PyPDF2 extracts PDF text with poor structure preservation:
- Word-per-line format with `\n \n` between every word
- Lost document structure (headers, sections, bullets)
- Sub-headers like "Capabilities:" weren't getting pauses before bullet points
- Required complex regex heuristics to restore structure

## Solution

Switch to PyMuPDF4LLM which extracts PDFs directly to Markdown format.

### Architecture

```
PDF File
    |
    v
[PyMuPDF4LLM]  -->  Markdown output
    |               (# headers, **bold**, bullets preserved)
    v
[TTS Preprocessor]
    |
    |- strip_markdown() - converts headers to text + \n\n for pause
    |- convert_lists()  - converts bullets to sentences
    |- normalize_text() - expands abbreviations, numbers
    |- clean_whitespace()
    v
TTS-Ready Text (with natural pauses)
```

### Markdown-to-TTS Transformation Rules

| Markdown Element | TTS Transformation | Pause Effect |
|-----------------|-------------------|--------------|
| `# H1 Header` | Strip #, add `\n\n` after | ~1000ms |
| `## H2 Header` | Strip ##, add `\n\n` after | ~1000ms |
| Line ending with `:` | Add `\n\n` after (sub-header) | ~750ms |
| `* bullet item` | Convert to sentence with `.` | ~500ms |
| `**bold text**` | Strip `**`, keep text | none |

### Files Modified

1. **requirements.txt** - Replaced `PyPDF2` with `pymupdf4llm>=0.0.17`
2. **app/extractors.py** - `extract_from_pdf()` now uses `pymupdf4llm.to_markdown()`
3. **app/preprocessor.py** - `strip_markdown()` enhanced to:
   - Add `\n\n` after headers for TTS pause
   - Add `\n\n` after sub-headers ending with `:`

### Test Results

Before (PyPDF2):
- 221 word-paragraphs (word-by-word reading)
- After heuristic fix: 17 over-joined paragraphs
- After structure fix: 159 paragraphs but missing sub-header pauses

After (PyMuPDF4LLM):
- 127 properly structured paragraphs
- "Capabilities:" on its own paragraph (pause before bullets)
- "Hard restrictions:" on its own paragraph (pause before bullets)
- Headers create natural section breaks

### Example Output

Input PDF section:
```
Capabilities:
* RAG over approved project knowledge
* cross-department idea exploration
```

TTS output:
```
Capabilities:

RAG over approved project knowledge. cross-department idea exploration.
```

TTS reads: "Capabilities" [pause] "RAG over approved project knowledge..."
