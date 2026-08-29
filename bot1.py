import telebot
import re
import unicodedata
import time
import datetime
import json
import os
import pymongo  
import random
import html
from telebot.types import ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv 


load_dotenv()

# ======================
# CONFIG (Environment Variables ကနေ ယူမယ်)
# ======================
TOKEN = os.getenv("TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS").split(",")]
DATA_FILE = os.getenv("DATA_FILE")
FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL")
MONGO_URI = os.getenv("MONGO_URI")

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")

# ======================
# DATABASE SETUP (MongoDB)
# ======================
client = pymongo.MongoClient(MONGO_URI)
db = client['bot_database']
brain_collection = db['brain']

def init_db():
    try:
        client.admin.command('ping')
        print("✅ MongoDB Connected Successfully!")
    except Exception as e:
        print(f"❌ MongoDB Connection Error: {e}")

# ======================
# DATA MANAGEMENT (JSON for Settings)
# ======================
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    
    data.setdefault("mute_time", 30)
    data.setdefault("strikes", {})
    data.setdefault("extra_words", [])
    data.setdefault("groups", [])
    data.setdefault("users", [])
    data.setdefault("reply_on", True)
    data.setdefault("reply_on_chats", {})
    data.setdefault("warning_text", None)
    data.setdefault("last_ts", {})
    return data

def save_data():
    data["groups"] = list(set(data.get("groups", [])))
    data["users"] = list(set(data.get("users", [])))
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

data = load_data()
BOT_START_TIME = int(time.time())

# ======================
# HELPER FUNCTIONS
# ======================
def is_joined(user_id):
    if user_id in ADMIN_IDS:
        return True
    try:
        member = bot.get_chat_member(FORCE_JOIN_CHANNEL, user_id)
        if member.status not in ['left', 'kicked']:
            return True
    except Exception as e:
        print(f"[DEBUG] force-join check error for user {user_id}: {e}")
    return False

# ======================
# DATABASE (Learning System) - MongoDB Version
# ======================
def save_to_brain(input_text, reply_text, sticker_id):
    try:
        query = {
            "input_text": input_text.lower().strip(), 
            "reply_text": reply_text, 
            "sticker_id": sticker_id
        }
        
        if not brain_collection.find_one(query):
            brain_collection.insert_one(query)
            print(f"✅ အဖြေအသစ် တိုးမှတ်သားပြီး: {input_text} -> {reply_text if reply_text else 'Sticker'}")
    except Exception as e:
        print(f"⚠️ save_to_brain error: {e}")

def get_reply(text):
    if not text:
        return None, None
        
    user_input = text.lower().strip()
    
    try:
        results = list(brain_collection.find({"input_text": user_input}))
        if results:
            chosen = random.choice(results)
            print(f"🎯 Found {len(results)} replies for '{user_input}', chose one randomly.")
            return chosen.get("reply_text"), chosen.get("sticker_id")
            
        return None, None
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None, None

# ======================
# UTILS & BUTTONS
# ======================
def is_clean_text(text):
    if not text: return False
    if len(text) < 1 or len(text) > 150: 
        return False
    if re.search(r'http[s]?://', text) or '@' in text: 
        return False
    return True

def mention(user):
    return f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"

def strike_key(chat_id, user_id):
    return f"{chat_id}:{user_id}"

def is_admin(chat_id, user_id):
    try:
        if user_id in ADMIN_IDS: return True
        admins = bot.get_chat_administrators(chat_id)
        return any(a.user.id == user_id for a in admins)
    except: return False

def parse_time(text):
    unit = text[-1].lower()
    try:
        if unit == 's': return int(text[:-1])
        if unit == 'm': return int(text[:-1]) * 60
        if unit == 'h': return int(text[:-1]) * 3600
        if unit == 'd': return int(text[:-1]) * 86400
        return int(text)
    except: return None

def main_buttons():
    kb = InlineKeyboardMarkup()
    kb.add(
         InlineKeyboardButton(
            "➕Add To Your Group ထည့်သွင်းရန်",
            url=f"https://t.me/{BOT_USERNAME}?startgroup=s&delete_message+manage_video_chats_message+invite_users")
          )
    kb.row(    
         InlineKeyboardButton("𝗢𝗪𝗡𝗘𝗥", url="http://t.me/LeyoxYan_Yan"),
         InlineKeyboardButton(" စကားပြော ", url="https://t.me/+CF-kTfbq6MhmZGM1")
          )
    kb.row(  
        InlineKeyboardButton("Botပြုလုပ်လိုပါက", url="tg://resolve?domain=LeyoxYan_Yan&text=Botအသစ်လုပ်ချင်လို့ပါ"),
        InlineKeyboardButton("UPDATE", url="https://t.me/NoLoveMusicUpate")
          )
    return kb

