from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
import sqlite3, random, os, requests
from gtts import gTTS

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# 🧠 DATABASE
conn = sqlite3.connect("memory.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, last_message TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS score (user_id INTEGER PRIMARY KEY, points INTEGER)")
conn.commit()

# ⚠️ BAD WORDS
bad_words = ["sex","porn","xxx","nude","fuck","bitch","dick","pussy","rape","pm","dm","punda","sunni","potta","oombu","gommala","mairu", "thevidya","kiss","pvrt","ommala","ummbi","sappu"]
warnings = {}

# 🔮 WELCOME
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        await update.message.reply_text(
f"""🔮 Welcome to "乃un 乃utter ﾌam"
👤 Name: {user.first_name}
📛 Username: @{user.username if user.username else "No username"}
📜 Rules:
🚫 No PM / DM
🚫 Avoid bad words
⚠️ Follow rules"""
        )

# ⚠️ AUTO MOD
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    msg = update.message.text.lower()
    user = update.message.from_user
    user_id = user.id
    username = f"@{user.username}" if user.username else user.first_name

    for word in bad_words:
        if word in msg:
            try:
                await update.message.delete()
            except:
                pass

            warnings[user_id] = warnings.get(user_id, 0) + 1
            reason = "No PM/DM" if word in ["pm","dm"] else "Rule break"

            keyboard = [[InlineKeyboardButton("✅ Remove Warn", callback_data=f"unwarn_{user_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if warnings[user_id] >= 3:
                try:
                    await update.effective_chat.ban_member(user_id)
                    await update.message.reply_text(f"🚫 {username} banned\nReason: {reason}")
                except:
                    pass
            else:
                await update.message.reply_text(
                    f"⚠️ {username} warned ({warnings[user_id]}/3)\nReason: {reason}\nWord: {word}",
                    reply_markup=reply_markup
                )
            return

# 👑 REMOVE WARN
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split("_")[1])
    admin = await update.effective_chat.get_member(query.from_user.id)

    if admin.status not in ["administrator", "creator"]:
        await query.edit_message_text("❌ Only admin")
        return

    if warnings.get(user_id, 0) > 0:
        warnings[user_id] -= 1
        await query.edit_message_text("✅ Warning removed")

# 🤖 FREE AI (HUGGINGFACE)
async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    text = update.message.text

    if any('\u0b80' <= c <= '\u0bff' for c in text):
        lang = "Tamil"
    elif any(w in text.lower() for w in ["bro","da","machan","epdi"]):
        lang = "Tanglish"
    else:
        lang = "English"

    try:
        API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}

        prompt = f"Reply only in {lang}. Talk like a friend. Message: {text}"

        res = requests.post(API_URL, headers=headers, json={"inputs": prompt})
        result = res.json()

        reply = result[0]["generated_text"]
        await update.message.reply_text(reply)

    except:
        await update.message.reply_text("⚠️ AI busy, try later")

# 🎮 GAME
def add_points(uid, pts):
    cursor.execute("SELECT points FROM score WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE score SET points=? WHERE user_id=?", (row[0]+pts, uid))
    else:
        cursor.execute("INSERT INTO score VALUES (?,?)", (uid, pts))
    conn.commit()

async def dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    num = random.randint(1,6)
    uid = update.message.from_user.id
    add_points(uid, num)
    await update.message.reply_text(f"🎲 Dice: {num} (+{num} pts)")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT * FROM score ORDER BY points DESC LIMIT 5")
    rows = cursor.fetchall()
    text = "🏆 Leaderboard:\n"
    for i,r in enumerate(rows,1):
        text += f"{i}. {r[0]} - {r[1]} pts\n"
    await update.message.reply_text(text)

# 🔊 VOICE
async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tts = gTTS(update.message.text)
    tts.save("v.mp3")
    await update.message.reply_voice(voice=open("v.mp3","rb"))
    os.remove("v.mp3")

# 🚀 MAIN
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_message))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_reply))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(CommandHandler("dice", dice))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("voice", voice))

print("🔥 Bot Running...")
app.run_polling()