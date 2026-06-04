import html
import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
import httpx

app = FastAPI(
    title="YouTube Transcript Cleaner",
    description="Clean and deduplicate noisy YouTube auto-generated VTT transcripts to prevent token wastage in LLMs.",
    version="0.1.0"
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
    url_str = str(request.url).strip()
    if not url_str:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
        
    if "youtube.com/api/timedtext" not in url_str:
        raise HTTPException(
            status_code=400, 
            detail="Invalid URL. Please provide a valid YouTube timedtext caption URL."
        )

    try:
        vtt_url = convert_url_to_vtt(url_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch the live WebVTT subtitle file
    try:
        async with httpx.AsyncClient() as client:
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
            detail=f"Network error trying to connect to YouTube caption API: {str(e)}"
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
        original_url=url_str,
        vtt_url=vtt_url,
        cleaned_text=cleaned_text,
        stats=TranscriptStats(
            original_chars=original_chars,
            cleaned_chars=cleaned_chars,
            original_tokens_est=original_tokens,
            cleaned_tokens_est=cleaned_tokens,
            tokens_saved_est=tokens_saved,
            savings_percentage=savings_percentage
        )
    )

# Serve Frontend static assets
@app.get("/")
async def serve_index():
    return FileResponse("app/static/index.html")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
