# 🚀 Get Started — Gym WhatsApp RAG Agent

Follow this guide to go from zero to a working AI-powered WhatsApp assistant for your gym. No prior AI experience needed — every step is explained.

> **Time required:** ~30 minutes (mostly waiting for Meta approvals)
>
> **Cost:** $0 to start (Claude API has a free tier, WhatsApp Cloud API is free for up to 250 conversations/day)

---

## Table of Contents

1. [What You'll Build](#1-what-youll-build)
2. [Prerequisites](#2-prerequisites)
3. [Fork & Clone](#3-fork--clone)
4. [Get Your API Keys](#4-get-your-api-keys)
5. [Configure the App](#5-configure-the-app)
6. [Run It Locally](#6-run-it-locally)
7. [Expose to the Internet](#7-expose-to-the-internet)
8. [Connect WhatsApp](#8-connect-whatsapp)
9. [Test It](#9-test-it)
10. [Deploy to Production](#10-deploy-to-production)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. What You'll Build

```
Your phone 🡆 WhatsApp 🡆 Meta servers 🡆 Your server 🡆 Claude AI 🡆 Reply back
```

When someone texts your WhatsApp Business number, Claude reads the message, searches your gym's knowledge base, books classes if needed, and replies — all automatically.

---

## 2. Prerequisites

You need **three** things before starting:

| What | Why | How to get |
|------|-----|------------|
| **Python 3.12+** | Runs the app | `brew install python` (Mac) or [python.org](https://python.org) |
| **Cloudflared** | Exposes your local server to the internet | `brew install cloudflared` (Mac) or [Cloudflare Tunnel docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) |
| **A phone with WhatsApp** | To test the bot | You already have this! |

---

## 3. Fork & Clone

**Step 1:** Click the **Fork** button at the top-right of [the repo](https://github.com/amitsehgal29/whatsappagent).

**Step 2:** Clone your fork:

```bash
git clone https://github.com/YOUR_USERNAME/whatsappagent.git
cd whatsappagent
```

**Step 3:** Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> 💡 The first install takes a few minutes — PyTorch and sentence-transformers are large packages.

---

## 4. Get Your API Keys

You need keys from two services: Anthropic (the AI brain) and Meta (the WhatsApp connection).

### 4a. Anthropic API Key

1. Go to **[console.anthropic.com](https://console.anthropic.com/)** → Sign up or log in.
2. Click **API Keys** in the left sidebar.
3. Click **Create Key** → give it a name → copy the key.
4. You'll start with $5 of free credits — enough for hundreds of conversations.

### 4b. Meta WhatsApp Cloud API

This one takes more steps but is completely free for testing.

#### Create a Meta Developer App

1. Go to **[developers.facebook.com](https://developers.facebook.com/)** → Log in.
2. Click **My Apps** (top right) → **Create App**.
3. Choose **Business** as the app type → click **Next**.
4. Fill in a name (e.g., "My Gym Bot") and your email → **Create App**.

#### Set Up WhatsApp

5. In the left sidebar, scroll to **Products** → click **WhatsApp** → **Set up**.
6. You'll see a **WhatsApp Business Account (WABA)** created automatically.
7. Under **Step 1: Select a phone number**, Meta gives you a **test phone number** — save this number. This is the number people will text.
8. Under **Step 2: Send a test message**, send yourself a message using the template. This verifies the phone number works.

#### Get Your Credentials

9. In the left sidebar under **WhatsApp → API Setup**, copy:
   - **Phone Number ID** — save this as `WHATSAPP_PHONE_NUMBER_ID`
   - **WhatsApp Business Account ID** — save this as `WHATSAPP_WABA_ID`

10. Click **Generate access token** (or go to **App Settings → Basic** → **Access Token**). Copy the temporary token — save as `WHATSAPP_TOKEN`.

> ⚠️ **Important:** The temporary token expires in 24 hours. For testing, just regenerate it before each session. For production, see [Section 10](#10-deploy-to-production).

#### Create a Verify Token

11. Make up a random string (e.g., `gym-bot-verify-2026`). Save this as `WHATSAPP_VERIFY_TOKEN`. Meta uses this to confirm it's talking to your server.

---

## 5. Configure the App

Open the `.env` file and fill in your keys:

```bash
# Anthropic
ANTHROPIC_API_KEY=sk-ant-api03-your-real-key-here

# WhatsApp Cloud API
WHATSAPP_TOKEN=your-access-token-here
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id-here
WHATSAPP_WABA_ID=your-waba-id-here
WHATSAPP_VERIFY_TOKEN=gym-bot-verify-2026

# Graph API version
GRAPH_API_VERSION=v25.0

# Claude model
MODEL=claude-sonnet-4-6

# YOUR WhatsApp number in E.164 format without the + sign
# (e.g., if your number is +1 234 567 8900, put 12345678900)
DEMO_MEMBER_PHONE=12345678900
```

> 🔒 `.env` is in `.gitignore` — it will never be committed to GitHub.

**Verify your config works:**

```bash
source venv/bin/activate
python3 -c "from app.config import *; print('Config loaded OK')"
```

---

## 6. Run It Locally

```bash
source venv/bin/activate
uvicorn app.main:app --port 8000
```

You should see:

```
INFO:     Started server process
INFO:     Database initialised and seeded.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Quick sanity check** — in a new terminal:

```bash
curl "http://localhost:8000/webhook?hub.mode=subscribe&hub.challenge=hello&hub.verify_token=gym-bot-verify-2026"
```

Should return: `hello`

---

## 7. Expose to the Internet

WhatsApp needs to reach your server via a public HTTPS URL. Cloudflare Tunnel creates one for free.

**In a new terminal:**

```bash
cloudflared tunnel --url http://localhost:8000
```

You'll see output like:

```
2024-01-01T00:00:00Z INF Requesting new quick Tunnel...
2024-01-01T00:00:00Z INF +------------------------------------------------------------+
2024-01-01T00:00:00Z INF |  Your quick Tunnel has been created! Visit it at:           |
2024-01-01T00:00:00Z INF |  https://example-try-cloudflare.com → http://localhost:8000 |
2024-01-01T00:00:00Z INF +------------------------------------------------------------+
```

**Copy the `https://*.trycloudflare.com` URL** — you'll need it next.

> 💡 Leave both terminals running. One runs the app, one runs the tunnel.

---

## 8. Connect WhatsApp

### 8a. Register the Webhook

1. Go back to the **[Meta Developer Dashboard](https://developers.facebook.com/)** → your app → **WhatsApp → Configuration**.
2. Under **Webhook**, click **Edit**.
3. Fill in:
   - **Callback URL:** `https://your-tunnel-url.trycloudflare.com/webhook`
   - **Verify Token:** `gym-bot-verify-2026` (or whatever you set in `.env`)
4. Click **Verify and Save**.

Meta will call your server's `GET /webhook` endpoint. If your app is running and the token matches, it succeeds.

### 8b. Subscribe to Message Events

Webhook verification alone is NOT enough. You must explicitly subscribe to message events:

```bash
curl -X POST \
  "https://graph.facebook.com/v25.0/YOUR_WABA_ID/subscribed_apps" \
  -H "Authorization: Bearer YOUR_WHATSAPP_TOKEN"
```

Replace `YOUR_WABA_ID` and `YOUR_WHATSAPP_TOKEN` with your actual values.

> If you skip this step, your webhook will receive nothing. This is the #1 gotcha.

### 8c. Subscribe to Webhook Fields

5. Still under **WhatsApp → Configuration → Webhook Fields**, click **Manage**.
6. Subscribe to **messages**. You can subscribe to others too (message delivery, etc.) — but **messages** is the only required one.

---

## 9. Test It

### 9a. Text the bot

Open WhatsApp on your phone. Text the **test phone number** Meta gave you (from Step 4b-6).

Send: **"Hi, what membership plans do you offer?"**

The bot should reply within 2-3 seconds with information from the knowledge base about Basic ($29/mo), Premium ($59/mo), and Family ($99/mo) plans.

### 9b. Try more queries

| Message | What it tests |
|---------|--------------|
| "What are your hours?" | RAG retrieval |
| "When is yoga this week?" | Class schedule tool |
| "What's my membership status?" | Member lookup (works because your phone is the demo member) |
| "I want to book a trial class" | Trial booking tool |
| "Who are the trainers?" | Trainer profiles + media send |
| "Register me for the yoga class" | Class registration (after asking for class schedule) |

### 9c. Verify the database

```bash
source venv/bin/activate
python3 -c "
import sqlite3
conn = sqlite3.connect('data/gym.db')
conn.row_factory = sqlite3.Row
for t in ['members','class_schedule','trial_bookings','class_registrations']:
    rows = conn.execute(f'SELECT * FROM {t}').fetchall()
    print(f'{t}: {len(rows)} rows')
    for r in rows:
        print(f'  {dict(r)}')
conn.close()
"
```

---

## 10. Deploy to Production

For a setup that survives restarts and handles real traffic:

### Replace the temporary token
- Go to **Meta Business Settings → Users → System Users**.
- Create a system user, assign it to your WhatsApp Business Account, and generate a **never-expiring access token**.

### Deploy the app
The included `Dockerfile` makes this straightforward:

```bash
docker build -t gym-whatsapp-agent .
docker run -p 8000:8000 --env-file .env --restart always gym-whatsapp-agent
```

Deploy to any cloud that runs containers: **Fly.io**, **Railway**, **Render**, or a $5 **Hetzner VPS** with Docker.

### Replace Cloudflare Tunnel
- In production, deploy behind a real domain with HTTPS (the cloud provider gives you one).
- Update the webhook callback URL in Meta Dashboard to your production URL.

### Production upgrades (when you need them)
- **Redis** instead of in-memory conversation history
- **PostgreSQL** instead of SQLite
- **Qdrant / Pinecone** instead of NumPy for vector search at scale

---

## 11. Troubleshooting

| Problem | Likely Fix |
|---------|-----------|
| **Webhook verification fails** | Check `WHATSAPP_VERIFY_TOKEN` matches in `.env` and Meta Dashboard. Check Cloudflare Tunnel is running. |
| **Messages not arriving** | Run the `subscribed_apps` curl command from Step 8b. This is the most common miss. |
| **"I can only read text messages"** | You sent an image/sticker. The bot only handles text. |
| **Claude returns errors** | Check `ANTHROPIC_API_KEY` in `.env`. Check your Anthropic console for credits. |
| **Media won't send** | Place `.jpg` files named `trainer1.jpg`, `trainer2.jpg` in the `media/` folder. |
| **Port 8000 already in use** | Use a different port: `uvicorn app.main:app --port 8001` (update the tunnel too). |
| **Token expired** | Regenerate a temporary access token in Meta Developer Dashboard. |

---

## Need Help?

- **Anthropic API docs:** [docs.anthropic.com](https://docs.anthropic.com/)
- **WhatsApp Cloud API docs:** [developers.facebook.com/docs/whatsapp/cloudapi](https://developers.facebook.com/docs/whatsapp/cloudapi)
- **Open an issue** on the GitHub repo

---

<p align="center">
  <sub>You now have a production-grade AI agent running on WhatsApp. 🎉</sub>
</p>
