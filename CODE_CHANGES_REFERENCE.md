# Code Changes Reference

## Issue 1: YouTube Download Path Bug

### File: `src/pitch_shifter_backend/services/processing.py`

#### Location: `download_youtube()` function, lines 248-256

**Before:**

```python
async def download_youtube(url: str, destination_dir: Path) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise HTTPException(status_code=500, detail="yt-dlp is not installed") from exc

    destination_dir.mkdir(parents=True, exist_ok=True)
    options = {
        "outtmpl": str(destination_dir / "%(title).200s-%(id)s.%(ext)s"),
        "noplaylist": True,
        "format": "best",
        "quiet": True,
        "no_warnings": True,
    }

    def _download() -> Path:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return Path(filename)  # ❌ BUG: Missing directory!

    return await asyncio.to_thread(_download)
```

**After:**

```python
async def download_youtube(url: str, destination_dir: Path) -> Path:
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise HTTPException(status_code=500, detail="yt-dlp is not installed") from exc

    destination_dir.mkdir(parents=True, exist_ok=True)
    options = {
        "outtmpl": str(destination_dir / "%(title).200s-%(id)s.%(ext)s"),
        "noplaylist": True,
        "format": "best",
        "quiet": True,
        "no_warnings": True,
    }

    def _download() -> Path:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return destination_dir / filename  # ✅ FIXED: Full path included!

    return await asyncio.to_thread(_download)
```

### Why This Fix Works

- `ydl.extract_info(url, download=True)` downloads the file to the path specified in `outtmpl`
- `ydl.prepare_filename(info)` returns only the basename of the downloaded file
- Without joining with `destination_dir`, the returned path is relative and incomplete
- The fix ensures the full path is returned: `destination_dir / filename`
- This full path is then used in `routes.py` to set `input_path` for the job

---

## Issue 2: Web Playback Not Implemented

### File: `frontend/app.js`

#### Part 1: New Function `setPlayerContent()` (Lines 136-151)

**Added:**

```javascript
function setPlayerContent(downloadUrl, mediaKind) {
  const audioPlayer = el("audioPlayer");
  const videoPlayer = el("videoPlayer");
  const placeholder = el("playerPlaceholder");

  if (!downloadUrl) {
    placeholder.style.display = "flex";
    audioPlayer.removeAttribute("src");
    videoPlayer.removeAttribute("src");
    return;
  }

  // Hide placeholder and set the appropriate player source
  placeholder.style.display = "none";
  if (mediaKind === "video") {
    videoPlayer.src = downloadUrl;
  } else {
    audioPlayer.src = downloadUrl;
  }
}
```

**Purpose:**

- Takes the download URL and media type
- If no URL, shows the placeholder (for failed jobs)
- If URL available, hides placeholder and sets `src` on the correct player

---

#### Part 2: Updated `renderJob()` Function (Lines 185-220)

**Before:**

```javascript
function renderJob(job) {
  state.currentJob = job;
  el("jobStatus").textContent = job.status || "unknown";
  el("jobId").textContent = job.id || job.job_id || "—";
  el("jobType").textContent = job.type || "—";
  el("jobSource").textContent = job.source_url || job.original_name || "—";
  el("jobShift").textContent = formatShiftLabel(job.shift_semitones);
  el("jobFormat").textContent = (job.output_format || "—")
    .toString()
    .toUpperCase();
  el("jobDetectedKey").textContent = job.detected_key || "Unknown";
  el("jobShiftedKey").textContent = job.shifted_key || "Unknown";

  const status = job.status || "unknown";
  if (status === "completed") {
    setBadge("Completed", "success");
    setOutputReady(job.download_url ? job.download_url : `/download/${job.id}`);
    // ❌ Player src never set!
  } else if (status === "failed") {
    setBadge("Failed", "danger");
    setOutputReady(null);
    el("outputText").textContent =
      job.error ||
      "The job failed. Check the backend logs for more information.";
  } else {
    setBadge(status.charAt(0).toUpperCase() + status.slice(1));
    setOutputReady(null);
  }
}
```

