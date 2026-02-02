# ⚡ Quick Start - Fix "Backend server not running" Error

## The Problem
Your Chrome extension shows these errors:
- ❌ `[background] FETCH_SCORE error: Failed to fetch`
- ❌ `[content.js] scoring error: Backend server not running`

**Why?** The backend API server needs to be running for the extension to work!

---

## The Solution (2 Minutes)

### Option 1: Use the Startup Script (Easiest)

```bash
# Open Terminal and run:
cd "/Users/naveenus/Library/Mobile Documents/com~apple~CloudDocs/Projects/TubeFocus/YouTube Productivity Score Development Container"

./start_backend.sh
```

The script will:
- ✅ Check if Python is installed
- ✅ Create `.env` file if missing
- ✅ Install dependencies
- ✅ Start the server on port 8080

---

### Option 2: Manual Steps

```bash
# 1. Navigate to backend directory
cd "/Users/naveenus/Library/Mobile Documents/com~apple~CloudDocs/Projects/TubeFocus/YouTube Productivity Score Development Container"

# 2. Create .env file (if it doesn't exist)
cat > .env << 'EOF'
GOOGLE_API_KEY=your_gemini_api_key_here
YOUTUBE_API_KEY=AIzaSyAiwFQ9eSuuMTdcY4XxLCU6991hfjlHeuE
API_KEY=test_key
PORT=8080
ENVIRONMENT=development
DEBUG=True
EOF

# 3. Install dependencies
pip3 install -r requirements.txt

# 4. Start server
python3 api.py
```

---

## Get Your Gemini API Key

**You MUST add a valid Gemini API key to the `.env` file!**

1. Go to: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key
4. Edit `.env` file and replace `your_gemini_api_key_here` with your actual key

---

## Verify It's Working

### 1. Check Server Status
Open http://localhost:8080/health in your browser

Should see:
```json
{
  "status": "healthy",
  "service": "YouTube Relevance Scorer API (Gemini Powered)",
  ...
}
```

### 2. Reload Chrome Extension
1. Go to `chrome://extensions`
2. Find "TubeFocus"  
3. Click reload button (🔄)

### 3. Test on YouTube
1. Open any YouTube video
2. Click TubeFocus extension
3. Start a session with a goal
4. You should see colored overlay (no errors!)

---

## Common Issues

### "pip3: command not found"
Install Python 3:
```bash
# macOS
brew install python3
```

### "Port 8080 already in use"
Kill the process:
```bash
kill -9 $(lsof -ti:8080)
```

### "GOOGLE_API_KEY not configured"
Edit `.env` and add your Gemini API key (see above)

### Extension still shows errors
1. Make sure backend is running (check terminal)
2. Reload extension in `chrome://extensions`
3. Close all YouTube tabs and open new ones

---

## Remember

**The backend server MUST be running for the extension to work!**

Keep the terminal window with `python3 api.py` open while using the extension.

---

## Next: Test All Agents

Once the backend is running:

1. **Gatekeeper**: Videos show colored overlay
2. **Auditor**: Hover on thumbnails → see badges after 2s
3. **Coach**: Watch 3+ videos → get notification after 2min
4. **Librarian**: Use "History" tab to search videos

---

For detailed docs, see: `STARTUP_GUIDE.md`
