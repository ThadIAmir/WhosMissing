"""
Who's Missing — V1
Telegram bot that tracks attendance polls and nudges non-voters.
"""

import asyncio
import html
import logging

from flask import Flask, request
from telegram import Bot
from telegram.constants import ParseMode

import db
from config import BOT_TOKEN, WEBHOOK_SECRET

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

db.init_db()

# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------
T: dict[str, dict[str, str]] = {
    "start": {
        "en": (
            "👋 I'm <b>Who's Missing</b> — I track attendance polls "
            "and tag members who haven't voted yet.\n\n"
            "<b>Commands:</b>\n"
            "• /create_poll — Create a new poll\n"
            "• /nudge — Tag everyone who hasn't voted\n"
            "• /status — See who has voted\n"
            "• /close_poll — Close the active poll\n"
            "• /sync_admins — Import admins as members\n"
            "• /members — List registered members\n"
            "• /forget — Remove a member from the list\n"
            "• /setlang — Change language (fa/en)\n"
            "• /ping — Health check\n\n"
            "ℹ️ Most commands require admin privileges."
        ),
        "fa": (
            "👋 من <b>Who's Missing</b> هستم — نظرسنجی‌های حضور رو پیگیری می‌کنم "
            "و کسایی که رأی ندادن رو منشن می‌کنم.\n\n"
            "<b>دستورات:</b>\n"
            "• /create_poll — ساخت نظرسنجی جدید\n"
            "• /nudge — منشن کسانی که رأی ندادن\n"
            "• /status — مشاهده آرای ثبت‌شده\n"
            "• /close_poll — بستن نظرسنجی فعال\n"
            "• /sync_admins — وارد کردن ادمین‌ها به عنوان اعضا\n"
            "• /members — لیست اعضای ثبت‌شده\n"
            "• /forget — حذف یک عضو از لیست\n"
            "• /setlang — تغییر زبان (fa/en)\n"
            "• /ping — بررسی وضعیت ربات\n\n"
            "ℹ️ بیشتر دستورات نیاز به دسترسی ادمین دارند."
        ),
    },
    "pong": {"en": "pong 🫡", "fa": "پونگ 🫡"},
    "admin_only": {
        "en": "🔒 Only group admins can use this command.",
        "fa": "🔒 فقط ادمین‌های گروه می‌تونن از این دستور استفاده کنن.",
    },
    "poll_usage": {
        "en": (
            "⚠️ <b>Invalid format.</b>\n\n"
            "Usage:\n"
            "<code>/create_poll\n"
            "Poll Question?\n"
            "Option 1\n"
            "Option 2\n"
            "// Optional explanation</code>"
        ),
        "fa": (
            "⚠️ <b>فرمت نامعتبر.</b>\n\n"
            "نحوه استفاده:\n"
            "<code>/create_poll\n"
            "سؤال نظرسنجی؟\n"
            "گزینه ۱\n"
            "گزینه ۲\n"
            "// توضیح اختیاری</code>"
        ),
    },
    "poll_options_count": {
        "en": "⚠️ Need between 2 and 10 options.",
        "fa": "⚠️ بین ۲ تا ۱۰ گزینه لازم است.",
    },
    "poll_question_long": {
        "en": "⚠️ Question too long (max 300 chars).",
        "fa": "⚠️ سؤال خیلی طولانی است (حداکثر ۳۰۰ کاراکتر).",
    },
    "poll_option_long": {
        "en": "⚠️ Option {n} too long (max 100 chars).",
        "fa": "⚠️ گزینه {n} خیلی طولانی است (حداکثر ۱۰۰ کاراکتر).",
    },
    "poll_created": {
        "en": "✅ Poll created! Cast your votes. Use /nudge when ready.",
        "fa": "✅ نظرسنجی ساخته شد! رأی بدید. وقتی آماده بودید /nudge بزنید.",
    },
    "no_active_poll": {
        "en": "ℹ️ No active poll in this chat. Create one with /create_poll.",
        "fa": "ℹ️ نظرسنجی فعالی وجود ندارد. با /create_poll یکی بسازید.",
    },
    "status_no_votes": {
        "en": "No votes recorded yet.",
        "fa": "هنوز رأیی ثبت نشده.",
    },
    "status_voted_count": {
        "en": "✅ <b>{n} voted:</b>",
        "fa": "✅ <b>{n} نفر رأی دادن:</b>",
    },
    "members_empty": {
        "en": (
            "ℹ️ No members registered yet.\n\n"
            "Promote friends to admin and run /sync_admins, "
            "or let them vote/chat."
        ),
        "fa": (
            "ℹ️ هنوز عضوی ثبت نشده.\n\n"
            "دوستاتون رو ادمین کنید و /sync_admins بزنید، "
            "یا بذارید رأی بدن/چت کنن."
        ),
    },
    "members_header": {
        "en": "👥 <b>Registered Members ({n}):</b>",
        "fa": "👥 <b>اعضای ثبت‌شده ({n}):</b>",
    },
    "sync_error": {
        "en": "⚠️ Could not fetch administrators. Make sure the bot is an admin.",
        "fa": "⚠️ نتونستم ادمین‌ها رو بگیرم. مطمئن شو ربات ادمین باشه.",
    },
    "sync_success": {
        "en": "✅ Synced {added} admins.\nTotal registered members: <b>{total}</b>.",
        "fa": "✅ {added} ادمین همگام‌سازی شد.\nکل اعضای ثبت‌شده: <b>{total}</b>.",
    },
    "tag_no_members": {
        "en": "⚠️ No registered members found. Run /sync_admins first.",
        "fa": "⚠️ عضو ثبت‌شده‌ای پیدا نشد. اول /sync_admins بزنید.",
    },
    "tag_all_voted": {
        "en": "🎉 <b>All {n} registered members have voted!</b>\n\nPoll: <i>{q}</i>",
        "fa": "🎉 <b>هر {n} عضو ثبت‌شده رأی دادن!</b>\n\nنظرسنجی: <i>{q}</i>",
    },
    "tag_reminder": {
        "en": (
            "⏰ <b>Reminder: Please vote!</b>\n\n"
            "Poll: <i>{q}</i>\n"
            "Pending ({pending}/{total}):\n\n"
            "{tags}"
        ),
        "fa": (
            "⏰ <b>یادآوری: لطفاً رأی بدید!</b>\n\n"
            "نظرسنجی: <i>{q}</i>\n"
            "منتظر رأی ({pending} از {total}):\n\n"
            "{tags}"
        ),
    },
    "poll_closed": {
        "en": "🔒 Poll closed.",
        "fa": "🔒 نظرسنجی بسته شد.",
    },
    "forget_usage": {
        "en": (
            "Usage:\n"
            "• Reply to someone's message with <code>/forget</code>\n"
            "• Or: <code>/forget @username</code>"
        ),
        "fa": (
            "نحوه استفاده:\n"
            "• روی پیام کسی ریپلای کنید و <code>/forget</code> بزنید\n"
            "• یا: <code>/forget @username</code>"
        ),
    },
    "forget_success": {
        "en": "✅ Removed <b>{name}</b> from the member list.",
        "fa": "✅ <b>{name}</b> از لیست اعضا حذف شد.",
    },
    "forget_not_found": {
        "en": "⚠️ Member not found in this group's list.",
        "fa": "⚠️ این عضو در لیست گروه پیدا نشد.",
    },
    "setlang_usage": {
        "en": "Usage: <code>/setlang fa</code> or <code>/setlang en</code>",
        "fa": "نحوه استفاده: <code>/setlang fa</code> یا <code>/setlang en</code>",
    },
    "setlang_success": {
        "en": "✅ Language set to <b>English</b>.",
        "fa": "✅ زبان به <b>فارسی</b> تغییر کرد.",
    },
}


