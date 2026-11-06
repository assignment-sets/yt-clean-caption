import html
import json
import re
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
import httpx

app = FastAPI(
    title="YouTube Transcript Cleaner",
    description="Clean and deduplicate noisy YouTube auto-generated VTT transcripts to prevent token wastage in LLMs.",
    version="0.2.0"
)

class CleanRequest(BaseModel):
    url: str

class TranscriptStats(BaseModel):
    original_chars: int
    cleaned_chars: int
    original_tokens_est: int
    cleaned_tokens_est: int
    tokens_saved_est: int
    savings_percentage: float

class CleanResponse(BaseModel):
    original_url: str
    vtt_url: str
    cleaned_text: str
    stats: TranscriptStats
    video_id: Optional[str] = None
    language: Optional[str] = None

def extract_video_id(url_or_id: str) -> Optional[str]:
    """
    Extracts an 11-character YouTube video ID from various YouTube URL formats:
    - https://www.youtube.com/watch?v=XH36GOyMDQ0
    - https://youtu.be/XH36GOyMDQ0
    - https://www.youtube.com/shorts/XH36GOyMDQ0
    - https://www.youtube.com/embed/XH36GOyMDQ0
    - Raw 11-char video ID (e.g. XH36GOyMDQ0)
    """
    clean_str = url_or_id.strip()
    patterns = [
        r'(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'
    ]
    for pattern in patterns:
        match = re.search(pattern, clean_str)
        if match:
            return match.group(1)
    return None

def convert_url_to_vtt(url: str) -> str:
    """
    Parses a YouTube timedtext URL, ensuring that the fmt query parameter is set to 'vtt'.
    This forces YouTube to return a WebVTT formatted caption response.
    """
    try:
        parsed = urlparse(url)
        params = dict(parse_qsl(parsed.query))
        params['fmt'] = 'vtt'
        new_query = urlencode(params)
        new_url = urlunparse(parsed._replace(query=new_query))
        return new_url
    except Exception as e:
        raise ValueError(f"Failed to process YouTube caption URL: {str(e)}")

async def resolve_video_vtt_url(client: httpx.AsyncClient, video_id: str) -> Tuple[str, str]:
    """
    Queries YouTube's internal Android player endpoint using the video's embedded session key
    and authentic mobile client headers to discover caption tracks without triggering bot challenges.
    Returns (vtt_url, language_code).
    """
    watch_url = f"https://www.youtube.com/watch?v={video_id}"
    browser_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Step 1: Fetch watch page to dynamically extract YouTube's public embedded INNERTUBE_API_KEY and visitorData
    api_key = ""
    visitor_data = ""
    html_content = ""
    try:
        watch_resp = await client.get(watch_url, headers=browser_headers, timeout=12.0)
        if watch_resp.status_code == 200:
            html_content = watch_resp.text
            match_key = re.search(r'\"INNERTUBE_API_KEY\":\"([^\"]+)\"', html_content)
            if match_key:
                api_key = match_key.group(1)
            match_visitor = re.search(r'\"visitorData\":\"([^\"]+)\"', html_content)
            if match_visitor:
                visitor_data = match_visitor.group(1)
    except Exception:
        pass

    # Step 2: Query Android InnerTube player endpoint
    player_url = f"https://www.youtube.com/youtubei/v1/player?key={api_key}" if api_key else "https://www.youtube.com/youtubei/v1/player"
    payload = {
        "context": {
            "client": {
                "clientName": "ANDROID",
                "clientVersion": "20.10.38",
                "androidSdkVersion": 34,
                "hl": "en",
                "gl": "US"
            }
        },
        "videoId": video_id
    }
    if visitor_data:
        payload["context"]["client"]["visitorData"] = visitor_data

    android_headers = {
        "Content-Type": "application/json",
        "User-Agent": "com.google.android.youtube/20.10.38 (Linux; U; Android 14; en_US; Pixel 8 Pro Build/UD1A.230803.041)",
        "X-YouTube-Client-Name": "3",
        "X-YouTube-Client-Version": "20.10.38"
    }
    if visitor_data:
        android_headers["X-Goog-Visitor-Id"] = visitor_data

    try:
        resp = await client.post(player_url, json=payload, headers=android_headers, timeout=12.0)
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Network error querying YouTube caption metadata: {str(e)}"
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"YouTube metadata API returned status code {resp.status_code}."
        )

    data = resp.json()

    # Check playability status
    playability = data.get("playabilityStatus", {})
    caption_tracks = []

    if playability.get("status") in ("OK", None):
        caption_renderer = data.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
        caption_tracks = caption_renderer.get("captionTracks", [])

    # Fallback: If Android endpoint is challenged or tracks not found, check watch page HTML
    if not caption_tracks and html_content:
        cap_match = re.search(r'\"captionTracks\":\s*(\[.+?\])', html_content)
        if cap_match:
            try:
                caption_tracks = json.loads(cap_match.group(1))
            except Exception:
                pass

    if not caption_tracks:
        reason = playability.get("reason", "No captions found for this video. Captions may be disabled or not yet generated.")
        raise HTTPException(status_code=400, detail=f"YouTube caption error: {reason}")

    # Prefer English track, or fallback to the first available track
    selected_track = next((t for t in caption_tracks if t.get("languageCode", "").startswith("en")), caption_tracks[0])
    base_url = selected_track.get("baseUrl")
    lang = selected_track.get("languageCode", "unknown")

    if not base_url:
        raise HTTPException(status_code=404, detail="Caption track baseUrl missing from YouTube response.")

    return convert_url_to_vtt(base_url), lang

