import os
import json
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)
import openai
from langdetect import detect  # to detect language

# ---------- CONFIG ----------
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
QUIZ_INTERVAL = int(os.getenv("QUIZ_INTERVAL", 600))

openai.api_key = OPENAI_KEY
DATA_FILE = "data.json"

# ---------- LOAD / SAVE DATA ----------
if not os.path.exists(DATA_FILE):
    data = {"warns": {}, "games": {}, "leaderboard": {}, "groups": []}
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)
else:
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# ---------- WELCOME ----------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.full_name
    username = update.effective_user.username or "No username"
    chat_id = str(update.effective_chat.id)
    if chat_id not in data["groups"]:
        data["groups"].append(chat_id)
        save_data()

    text = (
        f"🔮 Welcome to Bun Butter Jam!\n"
        f"👤 Name: {name}\n"
        f"💬 Username: {username}\n"
        f"🆔 Group ID: {chat_id}\n\n"
        f"📜 Rules:\n"
        f"📩 Don't PM/DM others\n"
        f"🚫 Avoid bad words\n"
        f"⚠️ Follow admin instructions\n"
        "If you have any issues, contact admin."
    )
    keyboard = [[InlineKeyboardButton("📜 Rules", callback_data="rules")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "rules":
        rules_text = (
            "📜 *Group Rules*\n"
            "1️⃣ No 18+ content\n"
            "2️⃣ No spam\n"
            "3️⃣ Respect others\n"
            "4️⃣ No PM/DM for bad things\n"
            "5️⃣ Follow admins"
        )
        await query.edit_message_text(rules_text, parse_mode='Markdown')

# ---------- BAD WORDS ----------
BAD_WORDS = [
    "sex","porn","xxx","nude","fuck","ass","bitch","cunt","dick",
    "cock","pussy","slut","whore","rape","masturbate","boobs","penis",
    "pm","dm","private chat","private message","direct chat","direct message",
    "punda","sunni","potta","thevudiya","thayoli","oombu","nudity","inbox","thevidya","ummbu","gommala","ommala","mairu","thayali"
]

async def handle_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id)
    user_name = update.effective_user.full_name

    msg_text = update.message.text or ""
    if any(word.lower() in msg_text.lower() for word in BAD_WORDS):
        await update.message.delete()
        # initialize warns
        if chat_id not in data["warns"]:
            data["warns"][chat_id] = {}
        if user_id not in data["warns"][chat_id]:
            data["warns"][chat_id][user_id] = {"name": user_name, "count":0}

        data["warns"][chat_id][user_id]["count"] += 1
        save_data()

        reason = "Used bad words / 18+ content / Against group rules"
        await update.effective_chat.send_message(
            f"⚠️ {user_name} received a warning!\n"
            f"Reason: {reason}\n"
            f"Total Warnings: {data['warns'][chat_id][user_id]['count']}"
        )

        # Ban at 3 warnings
        if data["warns"][chat_id][user_id]["count"] >= 3:
            await update.effective_chat.ban_member(update.effective_user.id)
            await update.effective_chat.send_message(
                f"⛔ {user_name} has been banned for repeated violations!"
            )

# ---------- REMOVE WARN (ADMIN) ----------
async def remove_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if not context.args:
        await update.message.reply_text("❌ Usage: /remove_warn <user_id>")
        return
    user_id = str(context.args[0])
    if chat_id in data["warns"] and user_id in data["warns"][chat_id]:
        data["warns"][chat_id][user_id]["count"] = 0
        save_data()
        await update.message.reply_text(
            f"✅ Warning removed for user {data['warns'][chat_id][user_id]['name']}"
        )

# ---------- AI CHAT ----------
async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    lang = detect(user_message)
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user","content":user_message}],
        max_tokens=200
    )
    reply = response['choices'][0]['message']['content']

    # Auto translate logic if needed (example: Tamil/Tanglish)
    if lang.startswith("ta"):
        reply = f"🇹🇦 {reply}"
    elif lang.startswith("en"):
        reply = f"🇬🇧 {reply}"
    else:
        reply = f"💬 {reply}"

    await update.message.reply_text(reply)

# ---------- GAMES ----------
async def guess_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = random.randint(1,50)
    await update.message.reply_text(f"Guess a number between 1-50! My number is {number}")

async def word_scramble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = ["python","telegram","bot","quiz","openai"]
    word = random.choice(words)
    scrambled = "".join(random.sample(word,len(word)))
    await update.message.reply_text(f"Unscramble this word: {scrambled}")

# ---------- LEADERBOARD ----------
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    lb = data.get("leaderboard", {}).get(chat_id, {})
    if not lb:
        await update.message.reply_text("No scores yet!")
        return
    sorted_lb = sorted(lb.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 Leaderboard:\n"
    for user, score in sorted_lb[:10]:
        text += f"{user}: {score}\n"
    await update.message.reply_text(text)

# ---------- AI QUIZ ----------
async def auto_ai_quiz(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in data["groups"]:
        question_prompt = "Ask a simple trivia question with options A,B,C,D."
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user","content":question_prompt}],
            max_tokens=150
        )
        question = response['choices'][0]['message']['content']
        await context.bot.send_message(chat_id=int(chat_id), text=f"📝 AI Quiz!\n{question}")

async def start_quiz_task(app):
    while True:
        await auto_ai_quiz(app)
        await asyncio.sleep(QUIZ_INTERVAL)

# ---------- START BOT ----------
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_bad_words))
    app.add_handler(CommandHandler("remove_warn", remove_warn))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_chat))
    app.add_handler(CommandHandler("guess", guess_number))
    app.add_handler(CommandHandler("scramble", word_scramble))
    app.add_handler(CommandHandler("leaderboard", show_leaderboard))
    app.add_handler(CallbackQueryHandler(button_callback))

    asyncio.create_task(start_quiz_task(app))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())