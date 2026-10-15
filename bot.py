import os
import re
import time
import json
import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from aiohttp import web
from dotenv import load_dotenv
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import (
    InputPeerUser,
    UpdateBotChatInviteRequester,
    PeerUser,
    PeerChannel,
)
from telethon.errors import (
    UserIsBlockedError,
    FloodWaitError,
    UserNotParticipantError,
    PeerIdInvalidError,
    ChatInvalidError,
    ChannelInvalidError,
    MessageIdInvalidError,
)

# ------------------ ENVIRONMENT ------------------
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ProBotX")

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", 10000))
SESSION_STRING = os.environ.get("SESSION_STRING", "")

START_TIME = time.time()


def parse_admin_ids(env_string):
    ids = []
    for uid in env_string.split(","):
        uid = uid.strip()
        if uid.lstrip("-").isdigit():
            ids.append(int(uid))
    return ids


ROOT_ADMINS = parse_admin_ids(os.environ.get("ADMIN_IDS", "0"))
ADMIN_IDS = list(ROOT_ADMINS)

# ------------------ DATABASE & STATE ------------------
DB_PATH = Path("bot_data.db")

tracked_users: dict[int, int] = {}
blocked_users: set[int] = set()
banned_users: set[int] = set()
user_join_dates: dict[int, str] = {}
user_meta: dict[int, dict] = {}  # {uid: {"referred_by": int, "referrals": int, "last_seen": str, "vip": int}}
saved_messages: dict[int, dict] = {}
button_forwards: dict[str, list] = {}

welcome_enabled = True
animations_enabled = True
maintenance_mode = False
broadcast_cancel_flag = False
bot_username_cache = ""

# Default "👇" रखा है जैसा तेरे इस कोड में था (Admin Panel से बदल भी सकते हो)
user_menu_text = "👇"
support_username = "@SAHILOFFICIAL_0"
force_channels: list[str] = []  # Supports multiple channels!
banner_config = {"msg_id": 0, "chat_id": 0}
click_stats = {"prediction": 0, "hack": 0, "support": 0, "vip_profile": 0}
anim_style = "royal_gold"  # royal_gold | cyberpunk | matrix | quantum | stealth

recently_welcomed: set[int] = set()
user_chat_state: dict[int, bool] = {}
admin_chat_state: dict[int, dict] = {}
auto_replies: dict[str, str] = {}
admin_msg_map: dict[tuple, list] = {}
rate_limit_bucket: dict[int, list[float]] = {}  # Anti-flood tracking

ADMIN_KB_LABELS = {
    "📊 stats", "⚙️ status", "📢 broadcast", "✉️ send message",
    "🔘 set button", "🗑 clear button", "🔢 set sequence", "🖼️ menu & banner",
    "🔒 force join", "🤖 auto-replies", "👑 manage admins", "🔇 toggle welcome",
    "📁 backup", "🔄 restore", "🧹 cleanup", "🔍 find user", "🛠 maintenance",
    "🎬 anim theme", "panel", "menu", "admin"
}

HOME_BACK_ROW = [
    Button.inline("🏠 Console Home", data=b"adm_home"),
    Button.inline("✖ Dismiss", data=b"adm_cancel"),
]
CANCEL_BTN = [
    [
        Button.inline("🏠 Back to Console", data=b"adm_home"),
        Button.inline("✖ Cancel", data=b"adm_cancel"),
    ]
]
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


# ------------------ LUXURY UI BOX & PROGRESS HELPERS ------------------
def ui_header(title: str, subtitle: str = "PROBOT-X LUXURY SUITE") -> str:
    return (
        f"╭━━━✦ **💎 {title}** ✦━━━╮\n"
        f"┆  *{subtitle}*\n"
        f"╰━━━━━━━━━━━━━━━━━━━━━━━╯"
    )


def ui_divider() -> str:
    return "━━━━━━━━━━━━━━━━━━━━━━━"


def make_bar(pct: int, length: int = 10, style: str = "modern") -> str:
    pct = max(0, min(100, pct))
    filled = int((pct / 100) * length)
    if style == "gold":
        return "▰" * filled + "▱" * (length - filled)
    elif style == "dots":
        return "⬤" * filled + "○" * (length - filled)
    return "█" * filled + "░" * (length - filled)


# ------------------ MULTI-THEME LUXURY ANIMATION PRESETS ------------------
ANIM_THEMES = {
    "royal_gold": {
        "hack": [
            (
                "╭━━━✦ **👑 ROYAL VIP VAULT** ✦━━━╮\n"
                "┆ 🔐 `Authenticating VIP Passkey...`\n"
                "┆ `▰▰▱▱▱▱▱▱▱▱ 18%`\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
                0.32,
            ),
            (
                "╭━━━✦ **👑 ROYAL VIP VAULT** ✦━━━╮\n"
                "┆ 🛰 `Establishing Encrypted Uplink...`\n"
                "┆ `▰▰▰▰▰▱▱▱▱▱ 52%`\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
                0.32,
            ),
            (
                "╭━━━✦ **👑 ROYAL VIP VAULT** ✦━━━╮\n"
                "┆ 💎 `Unsealing Number Hack Archive...`\n"
                "┆ `▰▰▰▰▰▰▰▰▱▱ 86%`\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
                0.32,
            ),
            (
                "╭━━━✦ **👑 ROYAL VIP VAULT** ✦━━━╮\n"
                "┆ ✨ **VIP PACKAGE UNLOCKED (100%)**\n"
                "┆ `▰▰▰▰▰▰▰▰▰▰ 100%` 🚀\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
                0.35,
            ),
        ],
        "prediction": [
            (
                "╭━━━✦ **📈 LUXURY AI ORACLE** ✦━━━╮\n"
                "┆ 🧠 `Syncing Live Market Liquidity...`\n"
                "┆ `▰▰▱▱▱▱▱▱▱▱ 22%`\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
                0.32,
            ),
            (
                "╭━━━✦ **📈 LUXURY AI ORACLE** ✦━━━╮\n"
                "┆ 📊 `Scanning 10,000+ Colour Cycles...`\n"
                "┆ `▰▰▰▰▰▰▱▱▱▱ 64%`\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
                0.32,
            ),
            (
                "╭━━━✦ **📈 LUXURY AI ORACLE** ✦━━━╮\n"
                "┆ 🎯 `Locking 99.6% Precision Signal...`\n"
                "┆ `▰▰▰▰▰▰▰▰▰▱ 94%`\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
                0.32,
            ),
            (
                "╭━━━✦ **📈 LUXURY AI ORACLE** ✦━━━╮\n"
                "┆ 💸 **GOLDEN SIGNAL READY (100%)**\n"
                "┆ `▰▰▰▰▰▰▰▰▰▰ 100%` ✨\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
                0.35,
            ),
        ],
    },
    "cyberpunk": {
        "hack": [
            ("⚡ `[ROOT] Connecting to Dark-Node Proxy Server...`\n`[█░░░░░░░░░] 12%`", 0.32),
            ("🌐 `[BYPASS] Injecting packet spoofing into firewall...`\n`[███░░░░░░░] 34%`", 0.32),
            ("🔐 `[CRACK] Bypassing SHA-256 Security Matrix...`\n`[█████░░░░░] 58%`", 0.32),
            ("🧬 `[DECRYPT] Unlocking VIP Number Hack Payload...`\n`[████████░░] 84%`", 0.32),
            ("📂 `[VERIFIED] Checksum matched! Extracting files...`\n`[██████████] 100%`", 0.32),
            ("✅ **SUCCESS:** Package extracted securely. Sending now... 🚀", 0.35),
        ],
        "prediction": [
            ("🤖 `[QUANTUM-AI] Booting Neural Prediction Engine v5.0...`\n`[█░░░░░░░░░] 15%`", 0.32),
            ("📊 `[MARKET-SCAN] Fetching live colour trading history...`\n`[████░░░░░░] 42%`", 0.32),
            ("🧠 `[DEEP-LEARN] Analyzing 10,000+ winning patterns...`\n`[███████░░░] 71%`", 0.32),
            ("🔍 `[ACCURACY] Filtering 99.4% high-probability trend...`\n`[█████████░] 93%`", 0.32),
            ("🎯 `[SIGNAL LOCKED] High-Win Colour Prediction Ready!`\n`[██████████] 100%`", 0.32),
            ("🎯 **SIGNAL READY:** Forwarding prediction details... 💸", 0.35),
        ],
    },
    "matrix": {
        "hack": [
            ("🟢 `01001101 [MATRIX-NODE] Entering Mainframe...`\n`[▓▓░░░░░░░░] 18%`", 0.32),
            ("🟢 `10110010 [DECODE] Tracing encrypted TCP stream...`\n`[▓▓▓▓░░░░░░] 44%`", 0.32),
            ("🟢 `01110101 [OVERFLOW] Overriding kernel permissions...`\n`[▓▓▓▓▓▓▓░░░] 76%`", 0.32),
            ("🟢 `11111111 [ACCESS GRANTED] Dumping VIP Hack Files...`\n`[▓▓▓▓▓▓▓▓▓▓] 100%`", 0.32),
            ("🔓 **MATRIX UNLOCKED:** Delivering payload... ⚡", 0.35),
        ],
        "prediction": [
            ("🟢 `00101101 [ORACLE-AI] Synchronizing Matrix Seed...`\n`[▓▓░░░░░░░░] 20%`", 0.32),
            ("🟢 `11010110 [PATTERN] Computing RNG hash sequence...`\n`[▓▓▓▓▓░░░░░] 55%`", 0.32),
            ("🟢 `01011100 [PREDICT] Next colour outcome isolated...`\n`[▓▓▓▓▓▓▓▓▓░] 92%`", 0.32),
            ("💎 **ORACLE LOCKED:** Sending VIP Colour Signal... 🚀", 0.35),
        ],
    },
    "quantum": {
        "hack": [
            ("⚛️ `[Q-CORE] Initializing 128-Qubit Entanglement...`\n`[▰▱▱▱▱▱▱▱▱▱] 14%`", 0.32),
            ("🛸 `[TUNNEL] Quantum tunneling past server auth...`\n`[▰▰▰▰▱▱▱▱▱▱] 46%`", 0.32),
            ("💠 `[SUPERPOSITION] Collapsing key possibilities...`\n`[▰▰▰▰▰▰▰▰▱▱] 82%`", 0.32),
            ("✨ `[SINGULARITY] VIP Hack Package Materialized!`\n`[▰▰▰▰▰▰▰▰▰▰] 100%`", 0.35),
        ],
        "prediction": [
            ("🌌 `[NEBULA-AI] Calibrating temporal market sensors...`\n`[▰▰▱▱▱▱▱▱▱▱] 22%`", 0.32),
            ("⚡ `[SYNAPSE] Simulating 1,000,000 trade timelines...`\n`[▰▰▰▰▰▰▱▱▱▱] 64%`", 0.32),
            ("🔮 `[CONVERGENCE] 99.8% Probability Vector Locked!`\n`[▰▰▰▰▰▰▰▰▰▰] 100%`", 0.35),
        ],
    },
}


def get_uptime():
    seconds = int(time.time() - START_TIME)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"


def format_eta(seconds: float) -> str:
    if seconds <= 0 or seconds > 86400:
        return "Calculating..."
    m, s = divmod(int(seconds), 60)
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def check_rate_limit(uid: int, max_events: int = 7, window: float = 4.0) -> bool:
    """Returns True if user is flooding and should be throttled."""
    if uid in ADMIN_IDS:
        return False
    now = time.time()
    history = rate_limit_bucket.get(uid, [])
    history = [t for t in history if now - t < window]
    history.append(now)
    rate_limit_bucket[uid] = history
    return len(history) > max_events


# ------------------ ANIMATION ENGINE ------------------
async def play_animation(
    event_or_msg,
    frames: list[tuple[str, float]],
    is_edit: bool = False,
    use_reply: bool = True,
):
    """Plays a multi-frame animation smoothly with FloodWait protection."""
    if is_edit:
        msg = event_or_msg
    else:
        msg = await (
            event_or_msg.reply(frames[0][0])
            if use_reply
            else event_or_msg.respond(frames[0][0])
        )

    if not animations_enabled or anim_style == "stealth":
        return msg

    start_idx = 0 if is_edit else 1
    for i in range(start_idx, len(frames)):
        text_frame, delay = frames[i]
        await asyncio.sleep(delay)
        try:
            await msg.edit(text_frame)
        except FloodWaitError as e:
            await asyncio.sleep(min(e.seconds, 2))
        except Exception:
            pass
    return msg


