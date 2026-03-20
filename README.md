# 🎙️ Wise Voice AI Agent — Real-Time Customer Support Bot

A production-style **real-time voice assistant** built for Wise customer support.
It listens continuously from the microphone, transcribes speech live, matches intent
against a JSON FAQ knowledge base, and speaks responses back — all in real time.

---

## 🚀 Live Demo

1. Run the agent: `python livekit_agent/agent.py dev`
2. Open: https://agents-playground.livekit.io
3. Enter your LiveKit credentials → Connect → Speak!

---

## 🧠 Architecture

```
User Mic (Browser / LiveKit Playground)
         │
         ▼
  LiveKit Room (WebRTC)
         │
         ▼
  Deepgram Nova-2 (Live Streaming STT)
         │
         ▼
  Transcript Text
         │
         ├── "hold on" / "wait" ──▶ INTERRUPT HANDLER
         │                          Stop TTS immediately
         │                          Wait 10 seconds
         │                          → "Are you still there?"
         │
         └── Normal speech
                  │
                  ▼
           Intent Detection (keyword scoring)
                  │
                  ▼
           FAQ JSON Lookup (data/faq.json)
                  │
                  ▼
           gTTS Synthesis → pydub → AudioFrames
                  │
                  ▼
           LiveKit AudioSource → Room → User hears response
```

---

## 🛠️ Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.10 | Core language |
| LiveKit | 1.1.2 | WebRTC real-time audio |
| livekit-agents | 1.1.7 | Worker + JobContext |
| Deepgram SDK | 3.5.0 | Live speech-to-text |
| gTTS | 2.5.4 | Text-to-speech |
| pydub | 0.25.1 | Audio transcoding |
| numpy | 1.26.4 | PCM frame processing |
| websockets | 12.0 | Deepgram transport |
| python-dotenv | 1.0.1 | Environment config |

---

## 📁 Project Structure

```
voice-agent/
├── livekit_agent/
│   └── agent.py              ← Main LiveKit worker + all agent logic
├── app/
│   ├── __init__.py
│   └── services/
│       ├── __init__.py
│       ├── deepgram_stt.py   ← Deepgram live transcription
│       ├── tts_service.py    ← gTTS + pydub → AudioFrames
│       ├── intent_service.py ← Keyword-based FAQ matching
│       └── faq_service.py    ← JSON FAQ loader
├── data/
│   └── faq.json              ← Wise support knowledge base (8 entries)
├── .env.example              ← Environment variable template
├── requirements.txt          ← All dependencies pinned
└── README.md
```

---

## ⚙️ Setup & Installation

### Prerequisites

| Requirement | Install |
|-------------|---------|
| Python 3.10 | https://python.org |
| ffmpeg | `winget install ffmpeg` (Windows) / `brew install ffmpeg` (Mac) |
| LiveKit account | https://cloud.livekit.io |
| Deepgram account | https://console.deepgram.com |

### Step 1 — Clone / Extract project

```bash
cd voice-agent
```

### Step 2 — Create virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac / Linux
python3.10 -m venv venv
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure environment

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key_here
LIVEKIT_API_SECRET=your_api_secret_here
DEEPGRAM_API_KEY=your_deepgram_api_key_here
```

**Getting credentials:**
- LiveKit → https://cloud.livekit.io → Settings → API Keys
- Deepgram → https://console.deepgram.com → API Keys → Create Key

---

## ▶️ Running the Agent

```bash
# Development mode (auto-restart on file change)
python livekit_agent/agent.py dev

# Production mode
python livekit_agent/agent.py start
```

**Expected terminal output:**
```
INFO  starting worker {"version": "1.1.7"}
INFO  registered worker {"url": "wss://your-project.livekit.cloud", "region": "India South"}
INFO  received job request ...
INFO  Deepgram live connection opened
INFO  Voice agent is live - listening for speech...
INFO  Speaking: Hello! Welcome to Wise support...
```

---

## 🧪 Testing the Agent

### Option 1 — LiveKit Playground (Recommended)

1. Go to 👉 https://agents-playground.livekit.io
2. Enter:
   - **URL:** `wss://your-project.livekit.cloud`
   - **API Key:** your key
   - **Secret:** your secret
3. Click **Connect**
4. Allow microphone access
5. Speak!

### Sample Questions to Test

| You say | Agent responds with |
|---------|-------------------|
| "Where is my money?" | Transfer status explanation |
| "When will my money arrive?" | Delivery time information |
| "I need a proof of payment" | How to download proof |
| "My transfer is delayed" | Delay reasons + next steps |
| "What is a reference number?" | Banking partner reference info |
| "I want to talk to support" | Support contact details |
| "Thank you" | Friendly acknowledgment |
| **"Hold on"** | Stops speaking, waits 10s → "Are you still there?" |

---

## ✨ Key Features

### ✅ Real-Time Voice Pipeline
- Audio streams frame-by-frame via LiveKit WebRTC
- No file uploads, no batch processing — purely streaming

### ✅ Live Transcription
- Deepgram Nova-2 model with `endpointing=300ms`
- Only fires on final (non-interim) results for clean intent detection

### ✅ Keyword-Based Intent Detection
- Scores every FAQ entry by counting keyword matches
- Highest score wins — fast and deterministic

### ✅ Interrupt Handling
```
User says "hold on" or "wait"
    → TTS stops immediately
    → Silence watchdog starts (10 seconds)
    → If no speech in 10s → "Are you still there?"
    → If user speaks → watchdog cancels, normal flow resumes
```

### ✅ Fallback Response
- If no FAQ matches → "This request needs a human support agent. Please hold while I transfer you. Goodbye."

---

## 📋 FAQ Knowledge Base

Edit `data/faq.json` to add entries:

```json
{
  "id": "unique_id",
  "question": "Human readable question",
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "answer": "The exact text the agent will speak."
}
```

Current entries: greeting, check_status, when_arrive, complete_not_arrived,
taking_longer, proof_of_payment, banking_partner_reference, contact_support

---

## 🔧 Design Decisions

| Decision | Reason |
|----------|--------|
| No FastAPI | Fully event-driven via LiveKit worker |
| No `input()` | Non-blocking, production-ready |
| No VoicePipelineAgent | Manual JobContext for full control |
| `async def` Deepgram handlers | SDK 3.5.0 requires awaitable handlers |
| `isinstance(result, str)` guard | Deepgram fires event twice — 2nd time as plain string |
| `asyncio.ensure_future()` | Safe task scheduling from any async context |

---

## 🐛 Troubleshooting

| Error | Fix |
|-------|-----|
| `DEEPGRAM_API_KEY is not set` | Check `.env` file exists and has the key |
| `ffmpeg not found` | Install ffmpeg and restart terminal |
| Agent connects but no transcription | Verify Deepgram key is valid and has credits |
| `Loaded 0 FAQ entries` | Make sure `data/faq.json` exists in project root |
| No audio from agent | Check LiveKit credentials are correct |

---

## 👨‍💻 Author

Built by **Satyam** — AI/ML Engineer  
IIIT Ranchi | Data Science & Machine Learning

**Tech used:** LiveKit · Deepgram · gTTS · Python 3.10 · asyncio

---

## 📄 License

MIT License — Free to use and modify.
