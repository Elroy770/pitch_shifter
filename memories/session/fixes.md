# Web Playback & YouTube Fixer - Session Notes

## Issues Found

### Issue 1: YouTube Download Failing

**Location**: [src/pitch_shifter_backend/services/processing.py](src/pitch_shifter_backend/services/processing.py#L250-L260)
**Problem**: The `download_youtube()` function returns `Path(filename)` where `filename` is just the basename without the directory. Should be `destination_dir / filename`.
**Fix**: Join filename with destination_dir

### Issue 2: Web Playback Not Implemented

**Location**: [frontend/app.js](frontend/app.js#L150-L180) in `renderJob()` function
**Problem**: When a job completes, the player's `src` attribute is never set. The audio/video elements exist but remain empty.
**Fix**: Set player src to download_url when status is 'completed'

## Implementation Steps

1. ✅ Fix YouTube download path bug
2. ✅ Add web playback - populate player src on job completion
3. ⏳ Test both end-to-end

## Files to Modify

- src/pitch_shifter_backend/services/processing.py (download_youtube function)
- frontend/app.js (renderJob and setOutputReady functions)
