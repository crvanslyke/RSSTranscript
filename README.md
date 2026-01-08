# Podcast Transcript Downloader

A simple Python tool to download and convert podcast transcripts from an RSS feed.

## Features
- Parses podcast RSS feeds.
- Finds episodes with the `podcast:transcript` tag.
- Downloads transcripts (HTML, VTT, SRT, JSON, etc.).
- **Automatic Conversion**: Converts HTML transcripts to clean plain text (`.txt`).
- **Resumable**: Skips already downloaded episodes.

## Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/crvanslyke/RSSTranscript.git
    cd RSSTranscript
    ```

2.  **Create a Virtual Environment**:
    ```bash
    python3 -m venv venv
    ```

3.  **Install Dependencies**:
    ```bash
    source venv/bin/activate
    pip install -r requirements.txt
    ```

## Usage

You must use the python executable inside the virtual environment.

### Option 1: Activate first (Recommended)
```bash
source venv/bin/activate
python main.py https://feeds.captivate.fm/live-well-and-flourish/
```

### Option 2: Run directly
```bash
./venv/bin/python main.py https://feeds.captivate.fm/live-well-and-flourish/
```

## Output
Files are saved in the `downloads/` directory, organized by Podcast Title.
