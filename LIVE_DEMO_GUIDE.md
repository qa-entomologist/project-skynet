# Live Demo Guide - Auto-QA Workflow

## 🎬 Complete Demo Walkthrough

### Pre-Demo Setup (5 minutes before)

1. **Start Mock Datadog Server**
   ```bash
   # Terminal 1
   cd "/Users/dgapuz/DataDog Hackathon"
   python3 mock_datadog_server.py --port 8080
   ```
   Keep this running throughout the demo.

2. **Verify .env Configuration**
   ```bash
   # Check your .env has:
   DD_API_KEY=your_real_key_or_demo_key
   DD_APP_KEY=your_real_key_or_demo_key
   DD_MOCK_SERVER=http://localhost:8080 
   //curl "http://localhost:8080/api/v1/events?start=0&end=$(date +%s)" | python3 -m json.tool
   AGENT_ENV=production
   ```

3. **Test Mock Server**
   ```bash
   # Terminal 2 - Quick test
   curl "http://localhost:8080/api/v1/events?start=0&end=$(date +%s)" | python3 -m json.tool
   ```
   Should show 3 crashes + 2 deployments.

---

## 🎯 Demo Script (10-15 minutes)

### Part 1: The Problem (2 minutes)

**What to say:**
> "When there's a crash or anomaly in production, the first person contacted is usually QA. They have to manually check if the crash is reproducible, which takes 30-60 minutes. Let me show you how we automate this."

**Show:**
- Open Datadog dashboard (or show mock server represents Datadog)
- Point out: "Here we have 3 crashes detected in the last few minutes"

---

### Part 2: Show What Datadog Detected (2 minutes)

**Terminal 2:**
```bash
curl "http://localhost:8080/api/v1/events?start=0&end=$(date +%s)" | python3 -m json.tool
```

**What to say:**
> "Datadog has detected 3 crashes:
> - crash_001: NullPointerException in playback buffer (iOS, 5 min ago)
> - crash_002: OutOfMemoryError in video decoder (Android, 12 min ago)  
> - crash_003: IndexOutOfBoundsException (iOS, 2 min ago)
> 
> Normally, QA would be paged to investigate each of these. Let's see how our agent handles this automatically."

**Point out:**
- Service: playback-service
- Different platforms
- Different severity levels
- Recent deployments (correlation)

---

### Part 3: Run Auto-QA Agent (5 minutes)

**Terminal 3:**
```bash
cd "/Users/dgapuz/DataDog Hackathon"
python3 run_risk_advisor.py --auto-qa \
  --service "playback-service" \
  --platform "ios" \
  --lookback-minutes 15
```

**What to say while it runs:**
> "Now I'm running our Auto-QA agent. Watch what happens:
> 
> 1. **It connects to Datadog** - Querying for anomalies and crashes
> 2. **Detects the crashes** - Found 3 crashes automatically
> 3. **Analyzes the code** - Uses AWS Bedrock to analyze recent code changes
> 4. **Determines reproducibility** - Checks if the crash is likely reproducible
> 5. **Tests reproduction** - Actually tests it in alpha/production
> 6. **Generates QA report** - Provides actionable recommendations"

**While waiting, explain:**
- "The agent is using AWS Bedrock to analyze code changes"
- "It's comparing the crash to recent deployments"
- "It's testing if the crash can be reproduced"

---

### Part 4: Show Results (3 minutes)

**What you'll see:**
```
🤖 Auto-QA Workflow — Automatic Crash Detection & Testing
════════════════════════════════════════════════════════════

  Status: completed
  Service: playback-service
  Anomalies Detected: 3
  Crashes Processed: 3

  📊 Summary:
     Overall Risk Score: 80/100
     Recommendation: BLOCK_RELEASE
     3 crashes processed: 1 confirmed reproducible, 0 not reproducible, 2 need manual QA

  🔍 Crash Analysis Results:

     1. Crash ID: crash_001
        Status: processed
        Reproducible: True
        Confidence: 85%
        Test Result: ✅ Reproduced
        QA Recommendation: ✅ CONFIRMED REPRODUCIBLE - Block release and fix...
```

