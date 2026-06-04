# GEMINI.md - YouTube Transcript Cleaner Context Preservation

This file documents the key technical architecture, commands, code style guidelines, and algorithms for the **YouTube Transcript Cleaner** to help preserve developer and agent context across sessions.

---

## 🚀 Core Commands

### Development Server
Run the local dev server in auto-reload mode (watches directory changes):
```bash
uv run uvicorn app.main:app --port 8000 --reload
```
Once started, the application is accessible at **[http://localhost:8000](http://localhost:8000)**.

### Dependencies
Dependencies are managed via `uv` using the non-package configuration `tool.uv.package = false`.
To add new packages:
```bash
uv add <package-name>
```

---

## 📂 Project Directory Structure

```
yt-transcript/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application, clean & deduplicate engine
│   └── static/          # Single-Page Web Frontend assets
│       ├── index.html   # Semantic structure and Google Font pairings
│       ├── style.css    # Premium glassmorphic cyber theme and layouts
│       └── script.js    # Fetch logic, counter animations, clipboard actions
├── pyproject.toml       # UV project dependencies (FastAPI, uvicorn, httpx)
├── GEMINI.md            # Active context preservation file (this file)
└── README.md            # General setup and usage overview
```

---

## 🧠 VTT Cleaning & Deduplication Algorithm

The core value proposition of this application is reducing LLM token consumption by **up to 89%** when parsing auto-generated captions. 

The cleaning logic is implemented in `app/main.py` under the function `parse_vtt_to_clean_text(vtt_content)` and follows these steps:

1. **Block Separation**: Splits the WebVTT file by double newlines (`\r?\n\s*\r?\n`) into individual caption cue blocks.
2. **Metadata Filtering**: Skips headers and meta-properties (`WEBVTT`, `Kind:`, `Language:`, `NOTE`).
3. **Timestamp Removal**: Detects the timeline segment (line containing `-->`) and drops it.
4. **Noise & Tag Stripping**: For each cue text line:
   - Removes word-level timings and formatting tags (e.g. `<00:00:01.230>` or `<c>`, `</c>`) using regex `re.sub(r'<[^>]+>', '', cue_line)`.
   - Unescapes HTML entities (like `&amp;` or `&#39;`) using `html.unescape`.
   - Discards empty rows.
5. **Roll-up Deduplication**: Auto-generated YouTube captions scroll by repeatedly appending words across consecutive cues. To resolve this:
   - Tracks a sequential history of lines across all blocks.
   - Discards any line that is **consecutively identical** to the previous line in the accumulator.
6. **Paragraph Flattening**: Merges all unique rows with a single space into a coherent narrative paragraph, removing double spacing.

---

## 🔗 YouTube `timedtext` API Specifications

- **Short-Lived Signatures**: Timedtext caption URLs copied from YouTube include custom expiration parameters (`&expire=...`) and signature hashes (`&signature=...`). These are **strictly time-sensitive and IP-bound** and will return HTTP `404` when expired.
- **Conversion to VTT**: To fetch clean captions, query parameter `fmt` must be set to `vtt`. The backend converter `convert_url_to_vtt` parses the incoming timedtext URL and replaces `fmt=json3` (or any other format parameter) with `fmt=vtt` using standard `urllib.parse` tools.
- **User Instruction**: In the UI, a step-by-step devtools network extraction guide is displayed to show users how to capture a fresh `timedtext` URL directly from their watching browser instance.

---

## 🔗 YouTube `timedtext` API Specifications

- **Short-Lived Signatures**: Timedtext caption URLs copied from YouTube include custom expiration parameters (`&expire=...`) and signature hashes (`&signature=...`). These are **strictly time-sensitive and IP-bound** and will return HTTP `404` when expired.
- **Conversion to VTT**: To fetch clean captions, query parameter `fmt` must be set to `vtt`. The backend converter `convert_url_to_vtt` parses the incoming timedtext URL and replaces `fmt=json3` (or any other format parameter) with `fmt=vtt` using standard `urllib.parse` tools.
- **User Instruction**: In the UI, a step-by-step devtools network extraction guide is displayed to show users how to capture a fresh `timedtext` URL directly from their watching browser instance.

---

## 🎨 Coding & Design Standards

- **Backend**: FastAPI with standard `Pydantic` validation schemas. `httpx` is used for asynchronous external requests.
- **Frontend Styling**: Clean vanilla CSS with fluid layouts, custom CSS transitions (`transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1)`), Outfit (Display) and Plus Jakarta Sans (Body) font pairings, and glassmorphic translucent layers.
- **No JS Frameworks**: Keeping the client lightweight and extremely performant by utilizing standard modular Vanilla Javascript (`DOMContentLoaded`, asynchronous Fetch API, standard clipboard APIs).
