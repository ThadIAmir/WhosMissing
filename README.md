# 👥 Who's Missing

A production Telegram bot that tracks attendance polls and automatically tags group members who haven't voted yet.

Built with **Python**, **Flask**, **SQLite**, and **python-telegram-bot** — deployed on PythonAnywhere with zero budget.

---

## The Problem

In recurring group gatherings (weekly football, gaming nights, meetups):

1. Someone creates a poll to check attendance.
2. Hours pass. Some members haven't voted.
3. The organizer manually cross-references the voter list against the group roster and types out individual tags.

**Who's Missing** replaces step 3 with a single command: `/nudge`.

---

## How It Works

/create_poll
Football Friday 8pm Azadi?
I'm in 🟢
Can't come 🔴
Maybe 🟡
// Bring water, park at back gate

text


The bot creates a **public, non-anonymous** Telegram poll. As members vote, it silently tracks them. When you're ready:

/nudge

text


The bot calculates `registered members − voters`, then posts a reply to the poll mentioning everyone who hasn't responded — using `@username` tags or clickable HTML mentions for users without public handles.

---

## Architecture

text

          Telegram Cloud
                │
                │ HTTPS POST (Webhook + secret token)
                ▼
    ┌───────────────────────────┐
    │   PythonAnywhere (WSGI)   │
    │                           │
    │   Flask                   │
    │     └─ asyncio.run()      │
    │          └─ ptb v20+     │
    │                           │
    └───────────┬───────────────┘
                │
                ▼
          SQLite (bot.db)

text


### Technical Challenges Solved

**No `getChatMembers` API.** Telegram intentionally prevents bots from fetching full member rosters. Who's Missing uses a multi-vector discovery pipeline:
- `/sync_admins` — leverages `getChatAdministrators` for instant bulk import
- Passive message listener — records any user who sends a message
- `chat_member` webhook events — tracks joins and leaves in real time
- `poll_answer` events — auto-registers anyone who votes

**Anonymous polls hide voters.** Telegram strips voter IDs from anonymous polls. The bot creates non-anonymous polls (`is_anonymous=False`) to receive `poll_answer` updates with full user data.

**Users without usernames.** Standard `@` mentions fail for private accounts. The bot dynamically generates HTML inline links (`<a href="tg://user?id=...">Name</a>`) that trigger push notifications for all users.

**WSGI ↔ async bridge.** Bridges Flask's synchronous WSGI requests into `python-telegram-bot` v20+ async methods using `asyncio.run()` per request — clean and reliable for low-traffic group bots.

---

## Commands

| Command | Admin Only | Description |
|---|---|---|
| `/create_poll` | ✅ | Create a poll (multi-line format, optional `//` explanation) |
| `/nudge` | ✅ | Tag all registered members who haven't voted |
| `/close_poll` | ✅ | Close the active poll and show final results |
| `/sync_admins` | ✅ | Import all group admins into the member registry |
| `/forget` | ✅ | Remove a member (reply to their message or `/forget @user`) |
| `/setlang` | ✅ | Switch bot language for this group (`fa` / `en`) |
| `/status` | — | View current vote breakdown |
| `/members` | — | List all registered members |
| `/ping` | — | Health check |

---

## Setup

### 1. Install
```bash
git clone https://github.com/YOUR_USERNAME/whosmissing.git
cd whosmissing
pip install -r requirements.txt

2. Configure

Bash

cp config.example.py config.py
# Edit config.py with your BOT_TOKEN and WEBHOOK_SECRET

3. Set Webhook

Bash

curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://<YOUR_DOMAIN>/<WEBHOOK_SECRET>",
    "allowed_updates": ["message", "poll_answer", "chat_member", "my_chat_member"],
    "secret_token": "<WEBHOOK_SECRET>"
  }'

4. First Use

    Add the bot to your group and make it an admin.
    Promote your friends to admin temporarily.
    Run /sync_admins to import everyone.
    Demote friends back to regular members (they stay in the registry).
    Create your first poll with /create_poll.
```

Roadmap

These features are planned if the project gains traction. Feedback, feature requests, and PRs are welcome!

    ⏰ Scheduled reminders — auto-nudge at configurable intervals
    ⏳ Deadlines — auto-close polls after a set time
    📋 Multiple simultaneous polls — e.g., Friday football + Thursday gamenet
    📊 Per-option breakdown — show how many chose each option in /status
    📝 Poll templates — save and reuse common poll formats
    📈 Statistics & history — attendance trends over time
    🔘 Inline button registration — tap-to-register for non-admin members
    💬 Reply-to-create flow — send a poll draft, reply with /create_poll

Open an issue or start a discussion if any of these would be useful to you!

License
MIT
