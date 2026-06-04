# YouTube Transcript Cleaner

A high-fidelity FastAPI & Web application that takes noisy YouTube auto-generated captions (timedtext API URLs) in `json3` or other formats, converts them to `vtt`, and strips all timings, style tags, and consecutive duplicate phrases/lines.

This creates a perfectly clean, flat plain-text transcript, significantly reducing LLM context token usage and improving model understanding.

## Features

- **Format Conversion**: Auto-converts YouTube `json3` query parameters to `vtt` subtitle format.
- **Roll-Up Deduplication**: Programmatically detects and removes the consecutive duplicate lines characteristic of YouTube's real-time caption scrolling.
- **Tag & Noise Stripping**: Removes style markers, class notations, and micro-timestamps.
- **Token Analytics**: Live computation of characters, estimated token usage, and percentage of tokens saved.
- **Stunning Dark Web UI**: Features glassmorphism panels, glowing buttons, smooth animations, quick-click examples, and a one-click "Copy to Clipboard" utility.

## Getting Started

1. **Install UV** (if not already installed):
   ```bash
   pip install uv
   ```

2. **Run the Server**:
   ```bash
   uv run uvicorn app.main:app --reload
   ```

3. **Use the App**:
   Open [http://localhost:8000](http://localhost:8000) in your web browser.