**After:**

```javascript
function renderJob(job) {
  state.currentJob = job;
  el("jobStatus").textContent = job.status || "unknown";
  el("jobId").textContent = job.id || job.job_id || "—";
  el("jobType").textContent = job.type || "—";
  el("jobSource").textContent = job.source_url || job.original_name || "—";
  el("jobShift").textContent = formatShiftLabel(job.shift_semitones);
  el("jobFormat").textContent = (job.output_format || "—")
    .toString()
    .toUpperCase();
  el("jobDetectedKey").textContent = job.detected_key || "Unknown";
  el("jobShiftedKey").textContent = job.shifted_key || "Unknown";

  const status = job.status || "unknown";
  if (status === "completed") {
    setBadge("Completed", "success");
    const downloadUrl = job.download_url
      ? job.download_url
      : `/download/${job.id}`;
    setOutputReady(downloadUrl);
    setPlayerContent(downloadUrl, job.media_kind); // ✅ Player src now set!
  } else if (status === "failed") {
    setBadge("Failed", "danger");
    setOutputReady(null);
    setPlayerContent(null, job.media_kind); // ✅ Clear player on failure
    el("outputText").textContent =
      job.error ||
      "The job failed. Check the backend logs for more information.";
  } else {
    setBadge(status.charAt(0).toUpperCase() + status.slice(1));
    setOutputReady(null);
  }
}
```

### Why This Fix Works

1. **Polling System**: The frontend polls `/jobs/{job_id}` every 1.5 seconds via `startPolling()`
2. **Status Change Detection**: When `job.status` changes to "completed", `renderJob()` is called
3. **Player Population**: The new `setPlayerContent()` function is called with:
   - The download URL (either from API or constructed as `/download/{job_id}`)
   - The media kind ("audio" or "video")
4. **Correct Player Selection**: Based on media kind, the appropriate player gets the src:
   - "audio" → sets `audioPlayer.src = downloadUrl`
   - "video" → sets `videoPlayer.src = downloadUrl`
5. **Browser Handling**: Once src is set, the browser's HTML5 media player:
   - Fetches the file from the backend
   - Displays play controls
   - Streams the media when user clicks Play

### HTML Structure Used

```html
<div class="player-stage" id="playerStage">
  <audio id="audioPlayer" controls preload="none" hidden></audio>
  <video id="videoPlayer" controls preload="none" hidden playsinline></video>
</div>
```

The `hidden` attribute is toggled by `setPlayerMode()` to show/hide based on media type.

---

## Data Flow for Web Playback

```
User submits job
    ↓
startPolling() begins polling every 1.5s
    ↓
/jobs/{job_id} endpoint called
    ↓
Backend processes file (FFmpeg pitch shift)
    ↓
Backend updates job status to "completed"
    ↓
Frontend receives updated job status
    ↓
renderJob() called
    ↓
setPlayerContent() called with downloadUrl and media_kind
    ↓
Appropriate player src set (audio or video)
    ↓
Browser displays player controls
    ↓
User clicks Play
    ↓
/download/{job_id} endpoint streams file to browser
    ↓
Media plays in player
```

---

## CORS and Media Streaming

The backend already has CORS enabled in `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

This allows the frontend to:

- Set the media player src to the same-origin `/download/{job_id}` endpoint
- Load and stream media files without CORS errors

---

## Summary of Changes

| File                     | Change                     | Lines            | Impact                              |
| ------------------------ | -------------------------- | ---------------- | ----------------------------------- |
| `services/processing.py` | Fixed YouTube path         | 253              | YouTube downloads now work          |
| `frontend/app.js`        | Added `setPlayerContent()` | 136-151          | Players can be populated with media |
| `frontend/app.js`        | Updated `renderJob()`      | 201-204, 208-209 | Players now auto-load on completion |

All changes are focused and minimal, with no breaking changes to existing functionality.