def t(key: str, chat_id: int, **kwargs) -> str:
    lang = db.get_chat_language(chat_id)
    template = T.get(key, {}).get(lang, T[key]["en"])
    return template.format(**kwargs) if kwargs else template


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------
app = Flask(__name__)


def _extract_command(text: str) -> str:
    if not text.startswith("/"):
        return ""
    return text.split()[0].split("@")[0].lower()


async def _is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Returns True if user is admin/creator. Sends a denial message if not."""
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        if member.status in ("administrator", "creator"):
            return True
    except Exception as e:
        logger.warning("Admin check failed for chat=%s user=%s: %s", chat_id, user_id, e)
    await bot.send_message(chat_id=chat_id, text=t("admin_only", chat_id))
    return False


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------

async def _handle_start(chat_id: int) -> None:
    async with Bot(token=BOT_TOKEN) as bot:
        await bot.send_message(
            chat_id=chat_id, text=t("start", chat_id), parse_mode=ParseMode.HTML,
        )


async def _handle_ping(chat_id: int) -> None:
    async with Bot(token=BOT_TOKEN) as bot:
        await bot.send_message(chat_id=chat_id, text=t("pong", chat_id))


async def _handle_setlang(chat_id: int, user_id: int, text: str) -> None:
    async with Bot(token=BOT_TOKEN) as bot:
        if not await _is_admin(bot, chat_id, user_id):
            return
        parts = text.split()
        if len(parts) < 2 or parts[1].lower() not in ("fa", "en"):
            await bot.send_message(
                chat_id=chat_id, text=t("setlang_usage", chat_id), parse_mode=ParseMode.HTML,
            )
            return
        lang = parts[1].lower()
        db.set_chat_language(chat_id, lang)
        await bot.send_message(
            chat_id=chat_id, text=t("setlang_success", chat_id), parse_mode=ParseMode.HTML,
        )


async def _handle_sync_admins(chat_id: int, user_id: int) -> None:
    async with Bot(token=BOT_TOKEN) as bot:
        if not await _is_admin(bot, chat_id, user_id):
            return
        try:
            admins = await bot.get_chat_administrators(chat_id=chat_id)
        except Exception as e:
            logger.error("Failed to fetch admins: %s", e)
            await bot.send_message(chat_id=chat_id, text=t("sync_error", chat_id))
            return

        added = 0
        for admin in admins:
            u = admin.user
            if u.is_bot:
                continue
            db.save_member(chat_id, u.id, u.first_name or "", u.last_name or "", u.username)
            added += 1

        total = len(db.get_chat_members(chat_id))
        await bot.send_message(
            chat_id=chat_id,
            text=t("sync_success", chat_id, added=added, total=total),
            parse_mode=ParseMode.HTML,
        )


async def _handle_create_poll(chat_id: int, user_id: int, full_text: str) -> None:
    async with Bot(token=BOT_TOKEN) as bot:
        if not await _is_admin(bot, chat_id, user_id):
            return

        lines = [l.strip() for l in full_text.split("\n") if l.strip()]
        if len(lines) < 3:
            await bot.send_message(
                chat_id=chat_id, text=t("poll_usage", chat_id), parse_mode=ParseMode.HTML,
            )
            return

        question = lines[1]
        options = lines[2:]

        explanation = None
        if options and options[-1].startswith("//"):
            explanation = options.pop()[2:].strip() or None

        if len(options) < 2 or len(options) > 10:
            await bot.send_message(chat_id=chat_id, text=t("poll_options_count", chat_id))
            return
        if len(question) > 300:
            await bot.send_message(chat_id=chat_id, text=t("poll_question_long", chat_id))
            return
        for i, opt in enumerate(options):
            if len(opt) > 100:
                await bot.send_message(
                    chat_id=chat_id, text=t("poll_option_long", chat_id, n=i + 1),
                )
                return

        msg = await bot.send_poll(
            chat_id=chat_id, question=question, options=options,
            is_anonymous=False, allows_multiple_answers=False,
            explanation=explanation,
        )
        db.create_poll(msg.poll.id, chat_id, msg.message_id, question, options, explanation)
        logger.info("Poll created: chat=%s, poll_id=%s", chat_id, msg.poll.id)
        await bot.send_message(chat_id=chat_id, text=t("poll_created", chat_id))


async def _handle_status(chat_id: int) -> None:
    poll = db.get_active_poll(chat_id)
    if not poll:
        async with Bot(token=BOT_TOKEN) as bot:
            await bot.send_message(chat_id=chat_id, text=t("no_active_poll", chat_id))
        return

    voters = db.get_poll_voters(poll["poll_id"])
    count = len(voters)
    q = html.escape(poll["question"])
    lines = [f"📊 <b>{q}</b>", ""]

    if count == 0:
        lines.append(t("status_no_votes", chat_id))
    else:
        lines.append(t("status_voted_count", chat_id, n=count))
        for name in voters.values():
            lines.append(f"  • {html.escape(name)}")

    async with Bot(token=BOT_TOKEN) as bot:
        await bot.send_message(
            chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML,
        )


async def _handle_members(chat_id: int) -> None:
    members = db.get_chat_members(chat_id)
    if not members:
        async with Bot(token=BOT_TOKEN) as bot:
            await bot.send_message(chat_id=chat_id, text=t("members_empty", chat_id))
        return

    lines = [t("members_header", chat_id, n=len(members)), ""]
    for m in members:
        uname = f" (@{m.username})" if m.username else ""
        lines.append(f"  • {html.escape(m.display_name)}{uname}")

    async with Bot(token=BOT_TOKEN) as bot:
        await bot.send_message(
            chat_id=chat_id, text="\n".join(lines), parse_mode=ParseMode.HTML,
        )


async def _handle_nudge(chat_id: int, user_id: int) -> None:
    async with Bot(token=BOT_TOKEN) as bot:
        if not await _is_admin(bot, chat_id, user_id):
            return

        poll = db.get_active_poll(chat_id)
        if not poll:
            await bot.send_message(chat_id=chat_id, text=t("no_active_poll", chat_id))
            return

        members = db.get_chat_members(chat_id)
        if not members:
            await bot.send_message(chat_id=chat_id, text=t("tag_no_members", chat_id))
            return

        voters = db.get_poll_voters(poll["poll_id"])
        not_voters = [m for m in members if m.user_id not in voters]
        q = html.escape(poll["question"])

        if not not_voters:
            await bot.send_message(
                chat_id=chat_id,
                text=t("tag_all_voted", chat_id, n=len(members), q=q),
                parse_mode=ParseMode.HTML,
                reply_to_message_id=poll["message_id"],
            )
            return

        tags = " ".join(m.tag for m in not_voters)
        await bot.send_message(
            chat_id=chat_id,
            text=t("tag_reminder", chat_id, q=q, pending=len(not_voters), total=len(members), tags=tags),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=poll["message_id"],
        )


async def _handle_close_poll(chat_id: int, user_id: int) -> None:
    async with Bot(token=BOT_TOKEN) as bot:
        if not await _is_admin(bot, chat_id, user_id):
            return

        poll = db.get_active_poll(chat_id)
        if not poll:
            await bot.send_message(chat_id=chat_id, text=t("no_active_poll", chat_id))
            return

        try:
            await bot.stop_poll(chat_id=chat_id, message_id=poll["message_id"])
        except Exception as e:
            logger.warning("stop_poll failed (may already be closed): %s", e)

        db.close_poll(poll["poll_id"])
        await bot.send_message(
            chat_id=chat_id, text=t("poll_closed", chat_id),
            reply_to_message_id=poll["message_id"],
        )


async def _handle_forget(
    chat_id: int, admin_id: int, text: str, reply_user: dict,
) -> None:
    async with Bot(token=BOT_TOKEN) as bot:
        if not await _is_admin(bot, chat_id, admin_id):
            return

        target_id = None
        target_name = None

        # Mode 1: reply to a message
        if reply_user and reply_user.get("id"):
            target_id = reply_user["id"]
            target_name = f"{reply_user.get('first_name', '')} {reply_user.get('last_name', '')}".strip()

        # Mode 2: @username or numeric ID in text
        else:
            parts = text.split()
            if len(parts) >= 2:
                arg = parts[1]
                if arg.startswith("@"):
                    member = db.get_member_by_username(chat_id, arg[1:])
                    if member:
                        target_id = member.user_id
                        target_name = member.display_name
                elif arg.isdigit():
                    target_id = int(arg)
                    member = db.get_member_by_id(chat_id, target_id)
                    if member:
                        target_name = member.display_name

        if not target_id:
            await bot.send_message(
                chat_id=chat_id, text=t("forget_usage", chat_id), parse_mode=ParseMode.HTML,
            )
            return

        existing = db.get_member_by_id(chat_id, target_id)
        if not existing:
            await bot.send_message(chat_id=chat_id, text=t("forget_not_found", chat_id))
            return

        db.remove_member(chat_id, target_id)
        await bot.send_message(
            chat_id=chat_id,
            text=t("forget_success", chat_id, name=html.escape(target_name or str(target_id))),
            parse_mode=ParseMode.HTML,
        )


# ---------------------------------------------------------------------------
# Poll Answer Handler
# ---------------------------------------------------------------------------

async def _handle_poll_answer(
    poll_id: str, user_id: int,
    first_name: str, last_name: str, username: str | None,
    option_ids: list[int],
) -> None:
    poll = db.get_poll_by_id(poll_id)
    if not poll:
        return

    full_name = f"{first_name} {last_name}".strip() or username or f"User {user_id}"
    db.save_member(poll["chat_id"], user_id, first_name, last_name, username)

    if option_ids:
        db.record_vote(poll_id, user_id, full_name)
        logger.info("Vote: poll=%s, user=%s", poll_id, full_name)
    else:
        db.retract_vote(poll_id, user_id)
        logger.info("Retract: poll=%s, user=%s", poll_id, full_name)


# ---------------------------------------------------------------------------
# Chat Member Handler
# ---------------------------------------------------------------------------

def _handle_chat_member_update(data: dict) -> None:
    cm = data.get("chat_member", {})
    chat_id = cm.get("chat", {}).get("id")
    status = cm.get("new_chat_member", {}).get("status", "")
    user = cm.get("new_chat_member", {}).get("user", {})

    if not chat_id or not user.get("id") or user.get("is_bot"):
        return

    uid = user["id"]
    if status in ("member", "administrator", "creator", "restricted"):
        db.save_member(chat_id, uid, user.get("first_name", ""), user.get("last_name", ""), user.get("username"))
        logger.info("Member joined: chat=%s, uid=%s", chat_id, uid)
    elif status in ("left", "kicked"):
        db.remove_member(chat_id, uid)
        logger.info("Member left: chat=%s, uid=%s", chat_id, uid)


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

@app.route(f"/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    # (e) Verify Telegram secret token header
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != WEBHOOK_SECRET:
        logger.warning("Rejected request with invalid secret token")
        return "Unauthorized", 403

    data = request.get_json(force=True)

    if "chat_member" in data:
        _handle_chat_member_update(data)
        return "OK", 200

    poll_answer = data.get("poll_answer")
    if poll_answer:
        u = poll_answer.get("user", {})
        asyncio.run(_handle_poll_answer(
            poll_answer["poll_id"], u["id"],
            u.get("first_name", ""), u.get("last_name", ""), u.get("username"),
            poll_answer.get("option_ids", []),
        ))
        return "OK", 200

    message = data.get("message")
    if message:
        chat_id = message.get("chat", {}).get("id")
        from_user = message.get("from", {})
        text = message.get("text", "")
        uid = from_user.get("id")

        if chat_id and uid and not from_user.get("is_bot"):
            db.save_member(chat_id, uid, from_user.get("first_name", ""), from_user.get("last_name", ""), from_user.get("username"))

        if chat_id and text:
            cmd = _extract_command(text)

            if cmd == "/start":
                asyncio.run(_handle_start(chat_id))
            elif cmd == "/ping":
                asyncio.run(_handle_ping(chat_id))
            elif cmd == "/setlang":
                asyncio.run(_handle_setlang(chat_id, uid, text))
            elif cmd == "/create_poll":
                asyncio.run(_handle_create_poll(chat_id, uid, text))
            elif cmd == "/status":
                asyncio.run(_handle_status(chat_id))
            elif cmd == "/members":
                asyncio.run(_handle_members(chat_id))
            elif cmd == "/sync_admins":
                asyncio.run(_handle_sync_admins(chat_id, uid))
            elif cmd in ("/tag_not_voters", "/nudge"):
                asyncio.run(_handle_nudge(chat_id, uid))
            elif cmd == "/close_poll":
                asyncio.run(_handle_close_poll(chat_id, uid))
            elif cmd == "/forget":
                reply_user = message.get("reply_to_message", {}).get("from", {})
                asyncio.run(_handle_forget(chat_id, uid, text, reply_user))

    return "OK", 200


@app.route("/")
def index():
    return "Who's Missing is running. 🟢", 200