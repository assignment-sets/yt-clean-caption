# GEMINI.md - YouTube Transcript Cleaner Context Preservation

Document key tech architecture, commands, code style, algorithms for **YouTube Transcript Cleaner** to preserve developer + agent context.

---

## 🚀 Core Commands

### Development Server
Run local dev server in auto-reload mode (watch dir changes):
```bash
uv run uvicorn app.main:app --port 8000 --reload
```
Once started, app accessible at **[http://localhost:8000](http://localhost:8000)**.

### Dependencies
Manage dependencies via `uv` using non-package config `tool.uv.package = false`.
Add new packages:
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

Reduce LLM token consumption **up to 89%** when parsing auto-generated captions.

Cleaning logic in `app/main.py` under `parse_vtt_to_clean_text(vtt_content)` steps:

1. **Block Separation**: Split WebVTT file by double newlines (`\r?\n\s*\r?\n`) into caption cue blocks.
2. **Metadata Filtering**: Skip headers + meta-properties (`WEBVTT`, `Kind:`, `Language:`, `NOTE`).
3. **Timestamp Removal**: Detect timeline segment (contains `-->`), drop it.
4. **Noise & Tag Stripping**: For each cue text line:
   - Remove word timings + formatting tags (e.g. `<00:00:01.230>` or `<c>`, `</c>`) using regex `re.sub(r'<[^>]+>', '', cue_line)`.
   - Unescape HTML entities (e.g. `&amp;`, `&#39;`) using `html.unescape`.
   - Discard empty rows.
5. **Roll-up Deduplication**: Auto captions scroll by appending words consecutively. To resolve:
   - Track sequential history of lines across blocks.
   - Discard line consecutively identical to previous line.
6. **Paragraph Flattening**: Merge unique rows with single space into narrative paragraph, remove double spacing.

---

## 🔗 YouTube `timedtext` API Specifications

- **Short-Lived Signatures**: timedtext URLs from YouTube contain custom expiration (`&expire=...`) + signature hashes (`&signature=...`). Strictly time-sensitive + IP-bound (return `404` when expired).
- **Conversion to VTT**: Query parameter `fmt` must be `vtt`. backend `convert_url_to_vtt` parses incoming timedtext URL, replaces `fmt=json3` (or other format param) with `fmt=vtt` via `urllib.parse`.
- **User Instruction**: UI displays step-by-step devtools network guide showing how to capture fresh `timedtext` URL from browser network tab.

---

## 🎨 Coding & Design Standards

- **Backend**: FastAPI with standard `Pydantic` validation schemas. `httpx` for async external requests.
- **Frontend Styling**: Clean vanilla CSS, fluid layouts, transitions (`transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1)`), Outfit (Display) + Plus Jakarta Sans (Body) fonts, glassmorphism layers.
- **No JS Frameworks**: Light, fast client using standard Vanilla Javascript (`DOMContentLoaded`, Fetch API, clipboard APIs).
