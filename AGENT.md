# AGENT.md - Developer & Agent Context

This document preserves the development and deployment architecture of the **YouTube Transcript Cleaner** to facilitate onboarding for future agents and developers.

---

## 📂 Project Architecture & Directory Structure

```
yt-transcript/
├── app/
│   ├── __init__.py
│   └── main.py          # FastAPI application & VTT cleaning engine
├── public/              # Static Frontend Assets (served at Root /)
│   ├── index.html       # Entrypoint page
│   └── static/          # Subdirectories for styled assets
│       ├── index.html   # (Optional / not used, root level is preferred)
│       ├── script.js    # Client-side fetch & UI interactions
│       └── style.css    # Premium glassmorphic cyber theme and layout
├── wrangler.jsonc       # Cloudflare Workers configuration file
├── pyproject.toml       # UV project dependencies (FastAPI, uvicorn, httpx)
├── GEMINI.md            # Original development context
└── AGENT.md             # Deployment and runtime integration context (this file)
```

---

## ⚙️ Runtime Modes (Dual Compatibility)

The application code is designed to run seamlessly in two distinct environments:

### 1. Standard ASGI Environment (Uvicorn / Local)
When run outside the Cloudflare runtime, the app functions as a standard FastAPI server:
- Frontend assets are mounted via `fastapi.staticfiles.StaticFiles` mapping `public/static` to `/static`.
- The root URL `/` serves `public/index.html` dynamically via file read.
- **Command**:
  ```bash
  uv run uvicorn app.main:app --port 8000 --reload
  ```

### 2. Cloudflare Workers Serverless Environment (Pyodide)
When deployed to Cloudflare Workers, the app uses native WebAssembly-based Python support:
- Cloudflare **Static Assets** intercepts static file requests (like `/index.html`, `/style.css`, `/script.js`) and serves them directly from the edge, bypassing the Python runtime entirely.
- The Workers runtime routes dynamic requests (like POST `/api/clean`) to the Python worker.
- The `asgi` built-in module handles request adapters between Workers and FastAPI.

#### Conditional Entrypoint Implementation:
```python
try:
    from workers import WorkerEntrypoint
    import asgi

    class Default(WorkerEntrypoint):
        async def fetch(self, request):
            return await asgi.fetch(app, request, self.env)
except ImportError:
    # Serve Frontend static assets only when running locally (outside of Cloudflare Workers)
    @app.get("/")
    async def serve_index():
        from pathlib import Path
        from fastapi.responses import HTMLResponse
        path = Path("public/index.html")
        if path.exists():
            return HTMLResponse(content=path.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>YouTube Transcript Cleaner</h1>")

    app.mount("/static", StaticFiles(directory="public/static"), name="static")
```

---

## 🚀 Key Commands

### Local Development (FastAPI / Uvicorn)
```bash
uv run uvicorn app.main:app --port 8000 --reload
```

### Local Workers Simulation (Wrangler Emulator)
To test the Cloudflare Workers bundling and routing logic locally:
```bash
uvx --from workers-py pywrangler dev --port 8787
```

### Cloudflare Workers Deployment
To deploy the stateless python worker and static assets:
```bash
uvx --from workers-py pywrangler deploy
```

> [!IMPORTANT]
> **Do not use bare `npx wrangler deploy` directly.**
> Cloudflare Python Workers compile against Pyodide (WASM) and resolve packages into `python_modules/` via `pylock.toml`. Bare `npx wrangler deploy` bypasses package vendoring and triggers `ModuleNotFoundError: No module named 'fastapi'` on the edge. Always use `uvx --from workers-py pywrangler deploy`. (Requires `uv >= 0.13.4`, run `uv self update` if needed).

---

## 📄 Cloudflare Configuration (`wrangler.jsonc`)

```jsonc
{
  "$schema": "node_modules/wrangler/config-schema.json",
  "name": "yt-clean-caption",
  "main": "app/main.py",
  "compatibility_date": "2026-06-03",
  "compatibility_flags": [
    "python_workers"
  ],
  "assets": {
    "directory": "./public"
  }
}
```

---

## 🧠 VTT Cleaning & Deduplication Algorithm

The core cleaner logic lies in `app/main.py` under the function `parse_vtt_to_clean_text(vtt_content)`:
1. **Block separation**: Split by double newlines (`\r?\n\s*\r?\n`).
2. **Metadata filtering**: Skip headers and meta properties (`WEBVTT`, `Kind:`, `Language:`, `NOTE`).
3. **Timestamp removal**: Detect timeline segment (contains `-->`) and drop it.
4. **Format/Tag stripping**: Strip inline timing and formatting tags (e.g. `<00:00:01.230>` or `<c>`) using regex `re.sub(r'<[^>]+>', '', cue_line)`. Unescape HTML entities.
5. **Roll-up Deduplication**: Compare consecutive lines. If a line matches the previous line, discard it.
6. **Paragraph flattening**: Combine all unique rows with a single space into a narrative paragraph.

---

## 🛡️ Caption Extraction & Anti-Bot Handshake

When querying YouTube from Cloudflare Workers (datacenter IPs), bare unauthenticated requests to YouTube APIs return `LOGIN_REQUIRED ("Sign in to confirm you’re not a bot")`.

To bypass this without external proxies or Google Cloud API keys, `resolve_video_vtt_url` in `app/main.py` uses a lightweight mobile handshake:
1. **Dynamic Session Extraction**: Fetches the video watch page with browser headers to extract YouTube's public embedded `INNERTUBE_API_KEY` and session `visitorData`.
2. **Android Client Emulation**: Queries `https://www.youtube.com/youtubei/v1/player?key={api_key}` with the `ANDROID` client payload (`clientVersion: 20.10.38`, `androidSdkVersion: 34`) and mobile headers (`X-YouTube-Client-Name: 3`, `X-Goog-Visitor-Id: visitorData`).
3. **Fallback Discovery**: If the mobile endpoint fails, parses the `captionTracks` directly from the watch page HTML.
4. **URL Format**: Forces `fmt=vtt` query param on the signed `baseUrl` so the VTT engine can clean it. Direct `timedtext` URLs are also accepted for backward compatibility.