# ------------------ DATABASE ENGINE ------------------
def init_db():
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                access_hash INTEGER NOT NULL,
                blocked INTEGER DEFAULT 0,
                joined_date TEXT,
                referred_by INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                last_seen TEXT,
                vip INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS messages (
                step INTEGER PRIMARY KEY,
                msg_type TEXT,
                text TEXT,
                msg_id INTEGER,
                from_chat INTEGER
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS button_msgs (
                btn_key TEXT,
                msg_id INTEGER NOT NULL,
                from_chat INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auto_replies (
                keyword TEXT PRIMARY KEY,
                response TEXT
            );
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS banned (
                user_id INTEGER PRIMARY KEY
            );
            """
        )
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in cur.fetchall()}
        migrations = [
            ("referred_by", "INTEGER DEFAULT 0"),
            ("referrals", "INTEGER DEFAULT 0"),
            ("last_seen", "TEXT"),
            ("vip", "INTEGER DEFAULT 0"),
        ]
        for col_name, col_def in migrations:
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass
        return conn


def load_from_db():
    global tracked_users, blocked_users, banned_users, user_join_dates, user_meta, saved_messages, button_forwards
    global welcome_enabled, animations_enabled, maintenance_mode, user_menu_text, support_username
    global force_channels, banner_config, click_stats, anim_style, auto_replies, ADMIN_IDS

    with sqlite3.connect(str(DB_PATH)) as conn:
        cur = conn.cursor()

        cur.execute("SELECT user_id FROM admins")
        for (uid,) in cur.fetchall():
            if uid not in ADMIN_IDS:
                ADMIN_IDS.append(uid)

        cur.execute("SELECT user_id FROM banned")
        for (uid,) in cur.fetchall():
            banned_users.add(uid)

        cur.execute(
            "SELECT user_id, access_hash, blocked, joined_date, referred_by, referrals, last_seen, vip FROM users"
        )
        for uid, hsh, blk, jdate, ref_by, refs, lseen, vip_flag in cur.fetchall():
            tracked_users[uid] = hsh
            if jdate:
                user_join_dates[uid] = jdate[:10]
            if blk:
                blocked_users.add(uid)
            user_meta[uid] = {
                "referred_by": ref_by or 0,
                "referrals": refs or 0,
                "last_seen": lseen or (jdate[:10] if jdate else "Unknown"),
                "vip": int(vip_flag or 0),
            }

        cur.execute("SELECT step, msg_type, text, msg_id, from_chat FROM messages")
        for step, mtype, text, mid, fchat in cur.fetchall():
            saved_messages[step] = {
                "type": mtype,
                "text": text,
                "msg_id": mid,
                "from_chat": fchat,
            }

        cur.execute("SELECT btn_key, msg_id, from_chat FROM button_msgs")
        button_forwards.clear()
        for key, mid, fchat in cur.fetchall():
            if key not in button_forwards:
                button_forwards[key] = []
            button_forwards[key].append({"msg_id": mid, "from_chat": fchat})

        cur.execute("SELECT key, value FROM settings")
        for k, v in cur.fetchall():
            if k == "welcome_enabled":
                welcome_enabled = v == "1"
            elif k == "animations_enabled":
                animations_enabled = v == "1"
            elif k == "maintenance_mode":
                maintenance_mode = v == "1"
            elif k == "user_menu_text":
                user_menu_text = v
            elif k == "support_username":
                support_username = v
            elif k == "anim_style":
                if v in ("royal_gold", "cyberpunk", "matrix", "quantum", "stealth"):
                    anim_style = v
            elif k == "force_channel":
                if v:
                    try:
                        parsed = json.loads(v)
                        if isinstance(parsed, list):
                            force_channels = [str(x).lstrip("@") for x in parsed if x]
                        else:
                            force_channels = [str(v).lstrip("@")]
                    except Exception:
                        force_channels = [
                            ch.strip().lstrip("@") for ch in v.split(",") if ch.strip()
                        ]
                else:
                    force_channels = []
            elif k == "banner_config":
                try:
                    banner_config = json.loads(v)
                except Exception:
                    pass
            elif k == "click_stats":
                try:
                    loaded_stats = json.loads(v)
                    click_stats.update(loaded_stats)
                except Exception:
                    pass

        cur.execute("SELECT keyword, response FROM auto_replies")
        for kw, resp in cur.fetchall():
            auto_replies[kw] = resp

    logger.info(
        f"Loaded {len(tracked_users)} users, {len(auto_replies)} auto-replies, {len(ADMIN_IDS)} admins."
    )


def save_user(uid: int, access_hash: int, blocked: bool = False):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    jdate = user_join_dates.get(uid) or now_str[:10]
    user_join_dates[uid] = jdate
    meta = user_meta.setdefault(
        uid, {"referred_by": 0, "referrals": 0, "last_seen": now_str, "vip": 0}
    )
    meta["last_seen"] = now_str
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO users 
               (user_id, access_hash, blocked, joined_date, referred_by, referrals, last_seen, vip) 
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                uid,
                access_hash,
                int(blocked),
                jdate,
                meta["referred_by"],
                meta["referrals"],
                meta["last_seen"],
                meta["vip"],
            ),
        )


def save_message_step(step: int, data: dict):
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO messages (step, msg_type, text, msg_id, from_chat) VALUES (?,?,?,?,?)",
            (
                step,
                data.get("type"),
                data.get("text"),
                data.get("msg_id"),
                data.get("from_chat"),
            ),
        )


def add_button_config(key: str, msg_id: int, from_chat: int):
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            "INSERT INTO button_msgs (btn_key, msg_id, from_chat) VALUES (?,?,?)",
            (key, msg_id, from_chat),
        )


def delete_button_config(key: str):
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("DELETE FROM button_msgs WHERE btn_key=?", (key,))


def set_setting(key: str, value: str):
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value)
        )


def increment_click(key: str):
    click_stats[key] = click_stats.get(key, 0) + 1
    set_setting("click_stats", json.dumps(click_stats))


def get_chat_id(reply_msg, event):
    if hasattr(reply_msg, "chat_id") and reply_msg.chat_id:
        return reply_msg.chat_id
    elif hasattr(reply_msg, "peer_id"):
        pid = reply_msg.peer_id
        if isinstance(pid, PeerUser):
            return pid.user_id
        elif isinstance(pid, PeerChannel):
            return pid.channel_id
    return event.chat_id


def get_growth_metrics():
    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    joined_today = sum(1 for d in user_join_dates.values() if d == today_str)
    joined_yesterday = sum(1 for d in user_join_dates.values() if d == yesterday_str)
    vip_count = sum(1 for m in user_meta.values() if m.get("vip"))
    return joined_today, joined_yesterday, vip_count


# ------------------ CLIENT ------------------
client = TelegramClient(
    StringSession(SESSION_STRING) if SESSION_STRING else "bot_session",
    API_ID,
    API_HASH,
)


# ------------------ GLASSMORPHISM LUXURY WEB DASHBOARD & API ------------------
async def web_handler(request):
    total_u = len(tracked_users)
    active_users = total_u - len(blocked_users)
    reach_pct = int((active_users / max(1, total_u)) * 100) if total_u else 100
    j_today, j_yest, vip_cnt = get_growth_metrics()
    total_clicks = sum(click_stats.values())
    hack_c = click_stats.get("hack", 0)
    pred_c = click_stats.get("prediction", 0)
    sup_c = click_stats.get("support", 0)
    status_label = "MAINTENANCE" if maintenance_mode else "OPERATIONAL"
    status_color = "#f59e0b" if maintenance_mode else "#10b981"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="15">
<title>PROBOT-X // ROYAL TELEMETRY</title>
<style>
  :root {{
    --bg: #05070d;
    --card: rgba(16, 22, 36, 0.78);
    --border: rgba(255, 255, 255, 0.08);
    --accent: #00f2fe;
    --gold: #fbbf24;
    --text: #f8fafc;
    --muted: #94a3b8;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: radial-gradient(circle at 15% 20%, #0f172a 0%, #05070d 75%);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 24px;
  }}
  .shell {{
    width: 100%;
    max-width: 780px;
    background: var(--card);
    backdrop-filter: blur(20px);
    border: 1px solid var(--border);
    border-radius: 24px;
    padding: 32px;
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.65), 0 0 40px rgba(0, 242, 254, 0.06);
  }}
  .top {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border);
    padding-bottom: 20px;
    margin-bottom: 24px;
    flex-wrap: wrap;
    gap: 12px;
  }}
  .brand {{ display: flex; align-items: center; gap: 12px; }}
  .brand-icon {{
    width: 44px; height: 44px; border-radius: 12px;
    background: linear-gradient(135deg, #00f2fe, #4facfe);
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; box-shadow: 0 0 20px rgba(0, 242, 254, 0.35);
  }}
  h1 {{ font-size: 20px; font-weight: 700; letter-spacing: 0.5px; }}
  .sub {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 1.2px; }}
  .pill {{
    display: inline-flex; align-items: center; gap: 8px;
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid {status_color}55;
    color: {status_color};
    padding: 6px 14px; border-radius: 999px; font-size: 12px; font-weight: 700;
    letter-spacing: 0.8px;
  }}
  .dot {{
    width: 8px; height: 8px; border-radius: 50%; background: {status_color};
    box-shadow: 0 0 10px {status_color};
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(165px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }}
  .kpi {{
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 18px;
  }}
  .kpi-label {{ font-size: 12px; color: var(--muted); margin-bottom: 8px; }}
  .kpi-val {{ font-size: 26px; font-weight: 800; color: #fff; }}
  .kpi-sub {{ font-size: 12px; color: var(--accent); margin-top: 4px; }}
  .bar-wrap {{
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 18px;
  }}
  .bar-head {{ display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 10px; }}
  .progress {{
    width: 100%; height: 10px; background: rgba(255, 255, 255, 0.07);
    border-radius: 999px; overflow: hidden;
  }}
  .fill {{
    width: {reach_pct}%; height: 100%;
    background: linear-gradient(90deg, #00f2fe, #4facfe);
    border-radius: 999px;
  }}
  .footer {{
    margin-top: 22px; display: flex; justify-content: space-between;
    font-size: 12px; color: var(--muted); flex-wrap: wrap; gap: 8px;
  }}
</style>
</head>
<body>
  <div class="shell">
    <div class="top">
      <div class="brand">
        <div class="brand-icon">👑</div>
        <div>
          <h1>PROBOT-X LUXURY TELEMETRY</h1>
          <div class="sub">@{bot_username_cache or 'VIP_BOT'} • Theme: {anim_style.upper()}</div>
        </div>
      </div>
      <div class="pill"><span class="dot"></span>{status_label}</div>
    </div>

    <div class="grid">
      <div class="kpi">
        <div class="kpi-label">TOTAL USERS</div>
        <div class="kpi-val">{total_u}</div>
        <div class="kpi-sub">+{j_today} joined today (Yest: +{j_yest})</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">ACTIVE REACHABLE</div>
        <div class="kpi-val">{active_users}</div>
        <div class="kpi-sub">{reach_pct}% delivery health</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">DIAMOND VIPs</div>
        <div class="kpi-val" style="color: var(--gold);">{vip_cnt}</div>
        <div class="kpi-sub">{len(ADMIN_IDS)} Active Admins</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">MODULE CLICKS</div>
        <div class="kpi-val">{total_clicks}</div>
        <div class="kpi-sub">⚡ {hack_c} | 📊 {pred_c} | 🎧 {sup_c}</div>
      </div>
    </div>

    <div class="bar-wrap">
      <div class="bar-head">
        <span><strong>Database Reachability Index</strong> ({active_users} active / {len(blocked_users)} blocked)</span>
        <span><strong>{reach_pct}%</strong></span>
      </div>
      <div class="progress"><div class="fill"></div></div>
    </div>

    <div class="footer">
      <span>⏱ Live Server Uptime: <strong>{get_uptime()}</strong></span>
      <span>🔄 Auto-refreshes every 15s • JSON API: <code>/health</code></span>
    </div>
  </div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def health_json_handler(request):
    return web.json_response(
        {
            "status": "maintenance" if maintenance_mode else "online",
            "uptime": get_uptime(),
            "total_users": len(tracked_users),
            "active_users": len(tracked_users) - len(blocked_users),
            "blocked_users": len(blocked_users),
            "banned_users": len(banned_users),
            "theme": anim_style,
            "clicks": click_stats,
        }
    )


async def start_web():
    app = web.Application()
    app.add_routes([web.get("/", web_handler), web.get("/health", health_json_handler)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Luxury Glassmorphism Web Telemetry Server running on port {PORT}")


# ------------------ DECORATORS & KEYBOARDS ------------------
def admin_only(func):
    async def wrapper(event):
        if event.sender_id not in ADMIN_IDS:
            await event.reply("🚫 `[Access Denied] Luxury Admin clearance required.`")
            return
        await func(event)

    return wrapper


def get_admin_keyboard():
    return [
        [Button.text("📊 Stats", resize=True), Button.text("⚙️ Status", resize=True)],
        [Button.text("📢 Broadcast", resize=True), Button.text("✉️ Send Message", resize=True)],
        [Button.text("🔘 Set Button", resize=True), Button.text("🗑 Clear Button", resize=True)],
        [Button.text("🔢 Set Sequence", resize=True), Button.text("🖼️ Menu & Banner", resize=True)],
        [Button.text("🔒 Force Join", resize=True), Button.text("🤖 Auto-Replies", resize=True)],
        [Button.text("👑 Manage Admins", resize=True), Button.text("🔍 Find User", resize=True)],
        [Button.text("🎬 Anim Theme", resize=True), Button.text("🛠 Maintenance", resize=True)],
        [Button.text("📁 Backup", resize=True), Button.text("🔄 Restore", resize=True)],
        [Button.text("🔇 Toggle Welcome", resize=True), Button.text("🧹 Cleanup", resize=True)],
    ]


def get_admin_inline_hub():
    """Interactive Luxury Glass Command Center inline buttons."""
    return [
        [
            Button.inline("📊 Live Analytics", data=b"adm_refresh_stats"),
            Button.inline("📢 Broadcast Hub", data=b"adm_open_bc"),
        ],
        [
            Button.inline("🎬 Theme Studio", data=b"adm_open_theme"),
            Button.inline("🖼️ Menu & Banner", data=b"adm_open_mb"),
        ],
        [
            Button.inline("🔒 Force Join", data=b"adm_open_fj"),
            Button.inline("🤖 Auto-Replies", data=b"adm_open_ar"),
        ],
        [
            Button.inline(
                f"🛠 Maintenance: {'🔴 ON' if maintenance_mode else '🟢 OFF'}",
                data=b"adm_toggle_maint_inline",
            ),
            Button.inline("👁 User Preview", data=b"adm_mb_preview"),
        ],
    ]


def build_admin_home_text() -> str:
    j_today, _, vip_cnt = get_growth_metrics()
    active_u = len(tracked_users) - len(blocked_users)
    return (
        f"{ui_header('ROYAL VIP ADMIN CONSOLE', 'ZERO-SLASH EXECUTIVE CONTROL v4.0')}\n\n"
        f"┏━━━ **📡 LIVE TELEMETRY** ━━━┓\n"
        f"┃ 🟢 **Uptime:** `{get_uptime()}`\n"
        f"┃ 👥 **Peers:** `{len(tracked_users)}` (`{active_u}` active | `+{j_today}` today)\n"
        f"┃ 💎 **VIP Members:** `{vip_cnt}`\n"
        f"┃ 🎨 **FX Theme:** `{anim_style.upper()}`\n"
        f"┃ 🔒 **Force Channels:** `{len(force_channels)} active`\n"
        f"┃ 🛠 **Maintenance:** `{'🔴 ACTIVE' if maintenance_mode else '🟢 NOMINAL'}`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"✨ *Tap any quick-action module below or use your bottom command deck:*"
    )


# ------------------ MULTI-CHANNEL FORCE JOIN CHECKER ------------------
async def get_unjoined_channels(uid: int) -> list[str]:
    if not force_channels or uid in ADMIN_IDS:
        return []
    missing = []
    for ch in force_channels:
        clean_ch = ch.lstrip("@")
        try:
            await client(GetParticipantRequest(channel=clean_ch, participant=uid))
        except UserNotParticipantError:
            missing.append(clean_ch)
        except Exception as e:
            logger.warning(f"Force join check error (@{clean_ch}): {e}")
    return missing


async def is_user_joined(uid: int) -> bool:
    missing = await get_unjoined_channels(uid)
    return len(missing) == 0


async def send_force_join_prompt(event, key: str):
    missing = await get_unjoined_channels(event.sender_id)
    if not missing:
        return await send_button_forward(event, key)

    btns = []
    status_lines = []
    for idx, ch in enumerate(force_channels, start=1):
        clean_ch = ch.lstrip("@")
        is_missing = clean_ch in missing
        mark = "🔴 Locked" if is_missing else "🟢 Cleared"
        status_lines.append(f"┃ `0{idx}.` **@{clean_ch}** ━ `{mark}`")
        if is_missing:
            btns.append(
                [
                    Button.url(
                        f"✨ Join VIP Channel #{idx} (@{clean_ch})",
                        f"https://t.me/{clean_ch}",
                    )
                ]
            )

    btns.append(
        [Button.inline("🔓 Verify & Unlock VIP Access", data=f"usr_verify_{key}".encode())]
    )
    joined_count = len(force_channels) - len(missing)
    pct = int((joined_count / max(1, len(force_channels))) * 100)

    msg_text = (
        f"{ui_header('VIP SECURITY GATEWAY', 'MEMBERSHIP VERIFICATION REQUIRED')}\n\n"
        f"┏━━━ **🔐 CLEARANCEPROGRESS** ━━━┓\n"
        f"┃ `{make_bar(pct, style='gold')} {pct}%`\n"
        + "\n".join(status_lines)
        + "\n┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "👉 *Join the official VIP channel(s) above, then tap **Verify & Unlock VIP Access** for instant delivery!*"
    )
    await event.reply(msg_text, buttons=btns)


@client.on(events.CallbackQuery(pattern=b"^usr_verify_(hack|prediction)$"))
async def user_verify_force_join(event):
    key = event.pattern_match.group(1).decode("utf-8")
    missing = await get_unjoined_channels(event.sender_id)
    if missing:
        return await event.answer(
            f"⚠️ Verification Failed! Please join the remaining {len(missing)} VIP channel(s) first.",
            alert=True,
        )
    await event.answer("✨ VIP Clearance Verified! Unlocking package...")
    try:
        await event.delete()
    except Exception:
        pass
    await send_button_forward(event, key, is_callback=True)


# ------------------ ADMIN ALERTS (WITH 1-CLICK LUXURY BUTTONS) ------------------
async def notify_admins_new_user(user, referred_by: int = 0):
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    safe_name = (
        full_name.replace("[", "")
        .replace("]", "")
        .replace("*", "")
        .replace("_", "")
        .replace("`", "")
    )
    if not safe_name.strip():
        safe_name = "Unknown User"

    linked_name = f"[{safe_name}](tg://user?id={user.id})"
    username_display = f"@{user.username}" if user.username else "❌ `No Handle`"
    ref_line = f"┃ 🎁 **Referred By:** `{referred_by}`\n" if referred_by else ""

    text = (
        f"{ui_header('NEW VIP PEER DETECTED', 'REAL-TIME ONBOARDING ALERT')}\n\n"
        f"┏━━━ **👤 USER IDENTITY** ━━━┓\n"
        f"┃ 🏷 **Name:** {linked_name}\n"
        f"┃ 🔗 **Handle:** {username_display}\n"
        f"┃ 🆔 **UID:** `{user.id}`\n"
        f"{ref_line}"
        f"┃ 📊 **Database Total:** `{len(tracked_users)}` peers\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━┛"
    )
    btns = [
        [
            Button.inline("✉️ Quick DM", data=f"adm_quickdm_{user.id}".encode()),
            Button.inline("🕵️ Dossier", data=f"adm_dossier_{user.id}".encode()),
            Button.inline("🚫 Ban", data=f"adm_quickban_{user.id}".encode()),
        ]
    ]
    for admin_id in ADMIN_IDS:
        try:
            await client.send_message(admin_id, text, buttons=btns)
        except Exception:
            pass


# ------------------ WELCOME SYSTEM & KEYBOARD MENU ------------------
async def remove_welcome_cooldown(uid):
    await asyncio.sleep(30)
    recently_welcomed.discard(uid)


async def send_user_menu(entity):
    # 🔥 EXACT 3 REPLY KEYBOARD BUTTONS PRESERVED AS REQUESTED 🔥
    btns = [
        [Button.text("⚡️ I Want Number HACK", resize=True)],
        [Button.text("📊 How To Start COLOUR TRADING", resize=True)],
        [Button.text("🎧 Contact Support", resize=True)],
    ]
    try:
        safe_text = user_menu_text or "👇"
        if banner_config.get("msg_id") and banner_config.get("chat_id"):
            try:
                b_msg = await client.get_messages(
                    banner_config["chat_id"], ids=banner_config["msg_id"]
                )
                if b_msg and b_msg.media:
                    await client.send_file(
                        entity, b_msg.media, caption=safe_text, buttons=btns
                    )
                    return
            except Exception as banner_err:
                logger.warning(f"Banner load failed, falling back to text: {banner_err}")

        await client.send_message(entity, safe_text, buttons=btns)
    except Exception as e:
        logger.error(f"Menu error: {e}")


async def send_welcome_sequence(user, ref_id: int = 0):
    uid = user.id
    if uid in recently_welcomed or uid in banned_users:
        return
    recently_welcomed.add(uid)

    if getattr(user, "is_bot", False):
        return

    try:
        full_user = await client.get_input_entity(uid)
        if not isinstance(full_user, InputPeerUser):
            return
        access_hash = full_user.access_hash
    except Exception:
        return

    is_new_user = uid not in tracked_users
    tracked_users[uid] = access_hash

    valid_ref = 0
    if is_new_user and ref_id and ref_id != uid and ref_id in tracked_users:
        valid_ref = ref_id
        ref_meta = user_meta.setdefault(
            ref_id, {"referred_by": 0, "referrals": 0, "last_seen": "Unknown", "vip": 0}
        )
        ref_meta["referrals"] = ref_meta.get("referrals", 0) + 1
        if ref_meta["referrals"] >= 5:
            ref_meta["vip"] = 1
        save_user(ref_id, tracked_users[ref_id], blocked=(ref_id in blocked_users))
        try:
            await client.send_message(
                ref_id,
                f"{ui_header('NEW REFERRAL REWARD', 'VIP INVITE ENGINE')}\n\n"
                f"🎉 **A new member joined via your personal invite link!**\n"
                f"🏆 **Total Invites:** `{ref_meta['referrals']}`\n"
                f"💎 **VIP Status:** `{'👑 DIAMOND VIP UNLOCKED' if ref_meta['vip'] else str(ref_meta['referrals']) + '/5 Invites'}`",
            )
        except Exception:
            pass

    if uid not in user_meta:
        user_meta[uid] = {
            "referred_by": valid_ref,
            "referrals": 0,
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "vip": 0,
        }

    save_user(uid, access_hash, blocked=False)
    blocked_users.discard(uid)

    if is_new_user and uid not in ADMIN_IDS:
        asyncio.create_task(notify_admins_new_user(user, referred_by=valid_ref))

    if not welcome_enabled or uid in ADMIN_IDS:
        asyncio.create_task(remove_welcome_cooldown(uid))
        return

    for step in sorted(saved_messages.keys()):
        item = saved_messages[step]
        try:
            if item["type"] == "forward":
                try:
                    await client.get_messages(item["from_chat"], ids=item["msg_id"])
                except Exception:
                    continue
                await client.forward_messages(
                    full_user, item["msg_id"], item["from_chat"]
                )
            else:
                await client.send_message(full_user, item["text"])
            await asyncio.sleep(0.5)
        except UserIsBlockedError:
            blocked_users.add(uid)
            save_user(uid, access_hash, blocked=True)
            return
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
        except Exception:
            continue

    asyncio.create_task(remove_welcome_cooldown(uid))


@client.on(events.ChatAction())
async def chat_action(event):
    if event.user_joined or event.user_added:
        user = await event.get_user()
        if user and user.id not in banned_users:
            await send_welcome_sequence(user)
            if user.id not in ADMIN_IDS:
                await send_user_menu(user)


@client.on(events.Raw(types=UpdateBotChatInviteRequester))
async def join_request(event):
    try:
        if event.user_id in banned_users:
            return
        user = await client.get_entity(event.user_id)
        await send_welcome_sequence(user)
        if event.user_id not in ADMIN_IDS:
            await send_user_menu(user)
    except Exception:
        pass


# ------------------ START COMMAND, REFERRAL & VIP PROFILE ------------------
@client.on(events.NewMessage(pattern=r"(?i)^(/start(?:\s+(.+))?|panel|menu|admin)$"))
async def start(event):
    if event.sender_id in banned_users:
        return await event.reply(
            "🚫 **Access Revoked:** Your account has been restricted from using this service."
        )

    raw_cmd = event.raw_text.strip()
    cmd_lower = raw_cmd.lower()
    if cmd_lower in ("panel", "menu", "admin") and event.sender_id not in ADMIN_IDS:
        return

    if maintenance_mode and event.sender_id not in ADMIN_IDS:
        return await event.reply(
            f"{ui_header('VIP SYSTEM UPGRADE', 'SCHEDULED MAINTENANCE')}\n\n"
            "⚡ Our core servers and AI prediction nodes are currently undergoing a scheduled luxury upgrade.\n"
            "⏳ *Please check back in a few minutes!*"
        )

    ref_id = 0
    arg_match = event.pattern_match.group(2)
    if arg_match and arg_match.startswith("ref_"):
        ref_str = arg_match.replace("ref_", "").strip()
        if ref_str.isdigit():
            ref_id = int(ref_str)

    user_chat_state[event.sender_id] = False
    admin_chat_state.pop(event.sender_id, None)

    if event.sender_id in blocked_users:
        blocked_users.discard(event.sender_id)
        access_hash = tracked_users.get(event.sender_id, 0)
        save_user(event.sender_id, access_hash, blocked=False)

    if event.sender_id in ADMIN_IDS:
        boot_frames = [
            (
                "╭━━━✦ **👑 EXECUTIVE AUTH** ✦━━━╮\n"
                "┆ 🔐 `Verifying Root Credentials...`\n"
                "┆ `▰▰▰▰▱▱▱▱▱▱ 42%`\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
                0.24,
            ),
            (
                "╭━━━✦ **👑 EXECUTIVE AUTH** ✦━━━╮\n"
                "┆ ✨ `Mounting Luxury Command Deck...`\n"
                "┆ `▰▰▰▰▰▰▰▰▰▰ 100%`\n"
                "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
                0.24,
            ),
        ]
        boot_msg = await play_animation(event, boot_frames)
        try:
            await boot_msg.delete()
        except Exception:
            pass

        # Send reply keyboard + interactive inline glass dashboard
        await event.respond(
            "⌨️ *Executive Reply Keyboard Mounted.*", buttons=get_admin_keyboard()
        )
        await event.respond(
            build_admin_home_text(), buttons=get_admin_inline_hub()
        )
    else:
        user = await event.get_sender()
        if user:
            await send_welcome_sequence(user, ref_id=ref_id)
            await send_user_menu(user)


def build_vip_lounge_card(uid: int) -> tuple[str, list]:
    meta = user_meta.get(
        uid, {"referred_by": 0, "referrals": 0, "last_seen": "Today", "vip": 0}
    )
    refs = meta.get("referrals", 0)
    is_vip = bool(meta.get("vip")) or refs >= 5
    bot_uname = bot_username_cache or "bot"
    ref_link = f"https://t.me/{bot_uname}?start=ref_{uid}"
    pct = min(100, int((refs / 5) * 100))

    share_text = quote(
        "🔥 Join this VIP Hack & Colour Trading Prediction Bot for instant winning signals!"
    )
    share_url = f"https://t.me/share/url?url={quote(ref_link)}&text={share_text}"

    text = (
        f"{ui_header('ROYAL VIP LOUNGE', 'PERSONAL MEMBERSHIP CARD')}\n\n"
        f"┏━━━ **🪪 MEMBER CREDENTIALS** ━━━┓\n"
        f"┃ 🆔 **Account ID:** `{uid}`\n"
        f"┃ 🎖 **Tier Status:** `{'👑 DIAMOND VIP' if is_vip else '🔹 STANDARD MEMBER'}`\n"
        f"┃ 📅 **Joined On:** `{user_join_dates.get(uid, 'Today')}`\n"
        f"┃ 👥 **Direct Invites:** `{refs} / 5 Friends`\n"
        f"┃ 📊 **VIP Unlock:** `{make_bar(pct, style='gold')} {pct}%`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"🔗 **Your Exclusive Referral Link:**\n`{ref_link}`\n\n"
        f"🎁 *Invite 5 friends using the button below to unlock **👑 DIAMOND VIP** priority access & instant support!*"
    )
    btns = [
        [Button.url("🚀 Share Invite Link with Friends", share_url)],
        [Button.inline("🏆 Top VIP Leaderboard", data=b"usr_vip_leaderboard")],
    ]
    return text, btns


@client.on(events.NewMessage(pattern=r"(?i)^(/vip|/profile|/myid|/invite)$"))
async def user_vip_profile_cmd(event):
    uid = event.sender_id
    if uid in banned_users:
        return
    increment_click("vip_profile")
    text, btns = build_vip_lounge_card(uid)
    await event.reply(text, buttons=btns)


@client.on(events.CallbackQuery(pattern=b"^usr_vip_leaderboard$"))
async def usr_vip_leaderboard_cb(event):
    await event.answer("🏆 Loading Top Inviters...")
    ranked = sorted(
        user_meta.items(), key=lambda x: x[1].get("referrals", 0), reverse=True
    )[:5]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = []
    for idx, (u_id, m_data) in enumerate(ranked):
        r_cnt = m_data.get("referrals", 0)
        if r_cnt > 0:
            masked = f"{str(u_id)[:4]}•••{str(u_id)[-2:]}"
            lines.append(
                f"┃ {medals[idx]} **User `{masked}`** — `{r_cnt} Invites` {'👑' if m_data.get('vip') else ''}"
            )
    board_body = (
        "\n".join(lines)
        if lines
        else "┃ *No referrals recorded yet. Be the #1 Top Inviter!*"
    )
    text = (
        f"{ui_header('VIP HALL OF FAME', 'TOP REFERRAL LEADERBOARD')}\n\n"
        f"┏━━━ **🏆 TOP 5 INVITERS** ━━━┓\n"
        f"{board_body}\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"💎 *Reach 5 invites to claim your automatic Crown!*"
    )
    btns = [[Button.inline("🔙 Back to My VIP Card", data=b"usr_vip_back")]]
    try:
        await event.edit(text, buttons=btns)
    except Exception:
        pass


@client.on(events.CallbackQuery(pattern=b"^usr_vip_back$"))
async def usr_vip_back_cb(event):
    await event.answer()
    text, btns = build_vip_lounge_card(event.sender_id)
    try:
        await event.edit(text, buttons=btns)
    except Exception:
        pass


# ------------------ USER KEYBOARD BUTTON HANDLERS & ANIMATIONS ------------------
@client.on(
    events.NewMessage(
        func=lambda e: e.is_private and e.text and "number hack" in e.text.lower()
    )
)
async def hack_button_handler(event):
    if event.sender_id in banned_users or check_rate_limit(event.sender_id):
        return
    if maintenance_mode and event.sender_id not in ADMIN_IDS:
        return await event.reply(
            "🛠 **System is currently undergoing VIP Maintenance. Please try again shortly!**"
        )
    increment_click("hack")
    if not await is_user_joined(event.sender_id):
        return await send_force_join_prompt(event, "hack")
    await send_button_forward(event, "hack")


@client.on(
    events.NewMessage(
        func=lambda e: e.is_private and e.text and "colour trading" in e.text.lower()
    )
)
async def prediction_button_handler(event):
    if event.sender_id in banned_users or check_rate_limit(event.sender_id):
        return
    if maintenance_mode and event.sender_id not in ADMIN_IDS:
        return await event.reply(
            "🛠 **System is currently undergoing VIP Maintenance. Please try again shortly!**"
        )
    increment_click("prediction")
    if not await is_user_joined(event.sender_id):
        return await send_force_join_prompt(event, "prediction")
    await send_button_forward(event, "prediction")


@client.on(
    events.NewMessage(
        func=lambda e: e.is_private and e.text and "contact support" in e.text.lower()
    )
)
async def contact_admin_handler(event):
    if (
        event.sender_id in banned_users
        or event.sender_id in ADMIN_IDS
        or check_rate_limit(event.sender_id)
    ):
        return
    increment_click("support")
    user_chat_state[event.sender_id] = True

    sup_frames = [
        (
            "╭━━━✦ **🎧 VIP CONCIERGE** ✦━━━╮\n"
            "┆ 🔐 `Opening 256-Bit Encrypted Line...`\n"
            "┆ `▰▰▰▱▱▱▱▱▱▱ 32%`\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
            0.3,
        ),
        (
            "╭━━━✦ **🎧 VIP CONCIERGE** ✦━━━╮\n"
            "┆ 📡 `Routing to Executive Support Desk...`\n"
            "┆ `▰▰▰▰▰▰▰▰▱▱ 78%`\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
            0.3,
        ),
        (
            "╭━━━✦ **🎧 VIP CONCIERGE** ✦━━━╮\n"
            "┆ 🟢 `Secure Tunnel Connected (100%)`\n"
            "┆ `▰▰▰▰▰▰▰▰▰▰ 100%`\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
            0.28,
        ),
    ]
    anim_msg = await play_animation(event, sup_frames, use_reply=True)
    try:
        await anim_msg.delete()
    except Exception:
        pass

    end_chat_btn = [
        [Button.inline("💎 View My VIP Card", data=b"usr_vip_back")],
        [Button.inline("🔒 Close Support Session", data=b"usr_end_support")],
    ]
    await event.reply(
        f"{ui_header('VIP CONCIERGE DESK', 'LIVE 2-WAY ENCRYPTED CHAT')}\n\n"
        f"👤 **Direct Admin Handle:** {support_username}\n"
        f"🟢 **Line Status:** `CONNECTED & READY`\n"
        f"{ui_divider()}\n"
        f"✍️ *Aap yahan niche seedha apna message, photo ya screenshot bhej sakte hain, wo direct Admin ko deliver ho jayega!*",
        buttons=end_chat_btn,
    )


@client.on(events.CallbackQuery(pattern=b"^usr_end_support$"))
async def user_end_support_cb(event):
    user_chat_state[event.sender_id] = False
    await event.answer("🔒 Support tunnel closed.")
    try:
        await event.edit(
            f"{ui_header('SESSION TERMINATED', 'VIP CONCIERGE DESK')}\n\n"
            "🔒 **Your support chat session has been closed.**\n"
            "👉 *Tap **🎧 Contact Support** on your keyboard anytime to reconnect.*"
        )
    except Exception:
        pass


async def send_button_forward(event, key, is_callback: bool = False):
    uid = event.sender_id
    config_list = button_forwards.get(key)

    if not config_list:
        msg_txt = (
            f"{ui_header('MODULE STANDBY', 'VIP VAULT NOTICE')}\n\n"
            "⚠️ *This VIP package is currently being updated by the administrator. Please check back shortly!*"
        )
        if is_callback:
            await event.respond(msg_txt)
        else:
            await event.reply(msg_txt)
        return

    theme_pack = ANIM_THEMES.get(anim_style, ANIM_THEMES["royal_gold"])
    if key in theme_pack:
        status_msg = await play_animation(
            event, theme_pack[key], use_reply=not is_callback
        )
    else:
        status_msg = await (
            event.respond("⏳ `Preparing VIP package...`")
            if is_callback
            else event.reply("⏳ `Preparing VIP package...`")
        )

    try:
        sent_count = 0
        for config in config_list:
            admin_id = config["from_chat"]
            admin_hash = tracked_users.get(admin_id, 0)
            from_peer = (
                InputPeerUser(admin_id, admin_hash)
                if (admin_id > 0 and admin_hash)
                else admin_id
            )
            try:
                await client.forward_messages(uid, config["msg_id"], from_peer)
                sent_count += 1
            except Exception as inner_e:
                logger.warning(
                    f"Could not forward msg {config['msg_id']} for {uid}: {inner_e}"
                )
            await asyncio.sleep(0.3)

        if sent_count == 0:
            await status_msg.edit(
                "❌ `[Error] Configured VIP files are unavailable or deleted.`"
            )
        else:
            await asyncio.sleep(0.6)
            await status_msg.delete()

    except UserIsBlockedError:
        blocked_users.add(uid)
        save_user(uid, tracked_users.get(uid, 0), blocked=True)
    except FloodWaitError as e:
        await status_msg.edit(
            f"⏳ High server traffic! Please wait `{e.seconds}` seconds."
        )
    except Exception as e:
        logger.error(f"Button {key} error for {uid}: {e}")
        await status_msg.edit("❌ An unexpected error occurred. Please try again.")


# =====================================================================
# 👑 ZERO-SLASH LUXURY ADMIN KEYBOARD & INLINE HUB HANDLERS
# =====================================================================


def build_stats_payload() -> tuple[str, list]:
    hack_msgs = len(button_forwards.get("hack", []))
    pred_msgs = len(button_forwards.get("prediction", []))
    total_u = len(tracked_users)
    active_count = total_u - len(blocked_users)
    health_pct = int((active_count / max(1, total_u)) * 100) if total_u else 100
    j_today, j_yest, vip_cnt = get_growth_metrics()

    banner_status = "🟢 Active" if banner_config.get("msg_id") else "🔴 None"
    force_status = (
        f"🟢 {len(force_channels)} Ch" if force_channels else "🔴 OFF"
    )
    total_clicks = sum(click_stats.values())

    btns = [
        [Button.inline("🔄 Refresh Live Telemetry", data=b"adm_refresh_stats")],
        HOME_BACK_ROW,
    ]

    msg = (
        f"{ui_header('EXECUTIVE ANALYTICS', 'REAL-TIME TELEMETRY & METRICS')}\n\n"
        f"┏━━━ **👥 AUDIENCE & HEALTH** ━━━┓\n"
        f"┃ ⏱ **Uptime:** `{get_uptime()}`\n"
        f"┃ 👥 **Total Peers:** `{total_u}` *(🟢 `{active_count}` Active)*\n"
        f"┃ 🔋 **Health:** `{make_bar(health_pct, style='gold')} {health_pct}%`\n"
        f"┃ 📈 **Growth:** `+{j_today} Today` • `+{j_yest} Yest`\n"
        f"┃ 💎 **Diamond VIPs:** `{vip_cnt}` • 👑 **Admins:** `{len(ADMIN_IDS)}`\n"
        f"┃ 🚫 **Blocked:** `{len(blocked_users)}` • **Banned:** `{len(banned_users)}`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"┏━━━ **🎯 MODULE ENGAGEMENT ({total_clicks})** ━━━┓\n"
        f"┃ ⚡ **Number Hack:** `{click_stats.get('hack', 0)}` clicks\n"
        f"┃ 📊 **Colour Trading:** `{click_stats.get('prediction', 0)}` clicks\n"
        f"┃ 🎧 **Support Desk:** `{click_stats.get('support', 0)}` sessions\n"
        f"┃ 💎 **VIP Lounge:** `{click_stats.get('vip_profile', 0)}` views\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"┏━━━ **⚙️ ENGINE CONFIG** ━━━┓\n"
        f"┃ 🔊 **Welcome:** `{'🟢 ON' if welcome_enabled else '🔴 OFF'}` (`{len(saved_messages)}` steps)\n"
        f"┃ 🎬 **Theme:** `{anim_style.upper()}`\n"
        f"┃ 🛠 **Maint Mode:** `{'🔴 ON' if maintenance_mode else '🟢 OFF'}`\n"
        f"┃ 🖼️ **Banner:** `{banner_status}` • 🔒 **Force:** `{force_status}`\n"
        f"┃ 📁 **Vault:** Hack (`{hack_msgs}`) • Trading (`{pred_msgs}`)\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛"
    )
    return msg, btns


@client.on(events.NewMessage(pattern=r"^(/stats|📊 Stats)$"))
@admin_only
async def stats_btn_handler(event):
    admin_chat_state.pop(event.sender_id, None)
    scan_frames = [
        ("📡 `[TELEMETRY] Querying SQLite Nodes & Click Metrics...`\n`▰▰▰▰▱▱▱▱▱▱ 40%`", 0.25),
        ("📊 `[TELEMETRY] Compiling Executive Report...`\n`▰▰▰▰▰▰▰▰▰▱ 92%`", 0.25),
    ]
    scan_msg = await play_animation(event, scan_frames)
    msg, btns = build_stats_payload()
    await scan_msg.edit(msg, buttons=btns)


@client.on(events.NewMessage(pattern=r"^(/status|⚙️ Status)$"))
@admin_only
async def status_btn_handler(event):
    admin_chat_state.pop(event.sender_id, None)
    t0 = time.perf_counter()
    diag_frames = [
        ("⚙️ `[DIAGNOSTICS] Pinging Telegram MTProto Data Centers...`", 0.24),
        ("🟢 `[DIAGNOSTICS] Measuring SQLite & Event Loop Latency...`", 0.24),
    ]
    diag_msg = await play_animation(event, diag_frames)
    ping_ms = (time.perf_counter() - t0) * 1000
    db_size_kb = (
        os.path.getsize(DB_PATH) / 1024 if os.path.exists(DB_PATH) else 0.0
    )

    steps = "\n".join(
        f"┃  • **Step {s}:** `{d['type'].upper()}`"
        for s, d in sorted(saved_messages.items())
    )
    await diag_msg.edit(
        f"{ui_header('SYSTEM DIAGNOSTICS', 'MTPROTO & DATABASE HEALTH')}\n\n"
        f"┏━━━ **⚡ CORE METRICS** ━━━┓\n"
        f"┃ 🟢 **State:** `{'🛠 MAINTENANCE' if maintenance_mode else 'OPTIMAL (100%)'}`\n"
        f"┃ ⚡ **Loop Latency:** `{ping_ms:.1f} ms`\n"
        f"┃ 💾 **SQLite Footprint:** `{db_size_kb:.1f} KB`\n"
        f"┃ ⏱ **Uptime:** `{get_uptime()}`\n"
        f"┃ 🤖 **Auto-Replies:** `{len(auto_replies)}` rules\n"
        f"┃ 🎬 **FX Engine:** `{anim_style.upper()}`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"┏━━━ **🔢 WELCOME PIPELINE** ━━━┓\n"
        f"{steps if steps else '┃  • *No welcome steps configured*'}\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━┛",
        buttons=[HOME_BACK_ROW],
    )


def build_theme_studio_payload() -> tuple[str, list]:
    btns = [
        [
            Button.inline(
                f"{'👑 ' if anim_style == 'royal_gold' else ''}Royal Gold (Luxury)",
                data=b"adm_theme_royal_gold",
            )
        ],
        [
            Button.inline(
                f"{'✅ ' if anim_style == 'cyberpunk' else ''}⚡ Cyberpunk",
                data=b"adm_theme_cyberpunk",
            ),
            Button.inline(
                f"{'✅ ' if anim_style == 'matrix' else ''}🟢 Matrix Code",
                data=b"adm_theme_matrix",
            ),
        ],
        [
            Button.inline(
                f"{'✅ ' if anim_style == 'quantum' else ''}⚛️ Quantum AI",
                data=b"adm_theme_quantum",
            ),
            Button.inline(
                f"{'✅ ' if anim_style == 'stealth' else ''}👻 Stealth (Instant)",
                data=b"adm_theme_stealth",
            ),
        ],
        HOME_BACK_ROW,
    ]
    text = (
        f"{ui_header('FX ANIMATION STUDIO', 'VISUAL MOTION PRESETS')}\n\n"
        f"🎨 **Active Motion Theme:** `{anim_style.upper()}`\n"
        f"{ui_divider()}\n"
        f"• **👑 Royal Gold:** Framed luxury cards with `▰▱` gold progress bars.\n"
        f"• **⚡ Cyberpunk:** High-tech terminal decryption & progress blocks.\n"
        f"• **🟢 Matrix Code:** Binary stream & mainframe override visuals.\n"
        f"• **⚛️ Quantum AI:** Entanglement & neural convergence FX.\n"
        f"• **👻 Stealth:** Zero delay — instant package forwarding.\n\n"
        f"👇 *Select a preset to apply globally across all user buttons:*"
    )
    return text, btns


@client.on(events.NewMessage(pattern=r"^🎬 Anim Theme$"))
@admin_only
async def anim_theme_menu_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    text, btns = build_theme_studio_payload()
    await event.reply(text, buttons=btns)


@client.on(events.NewMessage(pattern=r"^🛠 Maintenance$"))
@admin_only
async def maintenance_toggle_btn(event):
    global maintenance_mode
    admin_chat_state.pop(event.sender_id, None)
    maintenance_mode = not maintenance_mode
    set_setting("maintenance_mode", "1" if maintenance_mode else "0")
    status_str = (
        "🔴 ENABLED (Users Paused)" if maintenance_mode else "🟢 DISABLED (Bot Live)"
    )
    await event.reply(
        f"{ui_header('MAINTENANCE GATE', 'SYSTEM ACCESS CONTROL')}\n\n"
        f"📡 **Current Mode:** **{status_str}**",
        buttons=[HOME_BACK_ROW],
    )


@client.on(events.NewMessage(pattern=r"^(/togglewelcome|🔇 Toggle Welcome)$"))
@admin_only
async def toggle_welcome_btn(event):
    global welcome_enabled
    admin_chat_state.pop(event.sender_id, None)
    welcome_enabled = not welcome_enabled
    set_setting("welcome_enabled", "1" if welcome_enabled else "0")
    await event.reply(
        f"🔊 **Welcome Sequence Protocol:** `{'🟢 ENABLED' if welcome_enabled else '🔴 DISABLED'}`",
        buttons=[HOME_BACK_ROW],
    )


@client.on(events.NewMessage(pattern=r"^(/cleanup|🧹 Cleanup)$"))
@admin_only
async def cleanup_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    clean_frames = [
        ("🧹 `[VACUUM] Scanning database for dead/blocked accounts...`", 0.3),
        ("🗑️ `[PURGE] Wiping unreachable peers & optimizing SQLite...`", 0.3),
    ]
    c_msg = await play_animation(event, clean_frames)

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("DELETE FROM users WHERE blocked=1")
    removed = len(blocked_users)
    for uid in list(blocked_users):
        tracked_users.pop(uid, None)
    blocked_users.clear()
    await c_msg.edit(
        f"{ui_header('DATABASE OPTIMIZED', 'SQLITE VACUUM COMPLETE')}\n\n"
        f"🗑 **Purged Dead Peers:** `{removed}`\n"
        f"👥 **Active Clean Peers:** `{len(tracked_users)}`",
        buttons=[HOME_BACK_ROW],
    )


@client.on(events.NewMessage(pattern=r"^(/backup|📁 Backup)$"))
@admin_only
async def backup_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    b_frames = [
        ("🔐 `[BACKUP] Serializing user hashes, referrals & settings...`", 0.28),
        ("📦 `[EXPORT] Compressing JSON archive & verifying integrity...`", 0.28),
    ]
    b_msg = await play_animation(event, b_frames)

    db_admins = [a for a in ADMIN_IDS if a not in ROOT_ADMINS]
    data = {
        "tracked": tracked_users,
        "blocked": list(blocked_users),
        "banned": list(banned_users),
        "join_dates": user_join_dates,
        "user_meta": {str(k): v for k, v in user_meta.items()},
        "messages": {str(k): v for k, v in saved_messages.items()},
        "button_forwards": button_forwards,
        "welcome": welcome_enabled,
        "animations_enabled": animations_enabled,
        "maintenance_mode": maintenance_mode,
        "anim_style": anim_style,
        "user_menu_text": user_menu_text,
        "support_username": support_username,
        "force_channel": json.dumps(force_channels),
        "banner_config": banner_config,
        "click_stats": click_stats,
        "auto_replies": auto_replies,
        "db_admins": db_admins,
    }
    file = "backup.json"
    with open(file, "w") as f:
        json.dump(data, f)
    try:
        await b_msg.delete()
    except Exception:
        pass
    await client.send_file(
        event.chat_id,
        file,
        caption=(
            f"📁 **PROBOT-X MASTER BACKUP**\n"
            f"👥 **Total Peers:** `{len(tracked_users)}` | ⏱ **Uptime:** `{get_uptime()}`"
        ),
    )
    os.remove(file)


# --- 🔍 FIND USER (VIP DOSSIER) ---
@client.on(events.NewMessage(pattern=r"^🔍 Find User$"))
@admin_only
async def find_user_btn(event):
    admin_id = event.sender_id
    await event.reply(
        f"{ui_header('VIP USER INSPECTOR', 'DEEP DOSSIER LOOKUP')}\n\n"
        "👉 **Send the target user's Numeric Telegram UID below:**",
        buttons=CANCEL_BTN,
    )
    admin_chat_state[admin_id] = {"step": "inspect_user_id"}


# --- 1. INTERACTIVE BROADCAST MENU ---
def build_broadcast_hub_payload() -> tuple[str, list]:
    active_targets = len(tracked_users) - len(blocked_users)
    btns = [
        [Button.inline("📨 Standard Broadcast (Live Radar)", data=b"adm_bc_normal")],
        [Button.inline("📌 Broadcast + Auto-Pin Message", data=b"adm_bc_pin")],
        [Button.inline("⏰ Scheduled Timer Broadcast", data=b"adm_bc_sched")],
        HOME_BACK_ROW,
    ]
    text = (
        f"{ui_header('VIP BROADCAST ENGINE', 'MASS TRANSMISSION SUITE v4.0')}\n\n"
        f"┏━━━ **📡 TARGET TELEMETRY** ━━━┓\n"
        f"┃ 👥 **Total Database:** `{len(tracked_users)}` peers\n"
        f"┃ 🟢 **Reachable Targets:** `{active_targets}` peers\n"
        f"┃ ⚡ **Radar Refresh Rate:** `Every 3 Users`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"👇 *Select your transmission mode below:*"
    )
    return text, btns


@client.on(events.NewMessage(pattern=r"^📢 Broadcast$"))
@admin_only
async def broadcast_menu_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    text, btns = build_broadcast_hub_payload()
    await event.reply(text, buttons=btns)


# --- 2. INTERACTIVE SEND DM ---
@client.on(events.NewMessage(pattern=r"^✉️ Send Message$"))
@admin_only
async def send_dm_btn(event):
    admin_id = event.sender_id
    prompt = await event.reply(
        f"{ui_header('DIRECT VIP MESSAGING', '1-ON-1 ENCRYPTED DISPATCH')}\n\n"
        "👉 **Type and send the target user's Numeric UID:**",
        buttons=CANCEL_BTN,
    )
    admin_chat_state[admin_id] = {
        "step": "waiting_for_id",
        "target_id": None,
        "prompt_id": prompt.id,
    }


# --- 3. INTERACTIVE SET BUTTON MENU ---
@client.on(events.NewMessage(pattern=r"^🔘 Set Button$"))
@admin_only
async def set_button_menu_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    hack_cnt = len(button_forwards.get("hack", []))
    pred_cnt = len(button_forwards.get("prediction", []))
    btns = [
        [
            Button.inline("⚡ Replace Hack", data=b"adm_sbtn_rep_hack"),
            Button.inline(f"➕ Append Hack ({hack_cnt})", data=b"adm_sbtn_add_hack"),
        ],
        [
            Button.inline("📊 Replace Trading", data=b"adm_sbtn_rep_prediction"),
            Button.inline(
                f"➕ Append Trading ({pred_cnt})", data=b"adm_sbtn_add_prediction"
            ),
        ],
        HOME_BACK_ROW,
    ]
    await event.reply(
        f"{ui_header('VIP VAULT MANAGER', 'BUTTON PAYLOAD CONFIGURATOR')}\n\n"
        "• **Replace:** Wipes existing files and sets a new primary file.\n"
        "• **Append (+):** Adds an extra file/message to the sequence.\n\n"
        "👇 *Select a button vault to configure:*",
        buttons=btns,
    )


# --- 4. INTERACTIVE CLEAR BUTTON MENU ---
@client.on(events.NewMessage(pattern=r"^🗑 Clear Button$"))
@admin_only
async def clear_button_menu_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    btns = [
        [Button.inline("🗑 Purge Number Hack Vault", data=b"adm_cbtn_hack")],
        [Button.inline("🗑 Purge Colour Trading Vault", data=b"adm_cbtn_prediction")],
        HOME_BACK_ROW,
    ]
    await event.reply(
        f"{ui_header('PURGE VAULT FILES', 'MODULE RESET UTILITY')}\n\n"
        "👇 *Select which button vault you want to wipe clean:*",
        buttons=btns,
    )


# --- 5. INTERACTIVE WELCOME SEQUENCE MENU ---
@client.on(events.NewMessage(pattern=r"^🔢 Set Sequence$"))
@admin_only
async def sequence_menu_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    active_steps = (
        ", ".join(f"Step {s}" for s in sorted(saved_messages.keys())) or "None"
    )
    btns = [
        [
            Button.inline("➕ Step 1", data=b"adm_seq_set_1"),
            Button.inline("➕ Step 2", data=b"adm_seq_set_2"),
            Button.inline("➕ Step 3", data=b"adm_seq_set_3"),
        ],
        [
            Button.inline("➕ Step 4", data=b"adm_seq_set_4"),
            Button.inline("➕ Step 5", data=b"adm_seq_set_5"),
        ],
        [
            Button.inline("🗑 Del 1", data=b"adm_seq_del_1"),
            Button.inline("🗑 Del 2", data=b"adm_seq_del_2"),
            Button.inline("🗑 Del 3", data=b"adm_seq_del_3"),
        ],
        [Button.inline("🗑 Wipe ALL Welcome Steps", data=b"adm_seq_del_all")],
        HOME_BACK_ROW,
    ]
    await event.reply(
        f"{ui_header('ONBOARDING PIPELINE', 'WELCOME SEQUENCE BUILDER')}\n\n"
        f"✅ **Configured Steps:** `{active_steps}`\n\n"
        "👇 *Tap a slot below to assign or delete a welcome step:*",
        buttons=btns,
    )


# --- 6. INTERACTIVE MENU & BANNER CUSTOMIZER ---
def build_menu_banner_payload() -> tuple[str, list]:
    b_stat = "🟢 Active" if banner_config.get("msg_id") else "🔴 Not Set"
    anim_stat = f"🟢 {anim_style.upper()}" if animations_enabled else "🔴 OFF"
    btns = [
        [Button.inline("✏️ Edit Menu Prompt Text", data=b"adm_mb_text")],
        [
            Button.inline("🖼️ Upload Banner Media", data=b"adm_mb_setbanner"),
            Button.inline("🗑 Remove Banner", data=b"adm_mb_delbanner"),
        ],
        [Button.inline("🎧 Change Support @Handle", data=b"adm_mb_support")],
        [
            Button.inline(f"🎬 Switch Theme ({anim_stat})", data=b"adm_open_theme"),
            Button.inline("👁 Preview Menu", data=b"adm_mb_preview"),
        ],
        HOME_BACK_ROW,
    ]
    text = (
        f"{ui_header('BRANDING & FX STUDIO', 'MENU & BANNER CUSTOMIZER')}\n\n"
        f"┏━━━ **🎨 CURRENT BRANDING** ━━━┓\n"
        f"┃ 💬 **Prompt Text:** `{user_menu_text}`\n"
        f"┃ 🖼️ **Media Banner:** `{b_stat}`\n"
        f"┃ 🎧 **Concierge ID:** `{support_username}`\n"
        f"┃ 🎬 **Motion FX:** `{anim_stat}`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"👇 *Choose a branding element to customize:*"
    )
    return text, btns


@client.on(events.NewMessage(pattern=r"^🖼️ Menu & Banner$"))
@admin_only
async def menu_banner_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    text, btns = build_menu_banner_payload()
    await event.reply(text, buttons=btns)


# --- 7. INTERACTIVE MULTI-FORCE JOIN MENU ---
def build_force_join_payload() -> tuple[str, list]:
    f_stat = (
        ", ".join(f"@{c}" for c in force_channels) if force_channels else "🔴 Disabled"
    )
    btns = [
        [
            Button.inline("➕ Configure Channel(s)", data=b"adm_fj_set"),
            Button.inline("🔓 Disable Gate", data=b"adm_fj_clear"),
        ],
        HOME_BACK_ROW,
    ]
    text = (
        f"{ui_header('FORCE SUBSCRIBE GATE', 'MULTI-CHANNEL ACCESS CONTROL')}\n\n"
        f"📌 **Active Channels ({len(force_channels)}):** `{f_stat}`\n\n"
        f"💡 *Supports 1 or multiple channels (comma-separated). Ensure the bot has Admin rights in each channel!*"
    )
    return text, btns


@client.on(events.NewMessage(pattern=r"^🔒 Force Join$"))
@admin_only
async def force_join_menu_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    text, btns = build_force_join_payload()
    await event.reply(text, buttons=btns)


# --- 8. INTERACTIVE AUTO-REPLIES MENU ---
def build_auto_replies_payload() -> tuple[str, list]:
    btns = [
        [Button.inline("➕ Create Auto-Reply Rule", data=b"adm_ar_add")],
        [
            Button.inline(f"📋 View Rules ({len(auto_replies)})", data=b"adm_ar_list"),
            Button.inline("🗑 Delete Rule", data=b"adm_ar_del"),
        ],
        HOME_BACK_ROW,
    ]
    text = (
        f"{ui_header('AI AUTO-RESPONDER', 'SMART KEYWORD INTERCEPTOR')}\n\n"
        f"🔑 **Active Trigger Rules:** `{len(auto_replies)}`\n\n"
        f"👇 *Manage instant automated support responses below:*"
    )
    return text, btns


@client.on(events.NewMessage(pattern=r"^🤖 Auto-Replies$"))
@admin_only
async def auto_replies_menu_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    text, btns = build_auto_replies_payload()
    await event.reply(text, buttons=btns)


# --- 9. INTERACTIVE ADMIN & SECURITY MENU ---
@client.on(events.NewMessage(pattern=r"^👑 Manage Admins$"))
@admin_only
async def manage_admins_menu_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    btns = [
        [
            Button.inline("➕ Promote Admin", data=b"adm_sec_addadmin"),
            Button.inline("➖ Revoke Admin", data=b"adm_sec_deladmin"),
        ],
        [
            Button.inline(
                f"👑 Admin Roster ({len(ADMIN_IDS)})", data=b"adm_sec_listadmins"
            )
        ],
        [
            Button.inline("🚫 Ban User", data=b"adm_sec_ban"),
            Button.inline(
                f"✅ Unban User ({len(banned_users)})", data=b"adm_sec_unban"
            ),
        ],
        HOME_BACK_ROW,
    ]
    await event.reply(
        f"{ui_header('SECURITY & CLEARANCE', 'ADMIN & BAN MANAGEMENT')}\n\n"
        f"👑 **Authorized Admins:** `{len(ADMIN_IDS)}` | 🚫 **Banned Peers:** `{len(banned_users)}`\n\n"
        "👇 *Select a security action below:*",
        buttons=btns,
    )


# --- 10. INTERACTIVE RESTORE MENU ---
@client.on(events.NewMessage(pattern=r"^🔄 Restore$"))
@admin_only
async def restore_menu_btn(event):
    admin_chat_state.pop(event.sender_id, None)
    has_auto = os.path.exists("auto_backup.json")
    btns = [
        [Button.inline("📤 Upload Backup (.json) File", data=b"adm_res_upload")],
    ]
    if has_auto:
        btns.insert(
            0,
            [
                Button.inline(
                    "⚡ Instant Restore (auto_backup.json)", data=b"adm_res_auto"
                )
            ],
        )
    btns.append(HOME_BACK_ROW)

    await event.reply(
        f"{ui_header('RECOVERY CENTER', 'DATABASE SNAPSHOT RESTORE')}\n\n"
        "👇 *Select a recovery source to restore your users & settings:*",
        buttons=btns,
    )


# =====================================================================
# 🎯 INLINE CALLBACK HANDLERS FOR ADMIN SUB-MENUS
# =====================================================================
async def render_user_dossier(event, target_uid: int, is_edit: bool = True):
    in_db = target_uid in tracked_users
    is_blk = target_uid in blocked_users
    is_ban = target_uid in banned_users
    j_date = user_join_dates.get(target_uid, "Unknown")
    meta = user_meta.get(
        target_uid, {"referred_by": 0, "referrals": 0, "last_seen": "Unknown", "vip": 0}
    )
    is_vip = bool(meta.get("vip"))

    u_name = "Unknown"
    u_handle = "None"
    try:
        ent = await client.get_entity(target_uid)
        u_name = (
            f"{getattr(ent, 'first_name', '') or ''} {getattr(ent, 'last_name', '') or ''}".strip()
            or "User"
        )
        if getattr(ent, "username", None):
            u_handle = f"@{ent.username}"
    except Exception:
        pass

    status_badge = (
        "🚫 BANNED"
        if is_ban
        else (
            "🔴 BLOCKED BOT"
            if is_blk
            else ("🟢 ACTIVE PEER" if in_db else "⚪ NOT IN DB")
        )
    )
    dossier_btns = [
        [
            Button.inline(
                "✉️ Send Direct Message", data=f"adm_quickdm_{target_uid}".encode()
            )
        ],
        [
            Button.inline(
                "💎 Revoke VIP" if is_vip else "💎 Grant VIP",
                data=f"adm_togglevip_{target_uid}".encode(),
            ),
            Button.inline(
                "✅ Unban User" if is_ban else "🚫 Ban User",
                data=f"adm_secunbanid_{target_uid}".encode()
                if is_ban
                else f"adm_quickban_{target_uid}".encode(),
            ),
        ],
        HOME_BACK_ROW,
    ]
    text = (
        f"{ui_header('VIP PEER DOSSIER', 'EXECUTIVE INTELLIGENCE CARD')}\n\n"
        f"┏━━━ **👤 IDENTITY RECORD** ━━━┓\n"
        f"┃ 🏷 **Name:** `{u_name}`\n"
        f"┃ 🔗 **Handle:** `{u_handle}`\n"
        f"┃ 🆔 **UID:** `{target_uid}`\n"
        f"┃ 📡 **Status:** `{status_badge}`\n"
        f"┃ 🎖 **Tier:** `{'👑 DIAMOND VIP' if is_vip else '🔹 Standard'}`\n"
        f"┃ 👥 **Invites:** `{meta.get('referrals', 0)}` *(Ref by: `{meta.get('referred_by', 0)}`)*\n"
        f"┃ 📅 **Joined:** `{j_date}`\n"
        f"┃ 🕒 **Last Seen:** `{meta.get('last_seen', 'Unknown')}`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛"
    )
    if is_edit:
        await event.edit(text, buttons=dossier_btns)
    else:
        await event.respond(text, buttons=dossier_btns)


@client.on(events.CallbackQuery(pattern=b"^adm_"))
async def admin_callback_router(event):
    global banner_config, force_channels, animations_enabled, anim_style, maintenance_mode, broadcast_cancel_flag
    if event.sender_id not in ADMIN_IDS:
        return await event.answer("❌ Access Denied!", alert=True)

    admin_id = event.sender_id
    data = event.data.decode("utf-8")

    if data == "adm_bc_stop":
        broadcast_cancel_flag = True
        await event.answer("🛑 Aborting broadcast...", alert=True)
        return

    if data == "adm_home":
        admin_chat_state.pop(admin_id, None)
        await event.answer("🏠 Console Home")
        try:
            await event.edit(
                build_admin_home_text(), buttons=get_admin_inline_hub()
            )
        except Exception:
            await event.respond(
                build_admin_home_text(), buttons=get_admin_inline_hub()
            )
        return

    if data == "adm_cancel":
        admin_chat_state.pop(admin_id, None)
        await event.answer("Dismissed")
        try:
            await event.delete()
        except Exception:
            try:
                await event.edit("🚫 **Operation Dismissed.**")
            except Exception:
                pass
        return

    if data == "adm_open_bc":
        await event.answer()
        text, btns = build_broadcast_hub_payload()
        await event.edit(text, buttons=btns)
        return

    if data == "adm_open_theme":
        await event.answer()
        text, btns = build_theme_studio_payload()
        await event.edit(text, buttons=btns)
        return

    if data == "adm_open_mb":
        await event.answer()
        text, btns = build_menu_banner_payload()
        await event.edit(text, buttons=btns)
        return

    if data == "adm_open_fj":
        await event.answer()
        text, btns = build_force_join_payload()
        await event.edit(text, buttons=btns)
        return

    if data == "adm_open_ar":
        await event.answer()
        text, btns = build_auto_replies_payload()
        await event.edit(text, buttons=btns)
        return

    if data == "adm_toggle_maint_inline":
        maintenance_mode = not maintenance_mode
        set_setting("maintenance_mode", "1" if maintenance_mode else "0")
        await event.answer(
            f"🛠 Maintenance: {'ON' if maintenance_mode else 'OFF'}", alert=True
        )
        try:
            await event.edit(
                build_admin_home_text(), buttons=get_admin_inline_hub()
            )
        except Exception:
            pass
        return

    if data == "adm_refresh_stats":
        await event.answer("⚡ Refreshing live telemetry...")
        msg, btns = build_stats_payload()
        try:
            await event.edit(msg, buttons=btns)
        except Exception:
            pass
        return

    if data.startswith("adm_theme_"):
        chosen = data.replace("adm_theme_", "")
        if chosen in ("royal_gold", "cyberpunk", "matrix", "quantum", "stealth"):
            anim_style = chosen
            animations_enabled = chosen != "stealth"
            set_setting("anim_style", anim_style)
            set_setting("animations_enabled", "1" if animations_enabled else "0")
            await event.answer(f"🎬 Theme set to {anim_style.upper()}!", alert=True)
            text, btns = build_theme_studio_payload()
            try:
                await event.edit(text, buttons=btns)
            except Exception:
                pass
        return

    if data == "adm_mb_toggle_anim":
        animations_enabled = not animations_enabled
        set_setting("animations_enabled", "1" if animations_enabled else "0")
        anim_stat = "🟢 ON" if animations_enabled else "🔴 OFF"
        await event.answer(f"🎬 Animations: {anim_stat}", alert=True)
        text, btns = build_menu_banner_payload()
        await event.edit(text, buttons=btns)
        return

    if data.startswith("adm_dossier_"):
        target_uid = int(data.split("_")[-1])
        await event.answer("Opening VIP Dossier...")
        await render_user_dossier(event, target_uid, is_edit=False)
        return

    if data.startswith("adm_togglevip_"):
        target_uid = int(data.split("_")[-1])
        meta = user_meta.setdefault(
            target_uid,
            {"referred_by": 0, "referrals": 0, "last_seen": "Unknown", "vip": 0},
        )
        meta["vip"] = 0 if meta.get("vip") else 1
        save_user(
            target_uid,
            tracked_users.get(target_uid, 0),
            blocked=(target_uid in blocked_users),
        )
        await event.answer(
            f"💎 VIP {'Granted' if meta['vip'] else 'Revoked'}!", alert=True
        )
        await render_user_dossier(event, target_uid, is_edit=True)
        return

    if data.startswith("adm_quickdm_"):
        target_uid = int(data.split("_")[-1])
        await event.answer()
        prompt = await event.respond(
            f"{ui_header('DIRECT VIP DISPATCH', f'TARGET UID: {target_uid}')}\n\n"
            f"✍️ **Send your Message, Photo, Video, or Voice Note below:**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {
            "step": "waiting_for_msg",
            "target_id": target_uid,
            "prompt_id": prompt.id,
        }
        return

    if data.startswith("adm_quickban_"):
        target_uid = int(data.split("_")[-1])
        if target_uid in ADMIN_IDS:
            return await event.answer("❌ Cannot ban an Admin!", alert=True)
        banned_users.add(target_uid)
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO banned (user_id) VALUES (?)", (target_uid,)
            )
        await event.answer(f"🚫 User {target_uid} Banned!", alert=True)
        await event.respond(
            f"🚫 **User `{target_uid}` has been permanently BANNED.**",
            buttons=[HOME_BACK_ROW],
        )
        return

    if data == "adm_wipemsg":
        key = (event.chat_id, event.message_id)
        if key in admin_msg_map:
            target_msgs = admin_msg_map[key]
            for adm_id_item, msg_id_item in target_msgs:
                try:
                    await client.delete_messages(adm_id_item, [msg_id_item])
                except Exception:
                    pass
                admin_msg_map.pop((adm_id_item, msg_id_item), None)
            await event.answer("✅ Wiped from all Admin panels!")
        else:
            try:
                await event.delete()
            except Exception:
                pass
            await event.answer("🗑 Message deleted!")
        return

    if data in ("adm_bc_normal", "adm_bc_pin"):
        should_pin = data == "adm_bc_pin"
        mode_str = "📌 Broadcast + Auto-Pin" if should_pin else "📨 Standard Broadcast"
        await event.answer()
        await event.edit(
            f"{ui_header(mode_str.upper(), 'READY FOR PAYLOAD')}\n\n"
            f"👉 **Send or forward the Message, Photo, Video, or Post to transmit to `{len(tracked_users)}` users:**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {
            "step": "broadcast_send",
            "pin": should_pin,
            "delay_min": 0,
        }
        return

    if data == "adm_bc_sched":
        await event.answer()
        await event.edit(
            f"{ui_header('SCHEDULED BROADCAST', 'STEP 1/2: COUNTDOWN TIMER')}\n\n"
            "👉 **Enter the delay in minutes before firing (e.g., `10`, `30`, `60`):**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {"step": "broadcast_sched_time"}
        return

    if data.startswith("adm_sbtn_"):
        parts = data.split("_")
        mode = parts[2]
        btn_key = parts[3]
        await event.answer()
        action_label = "Replace Vault" if mode == "rep" else "Append to Vault"
        await event.edit(
            f"{ui_header(f'CONFIGURE {btn_key.upper()}', action_label.upper())}\n\n"
            f"👉 **Send the Message, File, Photo, or Video to attach to the `{btn_key}` button:**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {
            "step": "set_btn_file",
            "mode": mode,
            "btn_key": btn_key,
        }
        return

    if data.startswith("adm_cbtn_"):
        btn_key = data.split("_")[-1]
        button_forwards.pop(btn_key, None)
        delete_button_config(btn_key)
        await event.answer(f"🗑 {btn_key.upper()} vault purged!", alert=True)
        await event.edit(
            f"🗑 **All files in the `{btn_key.upper()}` vault have been wiped clean!**",
            buttons=[HOME_BACK_ROW],
        )
        return

    if data.startswith("adm_seq_set_"):
        step_num = int(data.split("_")[-1])
        await event.answer()
        await event.edit(
            f"{ui_header(f'WELCOME STEP {step_num}', 'ONBOARDING CONFIGURATOR')}\n\n"
            f"👉 **Send the Text, Photo, Video, or Forwarded Post for Step {step_num}:**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {"step": "set_seq_step", "seq_step": step_num}
        return

    if data.startswith("adm_seq_del_"):
        target = data.split("_")[-1]
        if target == "all":
            saved_messages.clear()
            with sqlite3.connect(str(DB_PATH)) as conn:
                conn.execute("DELETE FROM messages")
            await event.answer("🗑 All sequence steps cleared!", alert=True)
            await event.edit(
                "🗑 **All Welcome Sequence steps have been wiped!**",
                buttons=[HOME_BACK_ROW],
            )
        else:
            step_num = int(target)
            saved_messages.pop(step_num, None)
            with sqlite3.connect(str(DB_PATH)) as conn:
                conn.execute("DELETE FROM messages WHERE step=?", (step_num,))
            await event.answer(f"🗑 Step {step_num} deleted!", alert=True)
            await event.edit(
                f"🗑 **Welcome Sequence Step {step_num} removed!**",
                buttons=[HOME_BACK_ROW],
            )
        return

    if data == "adm_mb_text":
        await event.answer()
        await event.edit(
            f"{ui_header('EDIT MENU PROMPT', 'USER KEYBOARD CAPTION')}\n\n"
            f"📌 **Current Text:**\n{user_menu_text}\n"
            f"{ui_divider()}\n"
            "👉 **Send the new Menu Text (send `👇` for default minimal style):**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {"step": "set_menu_text"}
        return

    if data == "adm_mb_setbanner":
        await event.answer()
        await event.edit(
            f"{ui_header('UPLOAD VIP BANNER', 'MENU MEDIA HEADER')}\n\n"
            "👉 **Send any Photo, Video, or GIF to display above the user keyboard menu:**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {"step": "set_banner_media"}
        return

    if data == "adm_mb_delbanner":
        banner_config = {"msg_id": 0, "chat_id": 0}
        set_setting("banner_config", json.dumps(banner_config))
        await event.answer("🗑 Banner Removed!", alert=True)
        text, btns = build_menu_banner_payload()
        await event.edit(text, buttons=btns)
        return

    if data == "adm_mb_support":
        await event.answer()
        await event.edit(
            f"{ui_header('CONCIERGE HANDLE', 'SUPPORT CONTACT CONFIG')}\n\n"
            f"📌 **Current Handle:** `{support_username}`\n\n"
            "👉 **Send the new `@username` for user support inquiries:**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {"step": "set_support_id"}
        return

    if data == "adm_mb_preview":
        await event.answer("👁 Generating live user menu preview...")
        await send_user_menu(admin_id)
        await event.respond(
            "💡 *Tip: Type `panel` or `/start` anytime to restore your Executive Admin Keyboard.*",
            buttons=[HOME_BACK_ROW],
        )
        return

    if data == "adm_fj_set":
        await event.answer()
        await event.edit(
            f"{ui_header('CONFIGURE FORCE JOIN', 'CHANNEL GATEWAY SETUP')}\n\n"
            "👉 **Send your channel `@username` or `https://t.me/...` link:**\n"
            "💡 *For multiple channels, separate with commas (e.g. `@vip_ch1, @vip_ch2`)*\n\n"
            "⚠️ *Ensure the bot is promoted to Admin in each channel first!*",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {"step": "set_force_ch"}
        return

    if data == "adm_fj_clear":
        force_channels = []
        set_setting("force_channel", "")
        await event.answer("🔓 Force Join Disabled!", alert=True)
        text, btns = build_force_join_payload()
        await event.edit(text, buttons=btns)
        return

    if data == "adm_ar_add":
        await event.answer()
        await event.edit(
            f"{ui_header('NEW AUTO-REPLY RULE', 'STEP 1/2: TRIGGER KEYWORD')}\n\n"
            "👉 **Send the trigger keyword (e.g., `price`, `help`, `vip`):**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {"step": "ar_step_keyword"}
        return

    if data == "adm_ar_list":
        await event.answer()
        if not auto_replies:
            return await event.edit(
                "📭 **No Auto-Reply rules configured yet.**",
                buttons=[HOME_BACK_ROW],
            )
        msg = f"{ui_header('ACTIVE AUTO-REPLIES', f'{len(auto_replies)} RULES LOADED')}\n\n"
        for kw, resp in auto_replies.items():
            short_resp = resp[:35] + "..." if len(resp) > 35 else resp
            msg += f"🔹 `{kw}` ➔ {short_resp}\n"
        await event.edit(msg, buttons=[HOME_BACK_ROW])
        return

    if data == "adm_ar_del":
        await event.answer()
        if not auto_replies:
            return await event.edit(
                "📭 **No Auto-Reply rules to delete.**", buttons=[HOME_BACK_ROW]
            )
        kw_btns = []
        for kw in list(auto_replies.keys())[:15]:
            kw_btns.append(
                [Button.inline(f"🗑 Delete '{kw}'", data=f"adm_ardelkw_{kw}".encode())]
            )
        kw_btns.append(HOME_BACK_ROW)
        await event.edit(
            f"{ui_header('DELETE AUTO-REPLY', 'TAP RULE TO REMOVE')}\n\n"
            "👇 *Tap any keyword below to delete it immediately:*",
            buttons=kw_btns,
        )
        return

    if data.startswith("adm_ardelkw_"):
        kw = data.replace("adm_ardelkw_", "", 1)
        auto_replies.pop(kw, None)
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute("DELETE FROM auto_replies WHERE keyword=?", (kw,))
        await event.answer(f"🗑 Deleted: {kw}", alert=True)
        text, btns = build_auto_replies_payload()
        await event.edit(text, buttons=btns)
        return

    if data == "adm_sec_addadmin":
        await event.answer()
        await event.edit(
            f"{ui_header('PROMOTE NEW ADMIN', 'GRANT EXECUTIVE ACCESS')}\n\n"
            "👉 **Send the Numeric Telegram UID of the new Admin:**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {"step": "sec_add_admin"}
        return

    if data == "adm_sec_deladmin":
        await event.answer()
        sub_admins = [a for a in ADMIN_IDS if a not in ROOT_ADMINS]
        if not sub_admins:
            return await event.edit(
                "⚠️ **No Sub-Admins found (Root Admins cannot be removed).**",
                buttons=[HOME_BACK_ROW],
            )
        adm_btns = [
            [Button.inline(f"🗑 Revoke Admin {aid}", data=f"adm_secdelid_{aid}".encode())]
            for aid in sub_admins
        ]
        adm_btns.append(HOME_BACK_ROW)
        await event.edit(
            f"{ui_header('REVOKE ADMIN', 'SELECT SUB-ADMIN')}\n\n"
            "👇 *Tap an Admin ID below to revoke their privileges:*",
            buttons=adm_btns,
        )
        return

    if data.startswith("adm_secdelid_"):
        target_aid = int(data.split("_")[-1])
        if target_aid in ROOT_ADMINS:
            return await event.answer("❌ Cannot remove Root Admin!", alert=True)
        if target_aid in ADMIN_IDS:
            ADMIN_IDS.remove(target_aid)
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute("DELETE FROM admins WHERE user_id=?", (target_aid,))
        await event.answer("🗑 Admin Removed!", alert=True)
        await event.edit(
            f"🗑 **Admin `{target_aid}` privileges revoked!**",
            buttons=[HOME_BACK_ROW],
        )
        return

    if data == "adm_sec_listadmins":
        await event.answer()
        msg = f"{ui_header('EXECUTIVE ROSTER', 'AUTHORIZED ADMINISTRATORS')}\n\n"
        for aid in ADMIN_IDS:
            role = "👑 **Root Admin**" if aid in ROOT_ADMINS else "🔹 **Sub Admin**"
            msg += f"• {role} — `{aid}`\n"
        await event.edit(msg, buttons=[HOME_BACK_ROW])
        return

    if data == "adm_sec_ban":
        await event.answer()
        await event.edit(
            f"{ui_header('BLACKLIST USER', 'SECURITY RESTRICTION')}\n\n"
            "👉 **Send the Numeric UID of the user to Ban:**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {"step": "sec_ban_user"}
        return

    if data == "adm_sec_unban":
        await event.answer()
        if not banned_users:
            return await event.edit(
                "✅ **Blacklist is currently empty.**", buttons=[HOME_BACK_ROW]
            )
        ub_btns = [
            [Button.inline(f"✅ Unban {uid}", data=f"adm_secunbanid_{uid}".encode())]
            for uid in list(banned_users)[:15]
        ]
        ub_btns.append(HOME_BACK_ROW)
        await event.edit(
            f"{ui_header('UNBAN USER', 'RESTORE ACCESS')}\n\n"
            "👇 *Tap a User ID below to unban immediately (or type UID):*",
            buttons=ub_btns,
        )
        admin_chat_state[admin_id] = {"step": "sec_unban_user"}
        return

    if data.startswith("adm_secunbanid_"):
        target_uid = int(data.split("_")[-1])
        banned_users.discard(target_uid)
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute("DELETE FROM banned WHERE user_id=?", (target_uid,))
        admin_chat_state.pop(admin_id, None)
        await event.answer(f"✅ Unbanned {target_uid}!", alert=True)
        await event.edit(
            f"✅ **User `{target_uid}` has been restored!**",
            buttons=[HOME_BACK_ROW],
        )
        return

    if data == "adm_res_auto":
        await event.answer("Restoring from auto_backup.json...")
        try:
            with open("auto_backup.json", "r") as f:
                bdata = json.load(f)
            restore_from_dict(bdata)
            await event.edit(
                f"{ui_header('RESTORE COMPLETE', 'AUTO-BACKUP LOADED')}\n\n"
                f"✅ **Successfully restored `{len(tracked_users)}` peers!**",
                buttons=[HOME_BACK_ROW],
            )
        except Exception as e:
            await event.edit(
                f"❌ **Auto-Restore Failed:** `{e}`", buttons=[HOME_BACK_ROW]
            )
        return

    if data == "adm_res_upload":
        await event.answer()
        await event.edit(
            f"{ui_header('UPLOAD SNAPSHOT', 'JSON DATABASE RESTORE')}\n\n"
            "👉 **Upload and send your `.json` backup file below:**",
            buttons=CANCEL_BTN,
        )
        admin_chat_state[admin_id] = {"step": "restore_upload_json"}
        return


# =====================================================================
# 🚀 BROADCAST ENGINE 4.0 (LUXURY TELEMETRY + EVERY 3 USERS + SCHEDULER)
# =====================================================================
async def execute_broadcast(
    event,
    should_pin: bool,
    manual_text: str = None,
    reply_msg_obj=None,
    delay_minutes: int = 0,
):
    global broadcast_cancel_flag
    if not tracked_users:
        return await event.reply("❌ No tracked users in database.")

    if delay_minutes > 0:
        sched_msg = await event.reply(
            f"{ui_header('BROADCAST QUEUED', 'TIMER COUNTDOWN ACTIVE')}\n\n"
            f"⏳ **Scheduled Launch:** `In {delay_minutes} minutes`\n"
            f"👥 **Target Audience:** `{len(tracked_users)}` peers\n"
            f"💡 *Transmission will initiate automatically when countdown completes.*"
        )
        await asyncio.sleep(delay_minutes * 60)
        try:
            await sched_msg.delete()
        except Exception:
            pass

    broadcast_cancel_flag = False
    total_targets = len(tracked_users)
    stop_btn = [[Button.inline("🛑 Abort Transmission", data=b"adm_bc_stop")]]

    launch_frames = [
        (
            "╭━━━✦ **📡 BROADCAST ENGINE** ✦━━━╮\n"
            "┆ ⚡ `Locking peer database & warming threads...`\n"
            "┆ `▰▰▰▰▱▱▱▱▱▱ 40%`\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
            0.26,
        ),
        (
            "╭━━━✦ **📡 BROADCAST ENGINE** ✦━━━╮\n"
            f"┆ 🚀 `Igniting transmission to {total_targets} peers...`\n"
            "┆ `▰▰▰▰▰▰▰▰▰▰ 100%`\n"
            "╰━━━━━━━━━━━━━━━━━━━━━━━╯",
            0.26,
        ),
    ]
    status_msg = await play_animation(event, launch_frames)

    success = fail = skip = 0
    processed = 0
    bc_start_time = time.time()
    spin_idx = 0

    for uid, old_hash in list(tracked_users.items()):
        if broadcast_cancel_flag:
            break

        processed += 1
        if uid in blocked_users:
            skip += 1
        else:
            try:
                peer = await client.get_input_entity(uid)
                if reply_msg_obj:
                    sent = await client.forward_messages(
                        peer, reply_msg_obj.id, reply_msg_obj.chat_id
                    )
                elif manual_text is not None:
                    sent = await client.send_message(peer, manual_text)
                elif event.fwd_from:
                    sent = await client.forward_messages(peer, event.id, event.chat_id)
                else:
                    sent = await client.send_message(
                        peer, event.text or "", file=event.media
                    )

                if should_pin and sent:
                    try:
                        msg_to_pin = sent[0].id if isinstance(sent, list) else sent.id
                        await client.pin_message(peer, msg_to_pin, notify=True)
                    except Exception:
                        pass

                success += 1
                await asyncio.sleep(0.25)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds)
            except UserIsBlockedError:
                blocked_users.add(uid)
                save_user(uid, old_hash, blocked=True)
                fail += 1
            except Exception:
                fail += 1

        # 🔥 UPDATE EVERY 3 USERS (OR FINAL USER)
        if processed % 3 == 0 or processed == total_targets:
            pct = int((processed / total_targets) * 100)
            bar = make_bar(pct, style="gold")
            spinner = SPINNER_FRAMES[spin_idx % len(SPINNER_FRAMES)]
            spin_idx += 1

            elapsed = max(time.time() - bc_start_time, 0.1)
            speed = processed / elapsed
            remaining_users = total_targets - processed
            eta_str = format_eta(remaining_users / speed) if speed > 0 else "..."

            try:
                await status_msg.edit(
                    f"╭━━━✦ **{spinner} LIVE TRANSMISSION** ✦━━━╮\n"
                    f"┆ `{bar} {pct}%`\n"
                    f"╰━━━━━━━━━━━━━━━━━━━━━━━╯\n"
                    f"┏━━━ **📊 TELEMETRY STREAM** ━━━┓\n"
                    f"┃ 🔄 **Processed:** `{processed} / {total_targets}`\n"
                    f"┃ ✅ **Delivered:** `{success}`\n"
                    f"┃ ❌ **Failed/Blocked:** `{fail}`\n"
                    f"┃ ⏭ **Skipped:** `{skip}`\n"
                    f"┃ ⚡ **Velocity:** `{speed:.1f} peers/s` • ⏳ **ETA:** `{eta_str}`\n"
                    f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛",
                    buttons=stop_btn,
                )
            except Exception:
                pass

    total_time = format_eta(time.time() - bc_start_time)
    header_title = (
        "🛑 TRANSMISSION ABORTED"
        if broadcast_cancel_flag
        else "✅ TRANSMISSION COMPLETE"
    )
    await status_msg.edit(
        f"{ui_header(header_title, 'BROADCAST SUMMARY REPORT')}\n\n"
        f"┏━━━ **📈 FINAL METRICS** ━━━┓\n"
        f"┃ 👥 **Processed:** `{processed} / {total_targets}`\n"
        f"┃ ✅ **Delivered:** `{success}`\n"
        f"┃ ❌ **Failed/Blocked:** `{fail}`\n"
        f"┃ ⏭ **Skipped:** `{skip}`\n"
        f"┃ ⏱ **Elapsed Time:** `{total_time}`\n"
        f"┃ 📌 **Auto-Pinned:** `{'Yes' if should_pin else 'No'}`\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━━━┛",
        buttons=[HOME_BACK_ROW],
    )


# =====================================================================
# 🧠 MASTER INTERACTIVE STATE PROCESSOR (HANDLES ALL ADMIN INPUTS)
# =====================================================================
@client.on(
    events.NewMessage(
        func=lambda e: e.is_private
        and e.sender_id in ADMIN_IDS
        and e.sender_id in admin_chat_state
    )
)
async def handle_admin_chat_state(event):
    global user_menu_text, banner_config, support_username, force_channels
    admin_id = event.sender_id
    raw_txt = (event.raw_text or "").strip()

    if raw_txt.lower() in ADMIN_KB_LABELS or raw_txt.startswith("/"):
        return

    state = admin_chat_state[admin_id]
    step = state.get("step")

    # 0. Inspect User ID
    if step == "inspect_user_id":
        if not raw_txt.lstrip("-").isdigit():
            return await event.reply(
                "❌ **Invalid UID!** Please send a numeric Telegram ID:",
                buttons=CANCEL_BTN,
            )
        target_uid = int(raw_txt)
        admin_chat_state.pop(admin_id, None)
        scan_msg = await play_animation(
            event,
            [("🔍 `[DOSSIER] Querying peer profile & database records...`", 0.28)],
        )
        await render_user_dossier(scan_msg, target_uid, is_edit=True)

    # 1. Direct Message: Waiting for UID
    elif step == "waiting_for_id":
        if raw_txt.lstrip("-").isdigit():
            target_id = int(raw_txt)
            state["target_id"] = target_id
            state["step"] = "waiting_for_msg"
            await event.respond(
                f"{ui_header('TARGET LOCKED', f'UID: {target_id}')}\n\n"
                f"✍️ **Now send the Message, Photo, or Video to deliver:**",
                buttons=CANCEL_BTN,
            )
        else:
            await event.reply(
                "❌ **Invalid UID!** Please send a numeric ID:", buttons=CANCEL_BTN
            )

    # 2. Direct Message: Waiting for Message Content
    elif step == "waiting_for_msg":
        target_id = state["target_id"]
        admin_chat_state.pop(admin_id, None)
        try:
            access_hash = tracked_users.get(target_id, 0)
            peer = InputPeerUser(target_id, access_hash) if access_hash else target_id
            if event.text:
                await client.send_message(peer, event.text, file=event.media)
            elif event.media:
                await client.send_message(peer, file=event.media)
            user_chat_state[target_id] = True
            await event.respond(
                f"✅ **VIP Dispatch successfully delivered to `{target_id}`!**",
                buttons=[HOME_BACK_ROW],
            )
        except UserIsBlockedError:
            blocked_users.add(target_id)
            save_user(target_id, tracked_users.get(target_id, 0), blocked=True)
            await event.respond(
                "❌ **Delivery Failed:** User has blocked the bot.",
                buttons=[HOME_BACK_ROW],
            )
        except Exception as e:
            await event.respond(
                f"❌ **Delivery Failed:** `{e}`", buttons=[HOME_BACK_ROW]
            )

    # 3A. Scheduled Broadcast Step 1 (Minutes)
    elif step == "broadcast_sched_time":
        if not raw_txt.isdigit() or int(raw_txt) <= 0:
            return await event.reply(
                "❌ **Invalid Time!** Enter positive minutes (e.g. `15`):",
                buttons=CANCEL_BTN,
            )
        mins = int(raw_txt)
        state["delay_min"] = mins
        state["pin"] = False
        state["step"] = "broadcast_send"
        await event.reply(
            f"{ui_header('TIMER LOCKED', f'{mins} MINUTES DELAY')}\n\n"
            f"👉 **Now send the Message, Photo, or Video to broadcast in `{mins}m`:**",
            buttons=CANCEL_BTN,
        )

    # 3B. Broadcast Execution
    elif step == "broadcast_send":
        should_pin = state.get("pin", False)
        delay_min = state.get("delay_min", 0)
        admin_chat_state.pop(admin_id, None)
        asyncio.create_task(
            execute_broadcast(event, should_pin, delay_minutes=delay_min)
        )

    # 4. Set / Add Module Button File
    elif step == "set_btn_file":
        mode = state["mode"]
        btn_key = state["btn_key"]
        admin_chat_state.pop(admin_id, None)
        if mode == "rep":
            delete_button_config(btn_key)
            button_forwards[btn_key] = []
        if btn_key not in button_forwards:
            button_forwards[btn_key] = []
        add_button_config(btn_key, event.id, event.chat_id)
        button_forwards[btn_key].append(
            {"msg_id": event.id, "from_chat": event.chat_id}
        )
        total_f = len(button_forwards[btn_key])
        more_btn = [
            [
                Button.inline(
                    f"➕ Append Another File to {btn_key.upper()}",
                    data=f"adm_sbtn_add_{btn_key}".encode(),
                )
            ],
            HOME_BACK_ROW,
        ]
        await event.reply(
            f"{ui_header('VAULT UPDATED', f'{btn_key.upper()} MODULE')}\n\n"
            f"✅ **Payload stored successfully!**\n"
            f"📁 **Total Active Files in Vault:** `{total_f}`",
            buttons=more_btn,
        )

    # 5. Set Welcome Sequence Step
    elif step == "set_seq_step":
        seq_step = state["seq_step"]
        admin_chat_state.pop(admin_id, None)
        if event.media or event.fwd_from:
            data = {"type": "forward", "msg_id": event.id, "from_chat": event.chat_id}
        else:
            data = {"type": "text", "text": raw_txt}
        saved_messages[seq_step] = data
        save_message_step(seq_step, data)
        await event.reply(
            f"✅ **Welcome Pipeline Step {seq_step} Saved!**",
            buttons=[HOME_BACK_ROW],
        )

    # 6. Edit User Menu Text
    elif step == "set_menu_text":
        if not raw_txt:
            return await event.reply(
                "❌ Prompt text cannot be empty! Try again:", buttons=CANCEL_BTN
            )
        admin_chat_state.pop(admin_id, None)
        user_menu_text = raw_txt
        set_setting("user_menu_text", user_menu_text)
        await event.reply(
            f"✅ **User Menu Prompt Updated!**\n\nPreview:\n{user_menu_text}",
            buttons=[HOME_BACK_ROW],
        )

    # 7. Set Menu Banner Media
    elif step == "set_banner_media":
        if not event.media:
            return await event.reply(
                "❌ **Error:** Please send a Photo, Video, or GIF!",
                buttons=CANCEL_BTN,
            )
        admin_chat_state.pop(admin_id, None)
        banner_config = {"msg_id": event.id, "chat_id": event.chat_id}
        set_setting("banner_config", json.dumps(banner_config))
        await event.reply(
            "🖼️ **VIP Menu Banner Media Updated Successfully!**",
            buttons=[HOME_BACK_ROW],
        )

    # 8. Set Support Username
    elif step == "set_support_id":
        if not raw_txt:
            return await event.reply(
                "❌ Send a valid `@username`:", buttons=CANCEL_BTN
            )
        admin_chat_state.pop(admin_id, None)
        support_username = raw_txt if raw_txt.startswith("@") else f"@{raw_txt}"
        set_setting("support_username", support_username)
        await event.reply(
            f"✅ **Concierge Handle Updated:** `{support_username}`",
            buttons=[HOME_BACK_ROW],
        )

    # 9. Set Force Join Channel(s)
    elif step == "set_force_ch":
        if not raw_txt:
            return await event.reply(
                "❌ Send channel `@username`:", buttons=CANCEL_BTN
            )
        admin_chat_state.pop(admin_id, None)
        parsed_channels = []
        for part in raw_txt.split(","):
            ch = part.strip()
            if "t.me/" in ch:
                ch = ch.split("t.me/")[-1].split("/")[0]
            ch = ch.lstrip("@").strip()
            if ch and ch not in parsed_channels:
                parsed_channels.append(ch)
        force_channels = parsed_channels
        set_setting("force_channel", json.dumps(force_channels))
        ch_display = ", ".join(f"@{c}" for c in force_channels)
        await event.reply(
            f"🔒 **Force Subscribe Gate Enabled for:** `{ch_display}`",
            buttons=[HOME_BACK_ROW],
        )

    # 10. Auto-Reply Step 1 (Keyword)
    elif step == "ar_step_keyword":
        if not raw_txt:
            return await event.reply(
                "❌ Send a trigger keyword:", buttons=CANCEL_BTN
            )
        kw = raw_txt.lower()
        state["keyword"] = kw
        state["step"] = "ar_step_response"
        await event.reply(
            f"{ui_header('KEYWORD LOCKED', f'TRIGGER: {kw}')}\n\n"
            f"👉 **Step 2/2: Now send the automated response text for `{kw}`:**",
            buttons=CANCEL_BTN,
        )

    # 11. Auto-Reply Step 2 (Response)
    elif step == "ar_step_response":
        if not raw_txt:
            return await event.reply(
                "❌ Response text cannot be empty!", buttons=CANCEL_BTN
            )
        kw = state["keyword"]
        admin_chat_state.pop(admin_id, None)
        auto_replies[kw] = raw_txt
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO auto_replies (keyword, response) VALUES (?, ?)",
                (kw, raw_txt),
            )
        await event.reply(
            f"✅ **Auto-Reply Rule Saved!**\n🔑 `{kw}` ➔ {raw_txt}",
            buttons=[HOME_BACK_ROW],
        )

    # 12. Security: Add Admin
    elif step == "sec_add_admin":
        if not raw_txt.isdigit():
            return await event.reply(
                "❌ Send a numeric Telegram UID:", buttons=CANCEL_BTN
            )
        new_aid = int(raw_txt)
        admin_chat_state.pop(admin_id, None)
        if new_aid not in ADMIN_IDS:
            ADMIN_IDS.append(new_aid)
            with sqlite3.connect(str(DB_PATH)) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_aid,)
                )
        await event.reply(
            f"👑 **New Admin Promoted:** `{new_aid}`", buttons=[HOME_BACK_ROW]
        )

    # 13. Security: Ban User
    elif step == "sec_ban_user":
        if not raw_txt.isdigit():
            return await event.reply(
                "❌ Send a numeric Telegram UID:", buttons=CANCEL_BTN
            )
        b_uid = int(raw_txt)
        admin_chat_state.pop(admin_id, None)
        if b_uid in ADMIN_IDS:
            return await event.reply("❌ Cannot ban an Admin!")
        banned_users.add(b_uid)
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO banned (user_id) VALUES (?)", (b_uid,)
            )
        await event.reply(
            f"🚫 **User `{b_uid}` has been BANNED!**", buttons=[HOME_BACK_ROW]
        )

    # 14. Security: Unban User
    elif step == "sec_unban_user":
        if not raw_txt.isdigit():
            return await event.reply(
                "❌ Send a numeric Telegram UID:", buttons=CANCEL_BTN
            )
        ub_uid = int(raw_txt)
        admin_chat_state.pop(admin_id, None)
        banned_users.discard(ub_uid)
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute("DELETE FROM banned WHERE user_id=?", (ub_uid,))
        await event.reply(
            f"✅ **User `{ub_uid}` has been UNBANNED!**", buttons=[HOME_BACK_ROW]
        )

    # 15. Restore via JSON Upload
    elif step == "restore_upload_json":
        if not event.file or not event.file.name.endswith(".json"):
            return await event.reply(
                "❌ Please upload a valid `.json` backup file:", buttons=CANCEL_BTN
            )
        admin_chat_state.pop(admin_id, None)
        path = await client.download_media(event.media)
        try:
            with open(path, "r") as f:
                bdata = json.load(f)
            extra_adm = restore_from_dict(bdata)
            await event.reply(
                f"✅ **Restore Complete!** Loaded `{len(tracked_users)}` peers and `{extra_adm}` sub-admins.",
                buttons=[HOME_BACK_ROW],
            )
        except Exception as e:
            await event.reply(
                f"❌ **Restore Failed:** `{e}`", buttons=[HOME_BACK_ROW]
            )
        finally:
            if os.path.exists(path):
                os.remove(path)

    raise events.StopPropagation


# =====================================================================
# 🛠 LEGACY SLASH COMMANDS (BACKWARD COMPATIBILITY)
# =====================================================================
@client.on(events.NewMessage(pattern=r"^/cancel$"))
@admin_only
async def cancel_state_cmd(event):
    admin_chat_state.pop(event.sender_id, None)
    await event.reply("🚫 `[Notice] Operation cancelled successfully.`")


@client.on(events.NewMessage(pattern=r"^/del$"))
@admin_only
async def global_delete_cmd(event):
    if not event.is_reply:
        return await event.reply(
            "❌ `[Error] Please reply to the user's message with /del to wipe it.`"
        )
    replied = await event.get_reply_message()
    key = (event.chat_id, replied.id)
    if key in admin_msg_map:
        target_msgs = admin_msg_map[key]
        for adm_id, msg_id in target_msgs:
            try:
                await client.delete_messages(adm_id, [msg_id])
            except Exception:
                pass
            admin_msg_map.pop((adm_id, msg_id), None)
        del_confirm = await event.respond(
            "✅ `[sys] Message wiped globally from all Admin panels.`"
        )
        try:
            await event.delete()
        except Exception:
            pass
        await asyncio.sleep(3)
        try:
            await del_confirm.delete()
        except Exception:
            pass
    else:
        warn = await event.reply(
            "⚠️ `[Notice] Cannot wipe. Message not found in active global registry.`"
        )
        await asyncio.sleep(3)
        try:
            await warn.delete()
        except Exception:
            pass


@client.on(events.NewMessage(pattern=r"^/send\s+(\d+)(?:\s+(.+))?"))
@admin_only
async def send_dm_manual(event):
    target_uid = int(event.pattern_match.group(1))
    text_msg = event.pattern_match.group(2)
    try:
        peer = InputPeerUser(target_uid, tracked_users.get(target_uid, 0))
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            await client.send_message(
                peer, text_msg or reply_msg.text or "", file=reply_msg.media
            )
        elif text_msg:
            await client.send_message(peer, text_msg.strip())
        user_chat_state[target_uid] = True
        await event.reply(f"✅ **Message successfully delivered to `{target_uid}`!**")
    except UserIsBlockedError:
        blocked_users.add(target_uid)
        save_user(target_uid, tracked_users.get(target_uid, 0), blocked=True)
        await event.reply("❌ `[Error] Delivery Failed: User blocked the bot.`")
    except Exception:
        await event.reply("❌ `[Error] Delivery Failed:` System issue ya invalid ID.")


@client.on(events.NewMessage(pattern=r"^/broadcast(_pin)?(?:\s+(.+))?"))
@admin_only
async def broadcast_slash(event):
    should_pin = bool(event.pattern_match.group(1))
    text = (
        event.raw_text.replace("/broadcast_pin", "", 1)
        .replace("/broadcast", "", 1)
        .strip()
    )
    if not text and not event.is_reply:
        return await event.reply(
            "❌ Message text dein ya kisi message par reply karein."
        )
    reply_msg = await event.get_reply_message() if event.is_reply else None
    await execute_broadcast(
        event,
        should_pin,
        manual_text=text if not reply_msg else None,
        reply_msg_obj=reply_msg,
    )


@client.on(events.NewMessage(pattern=r"^/setmsg(\d+)(?:\s+(.+))?"))
@admin_only
async def setmsg_slash(event):
    step = int(event.pattern_match.group(1))
    extra = event.pattern_match.group(2)
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        data = {"type": "forward", "msg_id": reply_msg.id, "from_chat": event.chat_id}
    elif extra is not None:
        data = {"type": "text", "text": extra.strip()}
    else:
        if step in saved_messages:
            del saved_messages[step]
            with sqlite3.connect(str(DB_PATH)) as conn:
                conn.execute("DELETE FROM messages WHERE step=?", (step,))
            return await event.reply(f"🗑 Sequence step {step} hata diya gaya hai.")
        return await event.reply(
            "❌ Text provide karein ya kisi message par reply karein."
        )
    saved_messages[step] = data
    save_message_step(step, data)
    await event.reply(f"✅ Sequence Step {step} save ho gaya hai.")


@client.on(events.NewMessage(pattern=r"^/setbutton\s+(hack|prediction)$"))
@admin_only
async def set_button_slash(event):
    btn_key = event.pattern_match.group(1).lower()
    if not event.is_reply:
        return await event.reply(
            "❌ Please reply to the message you want to set for this button."
        )
    reply_msg = await event.get_reply_message()
    chat_id = get_chat_id(reply_msg, event)
    delete_button_config(btn_key)
    button_forwards[btn_key] = []
    add_button_config(btn_key, reply_msg.id, chat_id)
    button_forwards[btn_key].append({"msg_id": reply_msg.id, "from_chat": chat_id})
    await event.reply(f"✅ Button **'{btn_key}'** set ho gaya hai! (1 file)")


@client.on(events.NewMessage(pattern=r"^/addbutton\s+(hack|prediction)$"))
@admin_only
async def add_button_slash(event):
    btn_key = event.pattern_match.group(1).lower()
    if not event.is_reply:
        return await event.reply("❌ Please reply to the message.")
    if btn_key not in button_forwards:
        button_forwards[btn_key] = []
    reply_msg = await event.get_reply_message()
    chat_id = get_chat_id(reply_msg, event)
    add_button_config(btn_key, reply_msg.id, chat_id)
    button_forwards[btn_key].append({"msg_id": reply_msg.id, "from_chat": chat_id})
    await event.reply(
        f"✅ Additional file added! Total: `{len(button_forwards[btn_key])}`"
    )


@client.on(events.NewMessage(pattern=r"^/clearbutton\s+(hack|prediction)$"))
@admin_only
async def clear_button_slash(event):
    btn_key = event.pattern_match.group(1).lower()
    if btn_key in button_forwards:
        del button_forwards[btn_key]
        delete_button_config(btn_key)
        await event.reply(f"🗑 Button **'{btn_key}'** clear kar diya gaya hai.")
    else:
        await event.reply("⚠️ Is button ki koi configuration nahi mili.")


@client.on(events.NewMessage(pattern=r"^/addadmin\s+(\d+)"))
@admin_only
async def add_admin_slash(event):
    new_admin_id = int(event.pattern_match.group(1))
    if new_admin_id in ADMIN_IDS:
        return await event.reply(f"⚠️ User `{new_admin_id}` pehle se hi admin hai.")
    ADMIN_IDS.append(new_admin_id)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_admin_id,)
        )
    await event.reply(f"✅ Naya admin add ho gaya hai: `{new_admin_id}`")


@client.on(events.NewMessage(pattern=r"^/deladmin\s+(\d+)"))
@admin_only
async def del_admin_slash(event):
    target_admin_id = int(event.pattern_match.group(1))
    if target_admin_id in ROOT_ADMINS:
        return await event.reply("❌ Root Admin ko remove nahi kiya ja sakta.")
    if target_admin_id in ADMIN_IDS:
        ADMIN_IDS.remove(target_admin_id)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("DELETE FROM admins WHERE user_id=?", (target_admin_id,))
    await event.reply(f"🗑 Admin privileges hata di gayi hain: `{target_admin_id}`")


@client.on(events.NewMessage(pattern=r"^/listadmins"))
@admin_only
async def list_admins_slash(event):
    msg = "👑 **CURRENT ADMINS:**\n➖➖➖➖➖➖➖➖➖➖➖➖\n"
    for aid in ADMIN_IDS:
        role = "⭐ (Root Admin)" if aid in ROOT_ADMINS else "🔹 (Sub Admin)"
        msg += f"{role} `{aid}`\n"
    await event.reply(msg)


@client.on(events.NewMessage(pattern=r"^/setreply\s+(.+?)\s*\|\s*(.+)"))
@admin_only
async def set_auto_reply_slash(event):
    keyword = event.pattern_match.group(1).strip().lower()
    response = event.pattern_match.group(2).strip()
    auto_replies[keyword] = response
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO auto_replies (keyword, response) VALUES (?, ?)",
            (keyword, response),
        )
    await event.reply(f"✅ **Auto-Reply Saved:** `{keyword}`")


@client.on(events.NewMessage(pattern=r"^/delreply\s+(.+)"))
@admin_only
async def del_auto_reply_slash(event):
    keyword = event.pattern_match.group(1).strip().lower()
    if keyword in auto_replies:
        del auto_replies[keyword]
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute("DELETE FROM auto_replies WHERE keyword=?", (keyword,))
        await event.reply(f"🗑 Auto-reply deleted: `{keyword}`")
    else:
        await event.reply("⚠️ Keyword nahi mila.")


@client.on(events.NewMessage(pattern=r"^/listreplies$"))
@admin_only
async def list_auto_replies_slash(event):
    if not auto_replies:
        return await event.reply("📭 Abhi koi auto-replies set nahi hain.")
    msg = "🤖 **ACTIVE AUTO-REPLIES:**\n➖➖➖➖➖➖➖➖➖➖➖➖\n"
    for kw, resp in auto_replies.items():
        msg += f"🔹 `{kw}` ➡ {resp[:25]}\n"
    await event.reply(msg)


@client.on(events.NewMessage(pattern=r"^/restore"))
@admin_only
async def restore_slash(event):
    if not event.is_reply:
        return await event.reply("❌ Please reply to a `.json` backup file.")
    rep = await event.get_reply_message()
    if not rep.file or not rep.file.name.endswith(".json"):
        return await event.reply("❌ Invalid file format.")
    path = await client.download_media(rep.media)
    try:
        with open(path, "r") as f:
            data = json.load(f)
        extra_adm = restore_from_dict(data)
        await event.reply(
            f"✅ **Restore Successful:** Loaded `{len(tracked_users)}` users and `{extra_adm}` extra admins."
        )
    except Exception as e:
        await event.reply(f"❌ Restore failed: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)


def restore_from_dict(data: dict):
    global tracked_users, blocked_users, banned_users, user_join_dates, user_meta, saved_messages, button_forwards
    global welcome_enabled, animations_enabled, maintenance_mode, anim_style, user_menu_text, support_username
    global force_channels, banner_config, click_stats, auto_replies, ADMIN_IDS

    tracked_users = {int(k): int(v) for k, v in data.get("tracked", {}).items()}
    blocked_users = set(int(u) for u in data.get("blocked", []))
    banned_users = set(int(u) for u in data.get("banned", []))
    user_join_dates = {int(k): str(v) for k, v in data.get("join_dates", {}).items()}
    user_meta = {int(k): v for k, v in data.get("user_meta", {}).items()}
    saved_messages = {int(k): v for k, v in data.get("messages", {}).items()}
    button_forwards = data.get("button_forwards", {})
    welcome_enabled = data.get("welcome", True)
    animations_enabled = data.get("animations_enabled", True)
    maintenance_mode = data.get("maintenance_mode", False)
    anim_style = data.get("anim_style", "royal_gold")
    user_menu_text = data.get("user_menu_text", user_menu_text)
    support_username = data.get("support_username", support_username)

    raw_fc = data.get("force_channel", "")
    if isinstance(raw_fc, list):
        force_channels = [str(c).lstrip("@") for c in raw_fc if c]
    elif isinstance(raw_fc, str) and raw_fc:
        try:
            parsed = json.loads(raw_fc)
            force_channels = (
                [str(c).lstrip("@") for c in parsed if c]
                if isinstance(parsed, list)
                else [raw_fc.lstrip("@")]
            )
        except Exception:
            force_channels = [
                c.strip().lstrip("@") for c in raw_fc.split(",") if c.strip()
            ]
    else:
        force_channels = []

    banner_config = data.get("banner_config", {"msg_id": 0, "chat_id": 0})
    click_stats.update(
        data.get("click_stats", {"prediction": 0, "hack": 0, "support": 0})
    )
    auto_replies = data.get("auto_replies", {})
    db_admins = data.get("db_admins", [])

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("DELETE FROM users")
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM button_msgs")
        conn.execute("DELETE FROM auto_replies")
        conn.execute("DELETE FROM admins")
        conn.execute("DELETE FROM banned")

        for uid, hsh in tracked_users.items():
            jdate = user_join_dates.get(uid, datetime.now().strftime("%Y-%m-%d"))
            meta = user_meta.get(
                uid, {"referred_by": 0, "referrals": 0, "last_seen": jdate, "vip": 0}
            )
            conn.execute(
                """INSERT OR REPLACE INTO users 
                   (user_id, access_hash, blocked, joined_date, referred_by, referrals, last_seen, vip) 
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    uid,
                    hsh,
                    int(uid in blocked_users),
                    jdate,
                    meta.get("referred_by", 0),
                    meta.get("referrals", 0),
                    meta.get("last_seen", jdate),
                    meta.get("vip", 0),
                ),
            )
        for uid in banned_users:
            conn.execute("INSERT OR IGNORE INTO banned (user_id) VALUES (?)", (uid,))
        for step, d in saved_messages.items():
            conn.execute(
                "INSERT OR REPLACE INTO messages (step, msg_type, text, msg_id, from_chat) VALUES (?,?,?,?,?)",
                (step, d.get("type"), d.get("text"), d.get("msg_id"), d.get("from_chat")),
            )
        for key, cfg_list in button_forwards.items():
            if isinstance(cfg_list, dict):
                cfg_list = [cfg_list]
            for cfg in cfg_list:
                conn.execute(
                    "INSERT INTO button_msgs (btn_key, msg_id, from_chat) VALUES (?,?,?)",
                    (key, cfg["msg_id"], cfg["from_chat"]),
                )
        for kw, resp in auto_replies.items():
            conn.execute(
                "INSERT OR REPLACE INTO auto_replies (keyword, response) VALUES (?,?)",
                (kw, resp),
            )
        for admin_id in db_admins:
            conn.execute("INSERT INTO admins (user_id) VALUES (?)", (admin_id,))
            if admin_id not in ADMIN_IDS:
                ADMIN_IDS.append(admin_id)

    set_setting("welcome_enabled", "1" if welcome_enabled else "0")
    set_setting("animations_enabled", "1" if animations_enabled else "0")
    set_setting("maintenance_mode", "1" if maintenance_mode else "0")
    set_setting("anim_style", anim_style)
    set_setting("user_menu_text", user_menu_text)
    set_setting("support_username", support_username)
    set_setting("force_channel", json.dumps(force_channels))
    set_setting("banner_config", json.dumps(banner_config))
    set_setting("click_stats", json.dumps(click_stats))
    return len(db_admins)


