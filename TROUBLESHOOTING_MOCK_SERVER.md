# Troubleshooting Mock Datadog Server

## Issue: 401 Missing API Key

If you're getting "401 Missing API key" errors, the mock server has been updated to be more lenient for demo purposes.

### Solution 1: Restart the Mock Server

The updated server now accepts requests without API keys for demo purposes. **Restart the server** to get the fix:

```bash
# Stop the current server (Ctrl+C)
# Then restart:
python3 mock_datadog_server.py --port 8080
```

### Solution 2: Check How Datadog Client Sends Keys

The Datadog API client might be sending the API key in a way the mock server doesn't recognize. The updated server now:

1. ✅ Checks query parameters: `?api_key=xxx`
2. ✅ Checks headers: `DD-API-KEY: xxx`
3. ✅ Checks Authorization header: `Authorization: Bearer xxx`
4. ✅ **For demo: Allows requests without API key**

### Solution 3: Test the Server Directly

Test if the server is working:

```bash
# Test without API key (should work now)
curl http://localhost:8080/api/v1/events?start=0&end=$(date +%s)

# Test with API key in query
curl "http://localhost:8080/api/v1/events?start=0&end=$(date +%s)&api_key=test123"

# Test with API key in header
curl -H "DD-API-KEY: test123" http://localhost:8080/api/v1/events?start=0&end=$(date +%s)
```

All three should return JSON with events.

### Solution 4: Check Your .env Configuration

Make sure your `.env` has:

```bash
DD_API_KEY=your_real_key_here  # This is used by the agent
DD_MOCK_SERVER=http://localhost:8080
AGENT_ENV=production
```

The `DD_API_KEY` is used by the agent, but the mock server now accepts requests without it for demo purposes.

### Debug Mode

The updated server now prints debug information:

```
[12:34:56] GET /api/v1/events?start=... - 200
[WARNING] No API key provided, but allowing for demo purposes
```

If you see this, the server is working and allowing the request.

## Still Having Issues?

1. **Check server is running:**
   ```bash
   lsof -i :8080
   ```

2. **Check server logs:**
   The server prints each request - you should see logs when the agent makes requests.

3. **Try different port:**
   ```bash
   python3 mock_datadog_server.py --port 8081
   # Update .env: DD_MOCK_SERVER=http://localhost:8081
   ```

4. **Check agent logs:**
   When running the agent, it should show:
   ```
   Using mock Datadog server: http://localhost:8080
   ```

