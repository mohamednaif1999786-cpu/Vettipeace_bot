# mybot.py
import os
import asyncio
import sqlite3
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import openai
from gtts import gTTS

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QUIZ_INTERVAL = int(os.getenv("QUIZ_INTERVAL", 600))
openai.api_key = OPENAI_API_KEY

# SQLite storage
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS warns (user_id INTEGER PRIMARY KEY, username TEXT, warn_count INTEGER, reason TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS points (user_id INTEGER PRIMARY KEY, username TEXT, points INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS quiz (question TEXT, answer TEXT, active INTEGER)")
conn.commit()

BAD_WORDS = ["sex","porn","xxx","nude","fuck","ass","bitch","dick","pussy","rape","pm","dm","private chat","private message","direct chat","direct message","potta","sunni","oombu","ummbi","pvrt","inbox","thaniya","gommala","ommala","sappu","thayoli","thayali","thevidya","punda","thevudiya"]

# Helper functions
def get_warn(user_id):
    cursor.execute("SELECT warn_count FROM warns WHERE user_id=?", (user_id,))
    r = cursor.fetchone()
    return r[0] if r else 0

def add_warn(user_id, username, reason):
    count = get_warn(user_id) + 1
    cursor.execute("INSERT INTO warns(user_id, username, warn_count, reason) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET warn_count=?, reason=?", (user_id, username, count, reason, count, reason))
    conn.commit()
    return count

def remove_warn(user_id):
    cursor.execute("UPDATE warns SET warn_count=warn_count-1 WHERE user_id=? AND warn_count>0", (user_id,))
    conn.commit()

def add_points(user_id, username, pts):
    cursor.execute("INSERT INTO points(user_id, username, points) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET points=points+?", (user_id, username, pts, pts))
    conn.commit()

def get_leaderboard():
    cursor.execute("SELECT username, points FROM points ORDER BY points DESC LIMIT 10")
    return cursor.fetchall()

# WELCOME
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        uname = user.username if user.username else user.first_name
        await update.message.reply_text(
            f"🔮 Welcome to Bun Butter Jam!\n"
            f"👤 Name: {user.first_name}\n"
            f"📛 Username: @{uname}\n"
            f"📜 Rules:\n"
            f" - Don't PM/DM others\n"
            f" - Avoid bad words\n"
            f" - Contact admin for issues"
        )

# BAD WORDS CHECK
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return
    user = update.message.from_user
    text = update.message.text.lower()
    for w in BAD_WORDS:
        if w in text:
            await update.message.delete()
            reason = "No PM/DM" if w in ["pm","dm"] else "18+ behavior"
            count = add_warn(user.id, user.username or user.first_name, reason)
            if count >= 3:
                try:
                    await update.effective_chat.ban_member(user.id)
                    await update.message.reply_text(f"🚫 @{user.username or user.first_name} banned! Reason: {reason} ({count}/3)")
                except:
                    await update.message.reply_text("⚠️ Cannot ban, bot needs admin")
            else:
                await update.message.reply_text(f"⚠️ @{user.username or user.first_name} warned ({count}/3)\nReason: {reason}")
            return

# ADMIN COMMANDS
async def warn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Reply to someone to warn them.")
        return
    target = update.message.reply_to_message.from_user
    reason = " ".join(context.args) if context.args else "No reason"
    count = add_warn(target.id, target.username or target.first_name, reason)
    await update.message.reply_text(f"⚠️ @{target.username or target.first_name} warned ({count}/3). Reason: {reason}")

async def unwarn_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member = await update.effective_chat.get_member(update.message.from_user.id)
    if member.status not in ["administrator","creator"]:
        await update.message.reply_text("❌ Only admin/owner can remove warn")
        return
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        remove_warn(target.id)
        await update.message.reply_text(f"✅ Warning removed from @{target.username or target.first_name}")

# AI CHAT
async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return
    text = update.message.text
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":"You are a friendly Telegram group bot."},
                      {"role":"user","content":text}],
            max_tokens=100, temperature=0.7
        )
        reply = response.choices[0].message.content.strip()
        await update.message.reply_text(reply)
    except Exception:
        await update.message.reply_text("⚠️ AI error, try again later.")

# VOICE
async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = " ".join(context.args)
    if not msg_text:
        await update.message.reply_text("❌ Usage: /voice <text>")
        return
    tts = gTTS(text=msg_text, lang="en")
    tts.save("voice.mp3")
    await update.message.reply_voice(open("voice.mp3","rb"))
    os.remove("voice.mp3")

# LEADERBOARD
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = get_leaderboard()
    text = "🏆 Leaderboard:\n"
    for i,(uname,pts) in enumerate(top,1):
        text += f"{i}. {uname} - {pts} pts\n"
    await update.message.reply_text(text)

# AI QUIZ
async def generate_ai_quiz():
    prompt = "Generate one multiple choice general knowledge question format: question|opt1,opt2,opt3,opt4|correct_answer"
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":"You generate one MCQ question."},
                      {"role":"user","content":prompt}],
            max_tokens=200
        )
        text = response.choices[0].message.content.strip()
        q, opts, ans = text.split("|")
        return q.strip(), opts.split(","), ans.strip()
    except:
        return "What is 2+2?", ["1","2","3","4"], "4"

async def auto_ai_quiz_task(app):
    while True:
        question, options, answer = await generate_ai_quiz()
        cursor.execute("DELETE FROM quiz")
        cursor.execute("INSERT INTO quiz(question, answer, active) VALUES(?, ?, 1)", (question, answer))
        conn.commit()

        keyboard = [[InlineKeyboardButton(f"{chr(65+i)}: {opt}", callback_data=f"quizans_{opt}") for i,opt in enumerate(options)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        for chat_id in app.bot_data.get("groups", []):
            try:
                await app.bot.send_message(chat_id=chat_id, text=f"❓ AI Quiz:\n{question}", reply_markup=reply_markup)
            except: pass
        await asyncio.sleep(QUIZ_INTERVAL)

async def track_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if "groups" not in context.bot_data:
        context.bot_data["groups"] = set()
    context.bot_data["groups"].add(chat_id)

async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cursor.execute("SELECT question, answer FROM quiz WHERE active=1")
    row = cursor.fetchone()
    if not row:
        await query.edit_message_text("No active quiz.")
        return
    q, ans = row
    user = query.from_user
    if query.data.endswith(ans):
        add_points(user.id, user.username or user.first_name, 5)
        await query.edit_message_text(f"✅ Correct! +5 pts for @{user.username}")
    else:
        await query.edit_message_text(f"❌ Wrong! Correct: {ans}")

# MAIN
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_message))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_reply))
    app.add_handler(MessageHandler(filters.ALL, track_groups))

    app.add_handler(CommandHandler("warn", warn_command))
    app.add_handler(CommandHandler("unwarn", unwarn_command))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CallbackQueryHandler(quiz_answer))

    asyncio.create_task(auto_ai_quiz_task(app))

    print("🤖 Bun Butter Jam Bot Running...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())