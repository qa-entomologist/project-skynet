# Browser Demo - Viewing Crashes in "Datadog"

## Quick Browser Access

### Option 1: View Events (Crashes) in Browser

Open in your browser:
```
http://localhost:8080/api/v1/events?start=0&end=1771625103
```

Or use current timestamp:
```
http://localhost:8080/api/v1/events?start=0&end=$(date +%s)
```

**Note:** Replace `$(date +%s)` with actual timestamp, or use a large number like `9999999999`

### Option 2: Root Endpoint (Shows Info)

Now you can visit:
```
http://localhost:8080/
```

This will show:
- Available endpoints
- Sample usage
- Server status

### Option 3: Pretty JSON Viewer

For better viewing, use a JSON formatter:
```
http://localhost:8080/api/v1/events?start=0&end=9999999999
```

Then use browser extensions like:
- JSON Formatter (Chrome)
- JSONView (Firefox)

Or use online tools:
1. Copy the JSON from browser
2. Paste into https://jsonformatter.org/

## For Your Demo

**Best approach: Use curl in terminal for cleaner output:**

```bash
curl "http://localhost:8080/api/v1/events?start=0&end=$(date +%s)" | python3 -m json.tool
```

This formats the JSON nicely and is easier to read during a demo.

## Quick Test URLs

**Root (shows server info):**
```
http://localhost:8080/
```

**Events (crashes):**
```
http://localhost:8080/api/v1/events?start=0&end=9999999999
```

**Metrics:**
```
http://localhost:8080/api/v1/query?query=avg:crash_rate{service:playback-service}&from=0&to=9999999999
```

