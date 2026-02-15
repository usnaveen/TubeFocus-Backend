# 🚨 Error Handling System - YouTube Productivity Scorer API

## 📋 Overview

This API implements a comprehensive error handling system with custom error codes following industry standards. All errors return structured JSON responses with consistent formatting for easy frontend integration.

## 🔧 Error Response Format

All error responses follow this standardized format:

```json
{
  "error": true,
  "error_code": 1001,
  "message": "Video not found or inaccessible",
  "details": {
    "video_id": "dQw4w9WgXcQ",
    "possible_reasons": ["Video is private", "Video is deleted", "Invalid video ID"]
  },
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

## 📊 Error Code Categories

### 🎥 Video-Related Errors (1000-1099)
| Code | Message | HTTP Status | Description |
|------|---------|-------------|-------------|
| 1001 | VIDEO_NOT_FOUND | 404 | Video not found, private, or deleted |
| 1002 | VIDEO_PRIVATE | 403 | Video is private and inaccessible |
| 1003 | VIDEO_DELETED | 410 | Video has been deleted |
| 1004 | INVALID_VIDEO_ID | 400 | Invalid YouTube video ID format |
| 1005 | INVALID_VIDEO_URL | 400 | Invalid YouTube URL format |

### 📝 Data Availability Errors (1100-1199)
| Code | Message | HTTP Status | Description |
|------|---------|-------------|-------------|
| 1101 | MISSING_TITLE | 400 | Video title is missing |
| 1102 | MISSING_DESCRIPTION | 400 | Video description is missing |
| 1103 | MISSING_TAGS | 400 | Video tags are missing |
| 1104 | MISSING_CATEGORY | 400 | Video category is missing |
| 1105 | INSUFFICIENT_DATA | 400 | No scoring data available for requested parameters |

### 🔑 API Configuration Errors (1200-1299)
| Code | Message | HTTP Status | Description |
|------|---------|-------------|-------------|
| 1201 | YOUTUBE_API_KEY_MISSING | 503 | YouTube API key not configured |
| 1202 | YOUTUBE_API_QUOTA_EXCEEDED | 429 | YouTube API quota exceeded |
| 1203 | YOUTUBE_API_DISABLED | 503 | YouTube API is disabled |
| 1204 | YOUTUBE_API_INVALID_KEY | 401 | YouTube API key is invalid |

### 🧠 Scoring Errors (1300-1399)
| Code | Message | HTTP Status | Description |
|------|---------|-------------|-------------|
| 1301 | SCORING_MODELS_NOT_LOADED | 503 | AI models not loaded |
| 1302 | SCORING_FAILED | 500 | Scoring computation failed |
| 1303 | INVALID_PARAMETERS | 400 | Invalid scoring parameters |

### ✅ Request Validation Errors (1400-1499)
| Code | Message | HTTP Status | Description |
|------|---------|-------------|-------------|
| 1401 | INVALID_GOAL | 400 | Invalid goal format |
| 1402 | INVALID_API_KEY | 401 | Invalid API key |
| 1403 | MISSING_REQUIRED_FIELDS | 400 | Missing required request fields |

### ⚙️ System Errors (1500-1599)
| Code | Message | HTTP Status | Description |
|------|---------|-------------|-------------|
| 1501 | INTERNAL_ERROR | 500 | Internal server error |
| 1502 | SERVICE_UNAVAILABLE | 503 | Service temporarily unavailable |

## 🎯 Frontend Integration Guide

### 1. Error Handling in Extension

The Chrome extension should handle these errors gracefully and provide user-friendly messages:

```javascript
// Example error handling in background.js
async function handleAPIError(response) {
  if (response.error) {
    const errorCode = response.error_code;
    const message = response.message;
    
    switch (errorCode) {
      case 1001: // VIDEO_NOT_FOUND
        showUserMessage("This video is not available or has been removed.");
        break;
        
      case 1201: // YOUTUBE_API_KEY_MISSING
        showUserMessage("YouTube API is not configured. Please contact support.");
        break;
        
      case 1105: // INSUFFICIENT_DATA
        showUserMessage("Not enough information available to score this video.");
        break;
        
      default:
        showUserMessage(`Error: ${message}`);
    }
    
    // Log error for debugging
    console.error(`API Error ${errorCode}: ${message}`, response.details);
  }
}
```

### 2. User Interface Error Display

#### Score Card Error States
```javascript
function updateScoreCard(errorResponse) {
  const scoreCard = document.getElementById('score-card');
  
  if (errorResponse.error) {
    // Show error state
    scoreCard.innerHTML = `
      <div class="error-state">
        <div class="error-icon">⚠️</div>
        <div class="error-message">${errorResponse.message}</div>
        <div class="error-details">${formatErrorDetails(errorResponse.details)}</div>
        <button onclick="retryScoring()">Retry</button>
      </div>
    `;
    
    // Add error-specific styling
    scoreCard.classList.add('error');
  }
}
```

#### Toast Notifications
```javascript
function showErrorToast(errorResponse) {
  const toast = document.createElement('div');
  toast.className = 'error-toast';
  toast.innerHTML = `
    <div class="toast-content">
      <span class="toast-icon">❌</span>
      <span class="toast-message">${errorResponse.message}</span>
    </div>
  `;
  
  document.body.appendChild(toast);
  
  // Auto-remove after 5 seconds
  setTimeout(() => {
    toast.remove();
  }, 5000);
}
```

### 3. Retry Logic

Implement smart retry logic for transient errors:

```javascript
async function scoreVideoWithRetry(videoData, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch('/score/detailed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(videoData)
      });
      
      const result = await response.json();
      
      if (result.error) {
        // Don't retry on client errors (4xx)
        if (response.status >= 400 && response.status < 500) {
          throw new Error(result.message);
        }
        
        // Retry on server errors (5xx)
        if (attempt < maxRetries) {
          await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
          continue;
        }
      }
      
      return result;
      
    } catch (error) {
      if (attempt === maxRetries) {
        throw error;
      }
      
      // Exponential backoff
      await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, attempt)));
    }
  }
}
```

## 🔍 Error Scenarios & Solutions

### Scenario 1: Missing Description
**Request**: Score video with `["description"]` parameter
**Response**: 
```json
{
  "error": true,
  "error_code": 1105,
  "message": "No scoring data available for requested parameters",
  "details": {
    "requested_parameters": ["description"],
    "missing_data": ["description"],
    "available_data": ["title", "category"]
  }
}
```
**Frontend Action**: Show message "Description not available for this video. Using title and category instead."

### Scenario 2: YouTube API Unavailable
**Request**: Any scoring request
**Response**:
```json
{
  "error": true,
  "error_code": 1201,
  "message": "YouTube API key not configured",
  "details": {
    "solution": "Set YOUTUBE_API_KEY environment variable"
  }
}
```
**Frontend Action**: Show maintenance message and disable scoring functionality.

### Scenario 3: Video Not Found
**Request**: Score non-existent video
**Response**:
```json
{
  "error": true,
  "error_code": 1001,
  "message": "Video not found or inaccessible",
  "details": {
    "video_id": "invalid_id",
    "possible_reasons": ["Video is private", "Video is deleted", "Invalid video ID"]
  }
}
```
**Frontend Action**: Show "Video not available" message and suggest checking the URL.

## 🎨 CSS for Error States

```css
/* Error state styling */
.error-state {
  text-align: center;
  padding: 20px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #dc2626;
}