# ------------------ TWO-WAY CHAT & AUTO-REPLY ------------------
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def seamless_chat_handler(event):
    if event.sender_id in banned_users or event.sender_id in admin_chat_state:
        return

    text = event.raw_text.strip().lower() if event.raw_text else ""

    # Ignore admin commands & labels
    if text.startswith("/") or text in ADMIN_KB_LABELS:
        return
    # Ignore main user keyboard buttons
    if (
        "number hack" in text
        or "colour trading" in text
        or "contact support" in text
    ):
        return

    if event.sender_id not in ADMIN_IDS:
        if check_rate_limit(event.sender_id):
            return
        # --- USER TO ADMIN ---
        if user_chat_state.get(event.sender_id):
            bot_auto_replied = False
            for kw, resp in auto_replies.items():
                if kw in text:
                    try:
                        await client.send_message(event.sender_id, resp)
                        bot_auto_replied = True
                        break
                    except Exception:
                        pass

            user = await event.get_sender()
            name = user.first_name or "User"
            is_vip = user_meta.get(event.sender_id, {}).get("vip", 0)
            vip_tag = "┃ 🎖 **Tier:** `👑 DIAMOND VIP`\n" if is_vip else ""
            auto_tag = "┃ 🤖 **AI Status:** `Auto-Replied`\n" if bot_auto_replied else ""

            caption = (
                f"{ui_header('CONCIERGE INTERCEPT', 'INCOMING USER TRANSMISSION')}\n\n"
                f"┏━━━ **👤 SENDER DETAILS** ━━━┓\n"
                f"┃ 🏷 **From:** [{name}](tg://user?id={event.sender_id})\n"
                f"┃ 🆔 `{event.sender_id}`\n"
                f"{vip_tag}{auto_tag}"
                f"┗━━━━━━━━━━━━━━━━━━━━━━━━━┛"
            )

            if event.raw_text:
                caption += f"\n\n💬 **Message:**\n> {event.raw_text}"
            caption += "\n\n👇 *(Reply directly to this card or use quick actions)*"

            intercept_btns = [
                [
                    Button.inline(
                        "✉️ Quick Reply",
                        data=f"adm_quickdm_{event.sender_id}".encode(),
                    ),
                    Button.inline(
                        "🕵️ Dossier",
                        data=f"adm_dossier_{event.sender_id}".encode(),
                    ),
                ],
                [
                    Button.inline("🗑 Wipe Global", data=b"adm_wipemsg"),
                    Button.inline(
                        "🚫 Ban", data=f"adm_quickban_{event.sender_id}".encode()
                    ),
                ],
            ]

            sent_admin_msgs = []
            for admin_id in ADMIN_IDS:
                try:
                    sent_msg = await client.send_message(
                        admin_id, caption, file=event.media, buttons=intercept_btns
                    )
                    sent_admin_msgs.append((admin_id, sent_msg.id))
                except Exception:
                    pass

            if sent_admin_msgs:
                for adm_id, msg_id in sent_admin_msgs:
                    admin_msg_map[(adm_id, msg_id)] = sent_admin_msgs

            try:
                if not bot_auto_replied:
                    feedback_msg = await event.reply(
                        "📡 `Routing message to VIP Concierge...`"
                    )
                    await asyncio.sleep(0.4)
                    await feedback_msg.edit(
                        "✨ **Delivered to Executive Support!** *An admin will reply shortly.*"
                    )
                    await asyncio.sleep(2.5)
                    await feedback_msg.delete()
            except Exception:
                pass
        else:
            try:
                await event.delete()
            except Exception:
                pass
            open_sup_btn = [
                [Button.inline("💎 Open My VIP Lounge", data=b"usr_vip_back")]
            ]
            warning_msg = await event.respond(
                f"{ui_header('CONCIERGE LOCKED', 'DIRECT CHAT NOTICE')}\n\n"
                "🔒 **Direct messaging is currently in standby.**\n"
                "👉 *Tap the **'🎧 Contact Support'** button on your keyboard below to open an encrypted support line!*",
                buttons=open_sup_btn,
            )
            await asyncio.sleep(6)
            try:
                await warning_msg.delete()
            except Exception:
                pass
    else:
        # --- ADMIN TO USER ---
        if event.is_reply:
            replied_msg = await event.get_reply_message()
            replied_text = replied_msg.raw_text or ""

            match = re.search(r"🆔 `(\d+)`", replied_text)
            if match:
                target_uid = int(match.group(1))
                try:
                    access_hash = tracked_users.get(target_uid, 0)
                    peer = (
                        InputPeerUser(target_uid, access_hash)
                        if access_hash
                        else target_uid
                    )

                    if event.raw_text:
                        await client.send_message(
                            peer, event.raw_text, file=event.media
                        )
                    elif event.media:
                        await client.send_message(peer, file=event.media)

                    user_chat_state[target_uid] = True
                    admin_feedback = await event.reply("⚡ `Encrypting & dispatching...`")
                    await asyncio.sleep(0.3)
                    await admin_feedback.edit("✨ **Dispatched to User!**")
                    await asyncio.sleep(2)
                    try:
                        await admin_feedback.delete()
                    except Exception:
                        pass

                except UserIsBlockedError:
                    blocked_users.add(target_uid)
                    save_user(
                        target_uid, tracked_users.get(target_uid, 0), blocked=True
                    )
                    await event.reply(
                        "❌ `[Error] Transmission failed: User blocked the bot.`"
                    )
                except Exception as e:
                    await event.reply(f"❌ **Error:** `{e}`")