**What to say:**
> "Here's what the agent found:
> 
> - **Detected 3 crashes** from Datadog automatically
> - **Analyzed code** and determined crash_001 is reproducible (85% confidence)
> - **Tested reproduction** and confirmed it actually crashes
> - **Generated recommendation**: BLOCK RELEASE
> 
> This entire process took [X] seconds, compared to 30-60 minutes of manual QA work."

**Point out:**
- Speed: "This took seconds, not minutes"
- Accuracy: "85% confidence based on code analysis"
- Actionable: "Clear recommendation to block release"
- Evidence: "Shows which files are affected, reproduction steps"

---

### Part 5: Show the Full Workflow (2 minutes)

**What to say:**
> "Let me show you what happened behind the scenes:
> 
> 1. **Anomaly Detection** - Agent queried Datadog Metrics API for crash rate spikes
> 2. **Event Detection** - Queried Datadog Events API for crash events
> 3. **Code Analysis** - Used AWS Bedrock to analyze recent code changes
> 4. **Reproduction Testing** - Automatically tested in alpha environment
> 5. **Report Generation** - Created comprehensive QA report"

**Show the saved report:**
```bash
# Show the saved evaluation
cat evals/run_*.json | python3 -m json.tool | head -50
```

---

## 🎤 Key Talking Points

### Opening Hook
> "What if QA could automatically detect crashes, analyze code, and test reproduction - all without manual intervention? That's what we built."

### During Execution
> "Watch the agent work: It's querying Datadog, analyzing code with AI, and testing reproduction - all automatically."

### Results
> "In [X] seconds, we went from crash detection to actionable QA report. This eliminates the manual 30-60 minute investigation."

### Value Proposition
> "This means:
> - Faster incident response
> - Consistent QA analysis
> - Evidence-based decisions
> - No manual paging of QA engineers"

---

## 🛠️ Troubleshooting During Demo

### If agent is slow:
> "The agent is analyzing code with AWS Bedrock - this takes a few seconds but provides accurate results."

### If no crashes detected:
- Check mock server is running
- Verify service name: `--service "playback-service"`
- Check `.env` has `DD_MOCK_SERVER=http://localhost:8080`

### If errors occur:
> "Let me show you what the agent detected..." (fall back to showing the mock server data)

---

## 📋 Demo Checklist

- [ ] Mock server running (Terminal 1)
- [ ] .env configured correctly
- [ ] Tested mock server with curl
- [ ] Ready to run agent command
- [ ] Know your talking points
- [ ] Have backup plan if something fails

---

## 🎬 Alternative: Shorter Demo (5 minutes)

If you're short on time:

1. **Show crashes in Datadog** (30 sec)
   ```bash
   curl "http://localhost:8080/api/v1/events?start=0&end=$(date +%s)" | python3 -m json.tool
   ```

2. **Run agent** (2 min)
   ```bash
   python3 run_risk_advisor.py --auto-qa --service "playback-service"
   ```

3. **Show results** (2 min)
   - Point out: Detected crashes, analyzed code, tested reproduction
   - Show recommendation: BLOCK RELEASE

4. **Wrap up** (30 sec)
   - "This eliminates manual QA investigation"
   - "Takes seconds instead of minutes"

---

## 💡 Pro Tips

1. **Practice once** before the actual demo
2. **Have Terminal 1, 2, 3 ready** - don't switch during demo
3. **Explain while it runs** - don't wait in silence
4. **Show the mock server** - helps audience understand the flow
5. **Emphasize automation** - "No manual steps required"

---

## 🎯 Success Metrics to Mention

- **Time saved**: 30-60 minutes → seconds
- **Accuracy**: 85% confidence from code analysis
- **Automation**: Zero manual intervention
- **Actionable**: Clear recommendations with evidence

Good luck with your demo! 🚀

