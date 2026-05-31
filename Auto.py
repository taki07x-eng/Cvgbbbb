import re
import asyncio
from pymongo import MongoClient
from telethon import TelegramClient, events, Button
from telethon.tl.functions.messages import EditMessageRequest
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.types import ChannelParticipantAdmin, ChannelParticipantCreator

# --- CONFIGURATION ---
API_ID = 29515073
API_HASH = "17a8c38ec658c363675e6ffdf5ce2a42"
BOT_TOKEN = "8863782692:AAGxCK2m0eud6PGf2-A6bNEjgoKV8jM-Azk" 
MONGO_URI = "mongodb+srv://Kittux07:Ujjalpandit07@cluster0.yjsv2gg.mongodb.net/?appName=Cluster0"
OWNER_ID = 8735285838

# --- INITIALIZATION ---
client = TelegramClient('UltimateAutoBot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
db = MongoClient(MONGO_URI)["Anime_Automation_DB"]
channels_col = db["channels_data"]
user_states = {} # State tracking for admin commands

# --- DEFAULT SETTINGS ---
DEFAULT_TEMPLATE = (
    "╭─❍ 「 𝗔𝗡𝗜𝗠𝗘 𝗨𝗣𝗗𝗔𝗧𝗘 」\n"
    "├ 🏷️ 𝗘𝗽𝗶𝘀𝗼𝗱𝗲 : {EP:02d} (S{SEASON:02d})\n"
    "├ 🎧 𝗟𝗮𝗻𝗴𝘂𝗮𝗴𝗲 : {LANG}\n"
    "├ 📀 𝗤𝘂𝗮𝗹𝗶𝘁𝘆 : {QUALITY}\n"
    "╰───────────────\n"
    "⚡ 𝗝𝗼𝗶𝗻 𝗢𝘂𝗿 𝗠𝗮𝗶𝗻 𝗖𝗵𝗮𝗻𝗻𝗲𝗹 ➥ {MAIN_CH}\n"
    "✨ 𝗣𝗼𝘄𝗲𝗿𝗲𝗱 𝗕𝘆 ➥ {POWERED}"
)

# --- DATABASE HELPERS ---
def get_ch_data(cid):
    data = channels_col.find_one({"chat_id": cid})
    if not data:
        data = {
            "chat_id": cid, "title": "Unknown", "season": 1, "episode": 1,
            "template": DEFAULT_TEMPLATE, "status": "ON", "pack_limit": 12,
            "main_ch": "@Anime_Hindi_Flixx", "powered": "@Hindi_Anime_Flix",
            "manual_override": None
        }
        channels_col.insert_one(data)
    return data

# --- SMART DETECTION ENGINE ---
def detect_info(text, fname):
    combined = f"{fname} {text}".lower()
    
    # Quality Detection
    quality = "1080p"
    if "4k" in combined or "2160" in combined: quality = "4K UHD"
    elif "1080" in combined: quality = "1080p"
    elif "720" in combined: quality = "720p"
    elif "480" in combined: quality = "480p"

    # Language Detection
    lang = "Hindi Dubbed"
    languages = []
    if "hindi" in combined: languages.append("Hindi")
    if "english" in combined: languages.append("English")
    if "tamil" in combined: languages.append("Tamil")
    if "telugu" in combined: languages.append("Telugu")
    if languages: lang = " | ".join(languages)

    # Episode Detection (Regex)
    ep_num = None
    match = re.search(r'(?:e|ep|episode|ep\.)\s?(\d+)', combined)
    if match: ep_num = int(match.group(1))

    return ep_num, quality, lang

# --- ADMIN PANEL (PRIVATE CHAT) ---

@client.on(events.NewMessage(pattern='/start', func=lambda e: e.is_private and e.sender_id == OWNER_ID))
async def main_menu(event):
    all_ch = list(channels_col.find())
    if not all_ch:
        return await event.reply("❌ No channels found. Use `/add -100xxxx` to register.")
    
    btns = [[Button.inline(f"📺 {c.get('title')}", f"manage_{c['chat_id']}")] for c in all_ch]
    await event.reply("🏠 **Main Menu - Select Channel**", buttons=btns)

@client.on(events.CallbackQuery(data=re.compile(b"manage_(.*)")))
async def channel_panel(event):
    cid = int(event.data_match.group(1).decode())
    ch = get_ch_data(cid)
    user_states[event.sender_id] = {"cid": cid}
    
    text = (f"⚙️ **Channel:** {ch['title']}\n\n"
            f"🎬 Season: `{ch['season']}`\n"
            f"📟 Episode: `{ch['episode']:02d}`\n"
            f"⚡ Status: `{ch['status']}`")
    
    btns = [
        [Button.inline("🎬 Set Season", b"set_s"), Button.inline("📟 Set Episode", b"set_e")],
        [Button.inline("➕ Ep +1", b"ep_inc"), Button.inline("➖ Ep -1", b"ep_dec")],
        [Button.inline("✏️ Edit Template", b"edit_temp"), Button.inline("👁 Preview", b"preview")],
        [Button.inline("🔙 Back", b"back_main")]
    ]
    await event.edit(text, buttons=btns)

# --- CALLBACK LOGIC ---

@client.on(events.CallbackQuery())
async def cb_handler(event):
    cid = user_states.get(event.sender_id, {}).get("cid")
    if not cid: return

    if event.data == b"ep_inc":
        ch = get_ch_data(cid)
        channels_col.update_one({"chat_id": cid}, {"$inc": {"episode": 1}})
        await event.answer("✅ Episode Incremented", alert=False)
        await channel_panel(event)

    elif event.data == b"preview":
        ch = get_ch_data(cid)
        cap = ch['template'].format(EP=ch['episode'], SEASON=ch['season'], QUALITY="1080p", LANG="Hindi", MAIN_CH=ch['main_ch'], POWERED=ch['powered'])
        await event.answer(f"Preview:\n\n{cap}", alert=True)

    elif event.data == b"back_main":
        await main_menu(event)

# --- AUTO CAPTION ENGINE (CHANNEL) ---

@client.on(events.NewMessage(incoming=True))
async def auto_caption_worker(event):
    if not event.is_channel or not (event.photo or event.video or event.document):
        return

    ch = channels_col.find_one({"chat_id": event.chat_id})
    if not ch or ch["status"] == "OFF": return

    # Metadata
    fname = ""
    if event.document:
        for attr in event.document.attributes:
            if hasattr(attr, 'file_name'): fname = attr.file_name
    
    cap_text = event.message.message or event.message.caption or ""
    
    # Priority Detection
    det_ep, det_quality, det_lang = detect_info(cap_text, fname)
    
    # Resolve Priority: 1. Manual -> 2. Filename/Caption -> 3. Last DB
    final_ep = ch['manual_override'] or det_ep or ch['episode']
    
    # Reset manual override after use
    if ch['manual_override']:
        channels_col.update_one({"chat_id": event.chat_id}, {"$set": {"manual_override": None}})

    # Format
    try:
        final_caption = ch['template'].format(
            EP=final_ep, SEASON=ch['season'], QUALITY=det_quality, 
            LANG=det_lang, MAIN_CH=ch['main_ch'], POWERED=ch['powered']
        )
        
        await client(EditMessageRequest(peer=event.chat_id, id=event.id, message=final_caption))
        
        # Auto-Increment logic (Only on 1080p/4K to avoid double count)
        if det_quality in ["1080p", "4K UHD"] and final_ep == ch['episode']:
            channels_col.update_one({"chat_id": event.chat_id}, {"$inc": {"episode": 1}})
            
    except Exception as e:
        print(f"Edit Error: {e}")

# --- SYSTEM COMMANDS ---

@client.on(events.NewMessage(pattern='/add (.*)', from_users=OWNER_ID))
async def add_channel(event):
    try:
        cid = int(event.pattern_match.group(1))
        entity = await client.get_entity(cid)
        channels_col.update_one({"chat_id": cid}, {"$set": {"chat_id": cid, "title": entity.title}}, upsert=True)
        await event.reply(f"✅ **{entity.title}** registered successfully!")
    except:
        await event.reply("❌ Error: Invalid ID or Bot is not admin.")

# --- START ---
print("Bot Online ✅ Multi-Channel Pro Dashboard Active")
client.run_until_disconnected()