def parse_vtt_to_clean_text(vtt_content: str) -> str:
    """
    Parses WebVTT content, stripping out:
    1. Subtitle headers and metadata (WEBVTT, Kind, Language, NOTE, etc.)
    2. Timestamps and placement specs (e.g., '00:00:01.000 --> 00:00:03.000 align:start position:0%')
    3. Inline formatting and tag metadata (e.g., '<00:00:00.560><c> word</c>')
    4. Consecutive duplicate lines caused by YouTube's real-time caption scrolling/buildup
    """
    # Split the VTT into blocks separated by empty lines
    blocks = re.split(r'\r?\n\s*\r?\n', vtt_content.strip())
    raw_lines = []

    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue
        
        # Skip headers
        if any(lines[0].startswith(h) for h in ['WEBVTT', 'Kind:', 'Language:', 'NOTE']):
            continue
            
        # Find the timestamp index
        timestamp_idx = -1
        for i, line in enumerate(lines):
            if '-->' in line:
                timestamp_idx = i
                break
                
        if timestamp_idx == -1:
            continue
            
        # The caption text lies after the timestamp line
        cue_text_lines = lines[timestamp_idx + 1:]
        
        for cue_line in cue_text_lines:
            # Strip XML/HTML tags (like <00:00:00.560> or <c> or </c>)
            cleaned_cue_line = re.sub(r'<[^>]+>', '', cue_line)
            # Unescape HTML entities (e.g. &amp;, &quot;, &#39;)
            cleaned_cue_line = html.unescape(cleaned_cue_line).strip()
            
            if cleaned_cue_line:
                raw_lines.append(cleaned_cue_line)

    # Deduplicate consecutive identical lines
    deduped_lines = []
    for line in raw_lines:
        if not deduped_lines or deduped_lines[-1] != line:
            deduped_lines.append(line)

    # Flatten list of lines into a unified string paragraph
    text = ' '.join(deduped_lines)
    # Clean up any potential multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def estimate_tokens(text: str) -> int:
    """
    Simple heuristic to estimate LLM token count.
    Usually, 1 token is roughly 4 characters in English.
    """
    return max(1, len(text) // 4)

@app.post("/api/clean", response_model=CleanResponse)
async def clean_transcript(request: CleanRequest):
    input_str = str(request.url).strip()
    if not input_str:
        raise HTTPException(status_code=400, detail="URL or Video ID cannot be empty")

    async with httpx.AsyncClient() as client:
        video_id = extract_video_id(input_str)
        detected_lang = None

        if "youtube.com/api/timedtext" in input_str:
            # Direct legacy timedtext URL
            try:
                vtt_url = convert_url_to_vtt(input_str)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        elif video_id:
            # Standard video URL, Short URL, or 11-char Video ID
            vtt_url, detected_lang = await resolve_video_vtt_url(client, video_id)
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid input. Please provide a YouTube video URL (e.g. https://www.youtube.com/watch?v=...), Short, 11-char Video ID, or timedtext URL."
            )

        # Fetch the live WebVTT subtitle file
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = await client.get(vtt_url, headers=headers, timeout=15.0)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch captions from YouTube. YouTube returned status code {response.status_code}."
                )

            vtt_content = response.text
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Network error trying to connect to YouTube caption endpoint: {str(e)}"
            )

    # Clean the transcript
    cleaned_text = parse_vtt_to_clean_text(vtt_content)
    
    # Calculate metrics
    original_chars = len(vtt_content)
    cleaned_chars = len(cleaned_text)
    
    original_tokens = estimate_tokens(vtt_content)
    cleaned_tokens = estimate_tokens(cleaned_text)
    
    tokens_saved = max(0, original_tokens - cleaned_tokens)
    savings_percentage = 0.0
    if original_tokens > 0:
        savings_percentage = round((tokens_saved / original_tokens) * 100, 1)

    return CleanResponse(
        original_url=input_str,
        vtt_url=vtt_url,
        cleaned_text=cleaned_text,
        video_id=video_id,
        language=detected_lang,
        stats=TranscriptStats(
            original_chars=original_chars,
            cleaned_chars=cleaned_chars,
            original_tokens_est=original_tokens,
            cleaned_tokens_est=cleaned_tokens,
            tokens_saved_est=tokens_saved,
            savings_percentage=savings_percentage
        )
    )

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
