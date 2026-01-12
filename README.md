# TinyTTS

A lightweight, self-hosted text-to-speech web application that converts text and documents into natural-sounding audio.

## Features

- **Multiple Input Types**: Paste text directly or upload files (.txt, .md, .pdf)
- **Text Preprocessing**: Intelligent preprocessing for TTS-friendly output
  - Markdown stripping (headers, bold, italic, code blocks, links)
  - List conversion to natural speech patterns
  - Table-to-prose conversion
  - Text normalization (currency, dates, percentages, units, abbreviations)
- **Multiple Voices**: Support for 10 different voice options
- **Adjustable Speed**: Playback speed from 0.5x to 4.0x
- **Conversion History**: Browse and replay previous conversions
- **Smart Chunking**: Handles large documents with sentence-boundary-aware chunking
- **Storage Management**: Automatic cleanup when storage limits are reached
- **Dark Mode**: Toggle between light and dark themes

## Tech Stack

- **Backend**: Python/Flask
- **Frontend**: HTML, Tailwind CSS, Vanilla JavaScript
- **Database**: SQLite
- **TTS Engine**: OpenAI-compatible TTS API (via LiteLLM or similar)
- **Audio Processing**: pydub, ffmpeg

## Prerequisites

- Python 3.10+
- ffmpeg (for audio processing)
- Access to an OpenAI-compatible TTS API endpoint

## Installation

### Local Development

1. Clone the repository:
```bash
git clone https://github.com/yourusername/TinyTTS.git
cd TinyTTS
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the environment example and configure:
```bash
cp .env.example .env
# Edit .env with your settings
```

5. Run the application:
```bash
python run.py
```

The application will be available at `http://localhost:4040`

### Docker

Build and run with Docker:

```bash
docker build -t tinytts .
docker run -d -p 4040:4040 \
  -e LITELLM_API_KEY=your_api_key \
  -e LITELLM_BASE_URL=https://your-tts-endpoint.com \
  -v tinytts_data:/data \
  tinytts
```

Or use Docker Compose:

```bash
docker-compose up -d
```

## Configuration

Configure via environment variables or `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `LITELLM_API_KEY` | API key for TTS service | (required) |
| `LITELLM_BASE_URL` | TTS API endpoint URL | `http://localhost:4000` |
| `TTS_MODEL` | TTS model to use | `tts-kokoro` |
| `DEFAULT_VOICE` | Default voice selection | `af_alloy` |
| `DEFAULT_SPEED` | Default playback speed | `1.0` |
| `DATA_DIR` | Directory for data storage | `/data` |
| `MAX_STORAGE_GB` | Max storage before cleanup | `10` |
| `PORT` | Server port | `4040` |

### Available Voices (Kokoro TTS)

| Voice | Gender | Accent |
|-------|--------|--------|
| af_alloy | Female | American |
| af_nova | Female | American |
| af_bella | Female | American |
| af_sarah | Female | American |
| af_sky | Female | American |
| am_echo | Male | American |
| am_onyx | Male | American |
| am_adam | Male | American |
| bm_fable | Male | British |
| bm_george | Male | British |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main web interface |
| `/api/convert` | POST | Start a new conversion |
| `/api/status/<job_id>` | GET | Check conversion status |
| `/api/history` | GET | Get conversion history |
| `/api/audio/<id>` | GET | Stream audio file |
| `/api/download/<id>` | GET | Download audio file |
| `/api/delete/<id>` | DELETE | Delete a conversion |

## Project Structure

```
TinyTTS/
├── app/
│   ├── __init__.py      # Flask app factory
│   ├── config.py        # Configuration
│   ├── routes.py        # API endpoints
│   ├── tts.py           # TTS conversion logic
│   ├── preprocessor.py  # Text preprocessing pipeline
│   ├── chunker.py       # Text chunking
│   ├── extractors.py    # File content extraction
│   ├── database.py      # SQLite setup
│   ├── models.py        # Data models
│   ├── storage.py       # Storage management
│   └── templates/       # HTML templates
├── static/
│   ├── css/             # Stylesheets
│   └── js/              # JavaScript
├── tests/               # Test suite
├── run.py               # Application entry point
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration
└── docker-compose.yml   # Docker Compose setup
```

## Text Preprocessing

TinyTTS includes a comprehensive text preprocessing pipeline optimized for TTS:

1. **Table Conversion**: Markdown tables become prose ("Header is Value, Header is Value.")
2. **Markdown Stripping**: Removes formatting while preserving content
3. **List Conversion**: Bullet/numbered lists become natural sentences
4. **Text Normalization**:
   - `$100` → "100 dollars"
   - `50%` → "50 percent"
   - `01/15/2024` → "January 15th, 2024"
   - `Dr.` → "Doctor"
   - `10km` → "10 kilometers"
   - `1st` → "first"
5. **Whitespace Cleanup**: Collapses multiple spaces/newlines

## Development

Run tests:
```bash
pytest tests/ -v
```

Run with debug mode:
```bash
python run.py
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