# ======================
# CALLBACK HANDLERS
# ======================
@bot.callback_query_handler(func=lambda call: call.data.startswith("unmute:"))
def handle_unmute(call):
    chat_id = call.message.chat.id
    if not is_admin(chat_id, call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Admin များသာ Unmute လုပ်နိုင်ပါသည်။", show_alert=True)
        return
    
    target_id = int(call.data.split(":")[1])
    try:
        bot.restrict_chat_member(chat_id, target_id, 
            permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True))
        bot.edit_message_text(f"✅ {mention(call.from_user)} မှ User ကို Unmute လုပ်ပေးလိုက်ပါပြီ။", chat_id, call.message.message_id)
    except Exception as e:
        bot.answer_callback_query(call.id, f"Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "toggle_reply")
def toggle_reply_callback(call):
    chat_id = call.message.chat.id
    if not is_admin(chat_id, call.from_user.id):
        return bot.answer_callback_query(call.id, "❌ Admin များသာ လုပ်ဆောင်နိုင်ပါသည်။", show_alert=True)

    key = str(chat_id)
    current = data.get("reply_on_chats", {}).get(key, data.get("reply_on", True))
    new_status = not current
    data.setdefault("reply_on_chats", {})[key] = new_status
    save_data()

    btn_text = "🟢 Bot စာပြန်ခြင်း: ON" if new_status else "🔴 Bot စာပြန်ခြင်း: OFF"
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton(btn_text, callback_data="toggle_reply"))

    try:
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=kb)
    except Exception:
        pass
    bot.answer_callback_query(call.id, f"Bot စာပြန်ခြင်းကို {'ဖွင့်' if new_status else 'ပိတ်'} လိုက်ပါပြီ။")        