# ------------------ AUTO BACKUP (EVERY 6 HOURS & SEND TO ADMINS) ------------------
async def periodic_backup():
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            db_admins = [a for a in ADMIN_IDS if a not in ROOT_ADMINS]
            data = {
                "tracked": tracked_users,
                "blocked": list(blocked_users),
                "banned": list(banned_users),
                "join_dates": user_join_dates,
                "user_meta": {str(k): v for k, v in user_meta.items()},
                "messages": {str(k): v for k, v in saved_messages.items()},
                "button_forwards": button_forwards,
                "welcome": welcome_enabled,
                "animations_enabled": animations_enabled,
                "maintenance_mode": maintenance_mode,
                "anim_style": anim_style,
                "user_menu_text": user_menu_text,
                "support_username": support_username,
                "force_channel": json.dumps(force_channels),
                "banner_config": banner_config,
                "click_stats": click_stats,
                "auto_replies": auto_replies,
                "db_admins": db_admins,
            }
            file = "auto_backup.json"
            with open(file, "w") as f:
                json.dump(data, f)

            caption = (
                f"📁 **PROBOT-X 6-HOUR AUTO SNAPSHOT**\n"
                f"👥 **Peers:** `{len(tracked_users)}` | 👑 **Admins:** `{len(ADMIN_IDS)}`"
            )
            for admin_id in ROOT_ADMINS:
                try:
                    await client.send_file(admin_id, file, caption=caption)
                except Exception as e:
                    logger.error(
                        f"Failed to send periodic backup to admin {admin_id}: {e}"
                    )

            logger.info("Automatic 6-hour backup generated and sent to admins.")
        except Exception as e:
            logger.error(f"Periodic backup error: {e}")


# ------------------ MAIN ------------------
async def main():
    global bot_username_cache
    await client.start(bot_token=BOT_TOKEN)
    me = await client.get_me()
    bot_username_cache = getattr(me, "username", "") or "bot"
    init_db()
    load_from_db()
    await start_web()
    asyncio.create_task(periodic_backup())
    logger.info(
        f"ProBot-X v4.0 Luxury Edition (@{bot_username_cache}) is online..."
    )
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
