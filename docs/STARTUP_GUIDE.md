# 🚀 TubeFocus AI Agents - Quick Start Guide

## ⚠️ Fixing "Backend server not running" Error

The Chrome extension errors you're seeing mean the backend API server isn't running. Follow these steps to fix it:

---

## Step 1: Install Backend Dependencies

Open your terminal and run:

```bash
cd "/Users/naveenus/Library/Mobile Documents/com~apple~CloudDocs/Projects/TubeFocus/YouTube Productivity Score Development Container"

# Install dependencies
pip3 install -r requirements.txt
```

**If you don't have pip3**, install Python first:
- macOS: `brew install python3` (requires Homebrew)
- Or download from: https://www.python.org/downloads/

---

## Step 2: Set Environment Variables

The backend needs API keys to work. Create a `.env` file:

```bash
# Create .env file
cat > .env << 'EOF'
GOOGLE_API_KEY=your_gemini_api_key_here
YOUTUBE_API_KEY=AIzaSyAiwFQ9eSuuMTdcY4XxLCU6991hfjlHeuE
API_KEY=test_key
PORT=8080
ENVIRONMENT=development
DEBUG=True
EOF
```

**⚠️ Replace `your_gemini_api_key_here` with your actual Google Gemini API key.**

Get a Gemini API key here: https://makersuite.google.com/app/apikey

---

## Step 3: Start the Backend Server

```bash
# Make sure you're in the Development Container directory
python3 api.py
```

**You should see:**
```
INFO:__main__:Starting TubeFocus API server...
INFO:__main__:Environment: development
INFO:__main__:Debug mode: True
 * Running on http://0.0.0.0:8080
```

**Keep this terminal window open!** The server needs to stay running.

---

## Step 4: Test the Backend

Open a new terminal and test:

```bash
# Test health endpoint
curl http://localhost:8080/health

# You should see:
# {"status":"healthy","service":"YouTube Relevance Scorer API (Gemini Powered)",...}
```

---

## Step 5: Reload Chrome Extension

1. Go to `chrome://extensions`
2. Find "TubeFocus"
3. Click the **Reload** button (🔄)
4. The errors should now be gone!

---

## Step 6: Test the Extension

1. **Start a session:**
   - Click the TubeFocus extension icon
   - Go to "Setup" tab
   - Enter a goal: "Learn about machine learning"
   - Set duration: 25 minutes
   - Click "Start Session"

2. **Test Gatekeeper (Real-time scoring):**
   - Navigate to any YouTube video
   - You should see a colored overlay (green/red gradient)
   - Check extension popup "Current" tab for score

3. **Test Auditor (Hover detection):**
   - Go to YouTube homepage
   - Hover over video thumbnails for 2+ seconds
   - Look for badges: "✓ Verified" or "⚠️ Clickbait"

4. **Test Coach (Proactive intervention):**
   - Watch 3+ videos during your session
   - After 2 minutes, you may see a coach notification
   - Check "Current" tab for session stats

5. **Test Librarian (Search):**
   - Go to "History" tab in popup
   - Enter a search query (if videos are indexed)
   - See semantic search results

---

## Troubleshooting

### Error: "pip3: command not found"
**Solution:** Install Python 3
```bash
# macOS with Homebrew
brew install python3

# Or download from python.org
```

### Error: "Address already in use (port 8080)"
**Solution:** Kill existing process on port 8080
```bash
# Find process using port 8080
lsof -ti:8080

# Kill it
kill -9 $(lsof -ti:8080)

# Then restart: python3 api.py
```

### Error: "GOOGLE_API_KEY not configured"
**Solution:** Make sure you created `.env` file with valid API key
```bash
# Check if .env exists
cat .env

# Should show:
# GOOGLE_API_KEY=YOUR_ACTUAL_KEY_HERE
# YOUTUBE_API_KEY=...
```

### Error: "ModuleNotFoundError: No module named 'flask'"
**Solution:** Install dependencies again
```bash
pip3 install -r requirements.txt --upgrade
```

### Extension still shows errors after starting backend
**Solution:** 
1. Close all YouTube tabs
2. Reload extension in `chrome://extensions`
3. Open new YouTube tab
4. Start session again

---

## Quick Command Reference

### Start Backend (every time):
```bash
cd "/Users/naveenus/Library/Mobile Documents/com~apple~CloudDocs/Projects/TubeFocus/YouTube Productivity Score Development Container"
python3 api.py
```

### Stop Backend:
Press `Ctrl+C` in the terminal

### Check if Backend is Running:
```bash
curl http://localhost:8080/health
```

### View Backend Logs:
Just look at the terminal where `python3 api.py` is running

---

## Available Endpoints (for testing)

Once backend is running, you can test these endpoints:

```bash
# Health check
curl http://localhost:8080/health

# Test simple scoring (requires API key)
curl -X POST http://localhost:8080/score/simple \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: test_key" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "goal": "learn about music",
    "mode": "title_and_description"
  }'

# Get transcript
curl -X GET http://localhost:8080/transcript/dQw4w9WgXcQ \
  -H "X-API-KEY: test_key"
```

---

## Architecture Reminder

```
Chrome Extension (Frontend)
    ↓
background.js (makes API calls)
    ↓
http://localhost:8080 (Backend Flask Server)
    ↓
4 AI Agents:
  - Gatekeeper (scoring)
  - Auditor (clickbait detection)
  - Coach (behavior intervention)
  - Librarian (search/memory)
```

**The extension NEEDS the backend running to work!**

---

## Next Steps After It Works

1. ✅ Verify all 4 agents work
2. 📝 Document your learnings
3. 🎯 Practice explaining the architecture
4. 🚀 Deploy to Cloud Run (optional)
5. 💼 Prepare for interviews!

---

## Need Help?

**Common issues:**
- Backend not starting → Check Python version (`python3 --version` should be 3.8+)
- API key errors → Double-check `.env` file has valid Gemini key
- Port conflicts → Change PORT in `.env` to different number (e.g., 8081)

**Check logs:**
- Backend logs: Terminal where `python3 api.py` runs
- Extension logs: Chrome DevTools Console (F12)
- Background script: `chrome://extensions` → "Inspect views: background page"