# ======================
# ADMIN CONFIG COMMANDS
# ======================
@bot.message_handler(commands=["setmute"])
def set_mute_time(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    
    if message.chat.type == "private":
        if user_id not in ADMIN_IDS: return
    else:
        try:
            member = bot.get_chat_member(chat_id, user_id)
            is_group_admin = member.status in ["administrator", "creator"]
            if not is_group_admin and user_id not in ADMIN_IDS:
                return bot.reply_to(message, "❌ ဒီ command ကို Group Admin များသာ သုံးနိုင်ပါတယ်။")
        except Exception as e:
            print(f"Error checking admin status: {e}")
            return

    args = message.text.split()
    if len(args) < 2:
        return bot.reply_to(message, "Usage: /setmute 30s (or 5m, 1d)")
    
    seconds = parse_time(args[1])
    if seconds is not None:
        if seconds < 30:
            return bot.reply_to(message, "⚠️ Telegram စည်းကမ်းအရ Mute time ကို အနည်းဆုံး 30s ထားပေးရပါမယ်။")
        
        if "group_mute_times" not in data:
            data["group_mute_times"] = {}
        
        data["group_mute_times"][str(chat_id)] = seconds
        save_data()
        bot.reply_to(message, f"✅ ဒီ Group အတွက် Mute time ကို {args[1]} ({seconds} seconds) အဖြစ် သတ်မှတ်လိုက်ပါပြီ။")
    else:
        bot.reply_to(message, "❌ Invalid format! Use: 30s, 5m, or 1h")

@bot.message_handler(commands=["addword"])
def add_word(message):
    if message.chat.type != "private" or message.from_user.id not in ADMIN_IDS:
        return
    raw = message.text.replace("/addword", "").strip()
    if not raw:
        return bot.reply_to(message, "Usage: /addword <word>")
    norm = _normalize_text_for_match(raw)
    if not norm or len(norm) < 1:
        return bot.reply_to(message, "⚠️ စကားလုံး အနည်းဆုံး 2 လုံး ရှိရပါမည်။")
    if norm and norm not in data.get("extra_words", []):
        data.setdefault("extra_words", []).append(norm)
        save_data()
        bot.reply_to(message, f"✅ Added to global ban list: {raw}")
    else:
        bot.reply_to(message, f"ℹ️ '{raw}' already in global ban list.")

@bot.message_handler(commands=["setwarn"])
def set_warning_text(message):
    if not is_admin(message.chat.id, message.from_user.id):
        return bot.reply_to(message, "❌ Admins only.")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return bot.reply_to(message, "Usage: /setwarn <warning message>")
    data["warning_text"] = parts[1].strip()
    save_data()
    bot.reply_to(message, "✅ Warning text updated.")

@bot.message_handler(commands=["setword"])
def set_chat_word(message):
    if message.chat.type not in ["group", "supergroup"]:
        return
    if not is_admin(message.chat.id, message.from_user.id):
        return bot.reply_to(message, "❌ Admins only")
    raw = message.text.replace("/setword", "").strip()
    if not raw:
        return bot.reply_to(message, "Usage: /setword <word>")
    norm = _normalize_text_for_match(raw)
    if not norm or len(norm) < 2:
        return bot.reply_to(message, "⚠️ စကားလုံး အနည်းဆုံး 2 လုံး ရှိရပါမည်။")
    lst = data.setdefault("chat_words", {}).setdefault(str(message.chat.id), [])
    if norm not in lst:
        lst.append(norm)
        save_data()
        bot.reply_to(message, f"✅ Added '{raw}' to this chat's ban list.")
    else:
        bot.reply_to(message, f"ℹ️ '{raw}' already in this chat's ban list.")

@bot.message_handler(commands=["getwarn"])
def get_warning_text(message):
    if not is_admin(message.chat.id, message.from_user.id):
        return
    warn = data.get("warning_text") or "(default message)"
    bot.reply_to(message, f"Current warning text:\n{warn}")

@bot.message_handler(commands=["delword"])
def del_word(message):
    chat_id = message.chat.id
    if message.chat.type == "private":
        if message.from_user.id not in ADMIN_IDS:
            return
        target = data.setdefault("extra_words", [])
    else:
        if not is_admin(chat_id, message.from_user.id):
            return
        target = data.setdefault("chat_words", {}).setdefault(str(chat_id), [])

    raw = message.text.replace("/delword", "").strip()
    if not raw:
        return bot.reply_to(message, "Usage: /delword <word>")
    norm = _normalize_text_for_match(raw)
    if norm in target:
        target.remove(norm)
        save_data()
        bot.reply_to(message, f"✅ Removed from ban list: {raw}")
    else:
        bot.reply_to(message, "❌ Word not found in list.")

@bot.message_handler(commands=["list"])
def list_brain(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    if message.chat.type not in ["private", "group", "supergroup"]:
        return

    args = message.text.split(maxsplit=1)
    mode = args[1].strip().lower() if len(args) > 1 else "words"

    if message.reply_to_message and message.reply_to_message.sticker:
        sticker_id = message.reply_to_message.sticker.file_id
        try:
            results = list(brain_collection.find({"sticker_id": sticker_id}, {"_id": 1, "input_text": 1}))
        except Exception as e:
            print(f"Error fetching sticker entries: {e}")
            results = []

        if results:
            safe_sticker = html.escape(sticker_id)
            msg = f"<b>🎯 Sticker ID:</b>\n<code>{safe_sticker}</code>\n\n<b>ဒီ sticker မှတ်ထားတွေ:</b>\n"
            for doc in results:
                input_text = doc.get("input_text")
                safe_input = html.escape(input_text[:50]) if input_text else ""
                msg += f"• <code>{safe_input}</code>\n"
            msg += f"\n✂️ ဖျက်ချိုင်း: /d {safe_sticker}"
            bot.send_message(message.chat.id, msg, parse_mode="HTML", reply_to_message_id=message.message_id)
            return
        else:
            bot.send_message(message.chat.id, "ဒီ sticker မှတ်ထားတွေ မရှိပါ။", reply_to_message_id=message.message_id)
            return

    if mode == "brain":
        try:
            all_entries = list(brain_collection.find({}))
        except Exception as e:
            print(f"Error fetching brain entries: {e}")
            all_entries = []

        if not all_entries:
            bot.send_message(message.chat.id, "❌ မှတ်ဉာဏ်မှာ ဘာမျှ မရှိသေးပါ။", reply_to_message_id=message.message_id)
            return

        msg = f"<b>📚 မှတ်ဉာဏ်ရှိတဲ့ Entries ({len(all_entries)})</b>\n\n"
        for idx, doc in enumerate(all_entries, 1):
            input_text = doc.get("input_text")
            reply_text = doc.get("reply_text")
            sticker_id = doc.get("sticker_id")
            safe_input = html.escape(input_text[:40]) if input_text else ""
            if sticker_id:
                msg += f"<b>{idx}.</b> 📌 <code>{safe_input}</code>\n   ➜ 🎭 Sticker\n\n"
            else:
                reply_preview = html.escape(reply_text[:35]) if reply_text else "[Empty]"
                msg += f"<b>{idx}.</b> 💬 <code>{safe_input}</code>\n   ➜ {reply_preview}\n\n"
            if len(msg) > 3500:
                try:
                    bot.send_message(message.chat.id, msg, parse_mode="HTML", reply_to_message_id=message.message_id)
                except Exception as e:
                    print(f"[DEBUG] Error sending list: {e}")
                msg = ""

        help_msg = "\n<b>🗑️ ဖျတ်ချချန် နည်းလမ်း:</b>\n/d 1  -  /d hello  -  Sticker ➜ reply then /list"
        bot.send_message(message.chat.id, (msg + help_msg) if msg else help_msg, parse_mode="HTML", reply_to_message_id=message.message_id)
        return

    gw = data.get("extra_words", [])
    cw = data.get("chat_words", {}).get(str(message.chat.id), [])

    msg = f"<b>📋 Ban Words</b>\n\n"
    msg += f"<b>Global ({len(gw)}):</b>\n"
    msg += "".join([f"• <code>{html.escape(w)}</code>\n" for w in gw]) if gw else "(No global ban words)\n"
    msg += f"\n<b>This chat ({len(cw)}):</b>\n"
    msg += "".join([f"• <code>{html.escape(w)}</code>\n" for w in cw]) if cw else "(No chat-specific ban words)\n"
    msg += "\n<b>Use:</b> /addword <word> (owner private), /setword <word> (group admin), /delword <word>\n"
    msg += "To view saved replies: /list brain"

    bot.send_message(message.chat.id, msg, parse_mode="HTML", reply_to_message_id=message.message_id)

@bot.message_handler(commands=["d"])
def delete_brain_entry(message):
    if message.chat.type not in ["private", "group", "supergroup"]:
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return bot.reply_to(message, "သုံးပုံ:\n/d နံပါတ် - /d 1\n/d စာလုံး - /d hello\n/d sticker_id - /d CAACAgIA...")
    target = args[1].strip()
    
    deleted = 0
    try:
        all_docs = list(brain_collection.find({}))
        index = int(target)
        if 1 <= index <= len(all_docs):
            doc = all_docs[index - 1]
            result = brain_collection.delete_one({"_id": doc["_id"]})
            deleted = result.deleted_count
        if deleted:
            bot.reply_to(message, f"✅ Entry #{index} ကို ဖျက်ပြီးပါပြီ။")
        else:
            bot.reply_to(message, f"❌ Entry #{index} မတွေ့ပါ။")
        return
    except ValueError:
        pass
    
    target_lower = target.lower()
    try:
        result = brain_collection.delete_many({"$or": [{"input_text": target_lower}, {"sticker_id": target}]})
        deleted = result.deleted_count
    except Exception as e:
        print(f"Error deleting: {e}")
        deleted = 0
    
    if deleted:
        bot.reply_to(message, f"✅ မှတ်ဉာဏ်ထဲက '{target}' ကို ဖျက်ပြီးပါပြီ။ ({deleted} entry)")
    else:
        bot.reply_to(message, f"❌ '{target}' ဆိုတာ မတွေ့ပါ။")

@bot.message_handler(commands=["rp"])
def reply_toggle(message):
    chat_id = message.chat.id
    if not is_admin(chat_id, message.from_user.id):
        return bot.reply_to(message, "❌ Admin များသာ ဤ Setting ကို ပြောင်းလဲနိုင်ပါသည်။")
    
    current_status = data.get("reply_on_chats", {}).get(str(chat_id), True)
    new_status = not current_status
    
    data.setdefault("reply_on_chats", {})[str(chat_id)] = new_status
    save_data()
    
    kb = InlineKeyboardMarkup()
    btn_text = "🟢 Bot စာပြန်ခြင်း: ON" if new_status else "🔴 Bot စာပြန်ခြင်း: OFF"
    kb.add(InlineKeyboardButton(btn_text, callback_data="toggle_reply"))
    
    bot.send_message(chat_id, f"<tg-emoji emoji-id='5251299553239398548'>🤖</tg-emoji> <b>Bot စာပြန်ခြင်း စနစ်ကို {'ဖွင့်' if new_status else 'ပိတ်'} လိုက်ပါပြီ།</b>\n\n{btn_text}", 
                     reply_markup=kb, parse_mode="HTML")        

@bot.message_handler(commands=["id"])
def show_chat_id(message):
    bot.reply_to(message, f"Chat ID: {message.chat.id}")

@bot.message_handler(commands=["astk"])
def delete_all_sticker_memory(message):
    if message.from_user.id not in ADMIN_IDS:
        return bot.reply_to(message, "❌ ဒီ command ကို Bot Owner သာ အသုံးပြုနိုင်ပါသည်။")

    try:
        result = brain_collection.delete_many({"sticker_id": {"$ne": None, "$ne": ""}})
        bot.reply_to(message, f"✅ Sticker memory များကို ဖျက်ပြီးပါပြီ — {result.deleted_count} entries ဖျက်ပြီးပါပြီ။")
    except Exception as e:
        bot.reply_to(message, f"❌ ဖျက်ပေးစရာအမှားတက်ပါသည်: {e}")

# ======================
# BROADCAST & GROUP MANAGEMENT
# ======================
@bot.message_handler(commands=["broadcast"])
def broadcast(message):
    if message.from_user.id not in ADMIN_IDS:
        return bot.reply_to(message, "❌ ဒီ Command ကို Bot Owner သာ သုံးနိုင်ပါတယ်။")
    
    if not message.reply_to_message:
        return bot.reply_to(message, "⚠️ Broadcast ပို့ချင်တဲ့ Message ကို <b>Reply</b> ထောက်ပြီးမှ ဒီ command ကို သုံးပေးပါ။", parse_mode="HTML")

    target_msg = message.reply_to_message
    all_targets = list(set(data.get("groups", []) + data.get("users", [])))
    
    if not all_targets:
        return bot.reply_to(message, "⚠️ ပို့စရာ Target မရှိသေးပါဘူး။")

    status_msg = bot.reply_to(message, f"🚀 စုစုပေါင်း {len(all_targets)} နေရာကို ပို့နေပါပြီ...")
    success, fail = 0, 0

    for tid in all_targets:
        try:
            bot.forward_message(
                chat_id=tid, 
                from_chat_id=message.chat.id, 
                message_id=target_msg.message_id
            )
            success += 1
            time.sleep(0.1)
        except Exception as e:
            print(f"Broadcast failed for {tid}: {e}")
            fail += 1

    bot.edit_message_text(
        f"✅ <b>Broadcast ပို့ပြီးပါပြီ!</b>\n\n🟢 အောင်မြင်: {success}\n🔴 ကျရှုံး: {fail}",
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        parse_mode="HTML"
    )

@bot.message_handler(commands=["delgp"])
def del_group(message):
    if message.from_user.id not in ADMIN_IDS:
        return bot.reply_to(message, "❌ Only the bot owner can remove groups.")

    parts = message.text.split()
    if len(parts) == 1:
        gid = message.chat.id
    elif len(parts) == 2:
        try:
            gid = int(parts[1])
        except ValueError:
            return bot.reply_to(message, "⚠️ Chat ID က ကိန်းဂဏန်း ဖြစ်ရပါမယ်။")
    else:
        return bot.reply_to(message, "Usage: /delgp သို့မဟုတ် /delgp <chat_id>")

    if gid not in data.get("groups", []):
        return bot.reply_to(message, "ℹ️ ဒီ Group က စာရင်းထဲမှာ မရှိပါဘူး။")

    data["groups"].remove(gid)
    if str(gid) in data.get("reply_on_chats", {}):
        del data["reply_on_chats"][str(gid)]
    
    save_data()
    bot.reply_to(message, f"✅ Group {gid} ကို စာရင်းထဲကနေ ဖယ်ထုတ်လိုက်ပါပြီ။")

# ======================
# START & HELP
# ======================
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    
    if message.chat.type == "private":
        if message.chat.id not in data["users"]:
            data["users"].append(message.chat.id)
            save_data()

        if not is_joined(user_id):
            join_kb = InlineKeyboardMarkup()
            clean_channel = FORCE_JOIN_CHANNEL.replace('@', '')
            join_kb.add(InlineKeyboardButton("Channal Join ပေးပါ", url=f"https://t.me/{clean_channel}"))
            join_kb.add(InlineKeyboardButton("🔄  (စစ်ဆေးမည်)", url=f"https://t.me/{BOT_USERNAME}?start=start"))
            
            return bot.send_message(
                message.chat.id, 
                "<tg-emoji emoji-id='6269316311172518259'>❌</tg-emoji> <b>အသုံးပြုခွင့်မရှိသေးပါ!</b> <tg-emoji emoji-id='6257780484281997093'>❌</tg-emoji>\n\nဒီ Bot ကို သုံးဖို့အတွက် Group ကို အရင် Join ပေးရပါမယ်။",
                reply_markup=join_kb
            )

    bot.send_message(
        message.chat.id, 
        "<tg-emoji tg-emoji='5251299553239398548'>🤖</tg-emoji> Active!\n\n"
        "<tg-emoji emoji-id='5240241223632954241'>🚫</tg-emoji> Bio / Join / Link spam auto delete\n"
        "<tg-emoji emoji-id='6271786398404055377'>⚠️</tg-emoji> 3 Warnings = Auto Mute\n\n"
        "<tg-emoji emoji-id='5226945370684140473'>➕</tg-emoji> Bot ကို Group ထဲထည့်ပြီး Admin ပေးထားပါ။",
        reply_markup=main_buttons()
    )

@bot.message_handler(commands=["help"]) 
def help_command(message):
    help_text = (
        "👋 Owner အတွက် အသုံးပြုနိုင်သော Command များ-\n"
        "/setmute\n /addword (global)\n /delword (global)\n /broadcast\n /list\n"
        "/setwarn [message]\n /getwarn\n"
        "Group admins: /setword [word]\n /delword [word]\n"
    )
    if message.from_user.id in ADMIN_IDS:
        try:
            bot.send_message(message.from_user.id, help_text)
            bot.reply_to(message, "✅ Owner help sent privately.")
        except Exception:
            bot.reply_to(message, help_text)
    else:
        bot.reply_to(message, "❌ ဒီ Command ကို Bot Owner သာ သုံးနိုင်ပါတယ်။")

# ======================
# MESSAGE GUARD & LEARNING
# ======================
BASE_PATTERNS = [
    r"b[\W_]*i[\W_]*o",
    r"j[\W_]*o[\W_]*i[\W_]*n",
    r"t[\W_]*\.?[\W_]*m[\W_]*e",
    r"http",
    r"www",
    r"link",
    r"ဂျိုင်း",
    r"ဂျိုင်း[\s\S]*လင့်|ဂျိုင်း[\s\S]*လင့်|ဂျိုင်း[\s\S]*လင်ခ်",
    r"လင့်ခ်|လင့်|လင့်|လင်ခ်",
    r"ဘိုင်[\W_]*အို",
    r"ဘိုင်ယို"
]

PATTERN_NAMES = {
    0: "bio_en", 1: "join_en", 2: "telegram", 3: "http", 4: "www",
    5: "link_en", 6: "join_mm", 7: "join_mm_link_combo", 8: "link_mm",
    9: "bio_mm", 10: "bio_mm_alt"
}

def _normalize_text_for_match(s: str) -> str:
    if not s: return s
    nk = unicodedata.normalize('NFKC', s).lower()
    return ''.join(c for c in unicodedata.normalize('NFKD', nk) if not unicodedata.category(c).startswith('M'))

def matches_word_in_text(word: str, text: str) -> bool:
    if not word or not text: return False
    pattern = r'\b' + re.escape(word) + r'\b'
    return bool(re.search(pattern, text, flags=re.UNICODE))

def strip_accents(s: str) -> str:
    nkfd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nkfd if not unicodedata.category(c).startswith('M'))

def detect_reason(text):
    if not text: return "spam"
    try:
        t = strip_accents(unicodedata.normalize("NFKC", text).lower())
        for idx, pattern in enumerate(BASE_PATTERNS):
            if re.search(pattern, t):
                return PATTERN_NAMES.get(idx, "spam")
        for word in data.get("extra_words", []):
            if matches_word_in_text(word.lower(), t):
                return word
    except: pass
    return "spam"

@bot.message_handler(content_types=["new_chat_members"])
def welcome_group(message):
    try:
        if message.new_chat_members:
            for user in message.new_chat_members:
                if user.id == bot.get_me().id:
                    msg = "<tg-emoji emoji-id='5251299553239398548'>🤖</tg-emoji> <b>𝙼𝚢𝚊𝚗𝚖𝚊𝚛 𝙵𝚛𝚒𝚎𝚗𝚍 Bot Active!</b>\n\nကျွန်တော်ကို Admin ပေးထားဖို့ မမေ့ပါနဲ့ဗျာ။"
                    bot.send_message(message.chat.id, msg, reply_markup=main_buttons())
    except Exception as e:
        print(f"❌ Error in welcome_group: {e}")

@bot.message_handler(content_types=["text", "photo", "sticker", "story", "video", "animation"])
def handle_all(message):
    # Time Filter Check
    if hasattr(message, 'date'):
        msg_ts = message.date
        if isinstance(msg_ts, datetime.datetime):
            msg_ts = int(msg_ts.timestamp())
        try:
            msg_ts = int(msg_ts)
        except:
            msg_ts = None
            
        if msg_ts is not None:
            if msg_ts < BOT_START_TIME:
                return
            chat_key = str(message.chat.id)
            if "last_ts" not in data: data["last_ts"] = {}
            last = data.get("last_ts", {}).get(chat_key, 0)
            if msg_ts <= last:
                return
            data["last_ts"][chat_key] = msg_ts

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Auto Register Group
    if message.chat.type in ["group", "supergroup"]:
        if chat_id not in data.get("groups", []):
            data.setdefault("groups", []).append(chat_id)
            data.setdefault("reply_on_chats", {})[str(chat_id)] = False 
            save_data()

    # Commands Filter
    if message.content_type == 'text' and message.text and message.text.startswith('/'):
        return

    # Private force join check
    if message.chat.type == "private" and user_id not in ADMIN_IDS:
        if not is_joined(user_id):
            join_kb = InlineKeyboardMarkup()
            clean_channel = FORCE_JOIN_CHANNEL.replace('@', '')
            join_kb.add(InlineKeyboardButton(" Channel join", url=f"https://t.me/{clean_channel}"))
            join_kb.add(InlineKeyboardButton(" Join (စစ်ဆေးမည်)", url=f"https://t.me/{BOT_USERNAME}?start=start"))
            return bot.send_message(
                message.chat.id,
                "<tg-emoji emoji-id='6257780484281997093'>❌</tg-emoji> <b>အသုံးပြုခွင့်မရှိသေးပါ!</b>\n\nဒီ Bot ကို သုံးဖို့အတွက် Group ကို အရင် Join ပေးရပါမယ်။",
                reply_markup=join_kb
            )

    # 1. Guard System (Story / Forward Filter)
    is_story = (message.content_type == 'story')
    is_forwarded = bool(message.forward_from or message.forward_from_chat or message.forward_sender_name)

    if is_story or is_forwarded:
        if not is_admin(chat_id, user_id):
            try:
                bot.delete_message(chat_id, message.message_id)
            except Exception as e:
                print(f"❌ Failed to delete message: {e}")
                return

            warn_text = "⚠️ <b>သတိပေးချက်</b>\n\n"
            warn_text += "Story ပို့ခြင်းများကို ခွင့်မပြုပါ။\n" if is_story else "forwarded message များကို ခွင့်မပြုပါ။\n"
            if message.from_user:
                warn_text += f"👤 User: {mention(message.from_user)}"
            bot.send_message(chat_id, warn_text, parse_mode="HTML")
            return

    check_text = message.text if message.text else message.caption
    norm_text = strip_accents(unicodedata.normalize('NFKC', check_text).lower()) if check_text else ""

    # Non-admin bot spam check
    is_bot_sender = getattr(message.from_user, 'is_bot', False) or (message.from_user.username and message.from_user.username.lower().endswith('bot'))
    has_link = any(kw in check_text.lower() for kw in ['http', 't.me/', 'www']) if check_text else False
    is_long_text = len(check_text) > 50 if check_text else False
    
    if is_bot_sender and (has_link or is_long_text):
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception as e:
            print(f"⚠️ Failed to delete bot message: {e}")
        bot.send_message(chat_id, f"⚠️ အက်မင်မဟုတ်တဲ့ ဘော့မှ စာများ ပို့ခြင်းကို ခွင့်မပြုပါ။\n\n👤 Bot: {mention(message.from_user)}")
        return
    
    found = False
    matched_chat_word = None
    if check_text:
        if any(re.search(p, norm_text) for p in BASE_PATTERNS):
            found = True
        if not found:
            for w in data.get("extra_words", []):
                if matches_word_in_text(w, norm_text):
                    found = True
                    break
        if not found:
            cw = data.get("chat_words", {}).get(str(chat_id), [])
            for w in cw:
                if matches_word_in_text(w, norm_text):
                    found = True
                    matched_chat_word = w
                    break
    
    if found or is_forwarded:
        if not is_admin(chat_id, user_id):
            warn_msg = f"⚠️ သင့်စာထဲတွင် Group မှပိတ်ပင်ထားသော စကားပါနေသည်။ ({matched_chat_word})" if matched_chat_word else (data.get("warning_text") or "⚠️ သတိပေးချက်: သင့်စာသားတွင် ဂျိုင်း/ဘိုင်အို/လင့် ထဲတွင် တစ်ခုခုပါသည်။")
            bot.send_message(chat_id, warn_msg)
            
            reason = "forward" if is_forwarded else detect_reason(check_text)
            key = strike_key(chat_id, user_id)
            strikes = data["strikes"].get(key, 0) + 1
            data["strikes"][key] = strikes
            save_data()
            
            if strikes >= 3:
                current_mute_duration = data.get("group_mute_times", {}).get(str(chat_id), data.get("mute_time", 60))
                until_date = int(time.time()) + current_mute_duration
                try:
                    bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(), until_date=until_date)
                except Exception as e: 
                    print(f"❌ Failed to mute user {user_id}: {e}")
                
                kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🔓 Unmute", callback_data=f"unmute:{user_id}"))
                bot.send_message(
                    chat_id,
                    f"❌ <b>Auto Mute</b> ❌\n\n"
                    f"<blockquote>"
                    f"👤 <b>User:</b> {mention(message.from_user)}\n"
                    f"ℹ️ <b>အကြောင်းပြချက်:</b> (ဘိုင်အို/ဂျိုင်း/လင့်) ၃ ကြိမ်ပို့ခြင်း\n"
                    f"⏱️ <b>ကြာချိန်:</b> {current_mute_duration} စက္ကန့်\n\n"
                    f"⏳ သတ်မှတ်ချိန်ပြည့်ပါက အလိုအလျောက် Unmute ဖြစ်ပါမည်။"
                    f"</blockquote>",
                    reply_markup=kb, parse_mode="HTML"
                )
                data["strikes"][key] = 0
                save_data()
            else:
                bot.send_message(
                    chat_id,
                    f"❌ <b>သတိပေးချက် ({strikes}/3)</b> ❌\n\n"
                    f"<blockquote>"
                    f"👤 User: {mention(message.from_user)}\n"
                    f"🚫 (ဘိုင်အို / ဂျိုင်း / လင့်) ဆိုင်ရာ စာသားများ ပို့ခြင်းကို ခွင့်မပြုပါ။\n\n"
                    f"⚠️ ၃ ကြိမ် ပြုလုပ်ပါက Auto mute ဖြစ်ပါမည်။"
                    f"</blockquote>", parse_mode="HTML"
                )
            try: 
                bot.delete_message(chat_id, message.message_id)
            except Exception as e: 
                print(f"⚠️ Failed to delete message: {e}")
            return
        else:
            return

    # 2. Learning System
    if message.reply_to_message:
        if message.reply_to_message.content_type == 'sticker':
            parent = message.reply_to_message.sticker.file_id
        else:
            parent = message.reply_to_message.text.strip().lower() if message.reply_to_message.text else None

        if parent:
            if message.content_type == 'sticker':
                reply_sticker_id = message.sticker.file_id
                try:
                    brain_collection.insert_one({
                        "input_text": parent, 
                        "reply_text": None, 
                        "sticker_id": reply_sticker_id
                    })
                except Exception as e:
                    print(f"⚠️ Error saving sticker-to-sticker: {e}")
                return

            elif message.content_type == 'text':
                current_reply = message.html_text 
                if is_clean_text(current_reply):
                    save_to_brain(parent, current_reply, None)
                    return

    # 3. Chat Auto-Reply
    if not message.text or not message.text.startswith("/"):
        user_input = message.sticker.file_id if message.content_type == 'sticker' else (message.text.lower() if message.text else None)
        chat_key = str(chat_id)
        chat_reply_on = data.get("reply_on_chats", {}).get(chat_key, True)

        if user_input and chat_reply_on:
            reply_text, sticker_id = get_reply(user_input)
            try:
                if sticker_id:
                    bot.send_sticker(chat_id, sticker_id, reply_to_message_id=message.message_id)
                elif reply_text:
                    bot.reply_to(message, reply_text, parse_mode=None)
            except Exception as e:
                print(f"⚠️ Reply send error: {e}")

# ======================
# BOT RUNNER
# ======================
if __name__ == '__main__':
    init_db()
    print("🤖 Dating Bot is starting...")
    while True:
        try:
            print("🚀 Bot is now online.")
            bot.infinity_polling(timeout=90, long_polling_timeout=20, skip_pending=True)
        except Exception as e:
            print(f"⚠️ Connection Error: {e}")
            time.sleep(5)