.error-icon {
  font-size: 2rem;
  margin-bottom: 10px;
}

.error-message {
  font-weight: 600;
  margin-bottom: 10px;
}

.error-details {
  font-size: 0.875rem;
  color: #7f1d1d;
  margin-bottom: 15px;
}

/* Toast notifications */
.error-toast {
  position: fixed;
  top: 20px;
  right: 20px;
  background: #dc2626;
  color: white;
  padding: 12px 16px;
  border-radius: 6px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
```

## 📱 Mobile-Friendly Error Handling

```javascript
function showMobileError(errorResponse) {
  // Use native mobile alerts for critical errors
  if (errorResponse.error_code >= 1200) { // API configuration errors
    alert(`Service Error: ${errorResponse.message}`);
    return;
  }
  
  // Use in-app error display for user errors
  showInAppError(errorResponse);
}
```

## 🔄 Error Recovery Strategies

1. **Automatic Retry**: For server errors (5xx)
2. **User Retry**: For client errors (4xx) with retry button
3. **Fallback Scoring**: Use available parameters when some are missing
4. **Graceful Degradation**: Show partial results when possible
5. **Offline Mode**: Cache previous scores for unavailable videos

## 📊 Error Monitoring

```javascript
// Send error analytics to monitoring service
function logErrorToAnalytics(errorResponse) {
  analytics.track('api_error', {
    error_code: errorResponse.error_code,
    endpoint: currentEndpoint,
    user_agent: navigator.userAgent,
    timestamp: new Date().toISOString()
  });
}
```

This error handling system ensures your extension provides a professional, user-friendly experience even when things go wrong! 🚀
