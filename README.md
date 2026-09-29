# ⚽ Not-Voters-Tagger (@tagger_by_vote_bot)

A production-ready Telegram group bot built with **Python**, **Flask**, and **SQLite** that tracks attendance polls and automatically identifies and mentions group members who have not yet voted.

---

## 📌 The Problem It Solves

In recurring group gatherings (e.g., weekly football games, gaming nights, meetups):
1. An organizer creates a poll to gauge attendance.
2. After several hours, some members haven't voted.
3. Organizers are forced to manually cross-reference the voter list against the group roster and type out individual tags.

**Not-Voters-Tagger** automates this entire flow with a single command (`/tag_not_voters`), calculating:

$$\text{Non-Voters} = \text{Eligible Members} - \text{Voters}$$

and notifying remaining members using clickable Telegram mentions.

---

## ⚙️ Architecture & Technical Challenges

```text
                  Telegram Cloud
                        │
                        │ HTTPS POST (Webhook)
                        ▼
            ┌─────────────────────────┐
            │ PythonAnywhere / Server  │
            │                         │
            │     Flask (WSGI)        │
            │          │              │
            │     asyncio.run()       │
            │          │              │
            │   python-telegram-bot   │
            │                         │
            └──────────┬──────────────┘
                       │
                       ▼
                 SQLite (bot.db)

Key Technical Challenges Solved:

    No getChatMembers API in Telegram:
        Telegram Bot API intentionally restricts bots from fetching full member rosters for privacy reasons.
        Solution: Multi-vector discovery:
            /sync_admins: Leverages getChatAdministrators to import all promoted friends in 1 click.
            Silent passive listener on chat messages.
            Real-time chat_member update listener for joins/leaves.
            Auto-registration on poll_answer events.

    Tracking Voters via poll_answer:
        Telegram polls are anonymous by default. Bots cannot inspect votes on polls they did not create.
        Solution: The bot generates public, non-anonymous polls (is_anonymous=False) with unique poll_id mapping.

    Handling Users Without Public Usernames:
        Standard @username tags fail for members with private handles.
        Solution: Dynamic HTML inline links (<a href="tg://user?id=USER_ID">Name</a>) ensuring push notifications reach everyone.

    WSGI / Async Bridge:
        Bridges synchronous WSGI web server requests into asynchronous python-telegram-bot v20+ methods with zero hanging event loops.

    State Persistence:
        Backed by SQLite (PRAGMA foreign_keys = ON) with indexes and cascade rules to persist active polls, registered members, votes, and chat language preferences across server worker recycles.

🚀 Features

    🗳️ Dynamic Poll Creation: Create customizable polls with 2–10 options and optional explanations (// explanation).
    🔔 Targeted Reminders: /tag_not_voters tags only those who haven't cast a vote.
    🌐 Bilingual (Persian / English): Set per-chat language using /setlang fa or /setlang en.
    📊 Real-time Status: /status provides a quick overview of votes.
    👥 Roster Management: View registered members with /members and sync administrators with /sync_admins.
    🔄 Vote Retraction Handling: Accurately updates vote status if a user cancels or changes their vote.

📋 Commands
Command	Description
/create_poll	Create a new attendance poll (multi-line format)
/tag_not_voters	Tag all registered group members who haven't voted
/status	View current poll vote breakdown
/sync_admins	Fast-import group admins into member registry
/members	List all registered members in the chat
/setlang <fa|en>	Switch group response language
/ping	Server health-check
Poll Syntax Example:

text

/create_poll
Football Friday 8:00 PM Azadi?
I'm in 🟢
Can't make it 🔴
Tentative 🟡
// Bring water and arrive 15 min early!

🛠️ Local Setup & Deployment
1. Clone & Install

Bash

git clone https://github.com/YOUR_USERNAME/not-voters-tagger.git
cd not-voters-tagger
pip install -r requirements.txt

2. Configuration

Copy the example config and add your credentials:

Bash

cp config.example.py config.py

Edit config.py:

    BOT_TOKEN: From Telegram's @BotFather
    WEBHOOK_SECRET: A secure random token string

3. Set Webhook

Bash

curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://<YOUR_DOMAIN>/<YOUR_WEBHOOK_SECRET>",
    "allowed_updates": ["message", "poll_answer", "chat_member", "my_chat_member"]
  }'

📄 License

MIT License
