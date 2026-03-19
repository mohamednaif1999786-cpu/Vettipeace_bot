import os
import random
import json
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

BOT_TOKEN = os.getenv("BOT_TOKEN")
QUIZ_INTERVAL = int(os.getenv("QUIZ_INTERVAL", 600))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "123456"))

BAD_WORDS = [
    "sex","porn","xxx","nude","fuck","ass","bitch","cunt","dick",
    "cock","pussy","slut","whore","rape","masturbate","boobs","penis",
    "pm","dm","private chat","private message","direct chat","direct message",
    "punda","sunni","potta","thevudiya","thayoli","oombu","nudity","inbox","thevidya","ummbu","gommala","ommala","mairu","thayali"
]

warnings = {}
games_data_file = "games_data.json"

# ------------------ STORAGE ------------------
def load_data():
    if os.path.exists(games_data_file):
        with open(games_data_file, "r") as f:
            return json.load(f)
    return {"leaderboard": {}, "guess_number": {}, "word_scramble": {}}

def save_data(data):
    with open(games_data_file, "w") as f:
        json.dump(data, f)

# ------------------ WELCOME ------------------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        name = user.first_name
        username = f"@{user.username}" if user.username else "NoUsername"
        chat_id = update.effective_chat.id
        msg = (
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
        await update.message.reply_text(msg)

# ------------------ BAD WORDS ------------------
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return
    msg = update.message.text.lower()
    user = update.message.from_user
    user_id = user.id
    username = user.username or "NoUsername"

    for word in BAD_WORDS:
        if word in msg:
            try: await update.message.delete()
            except: pass
            warnings[user_id] = warnings.get(user_id, 0) + 1
            reason = "18+ behavior" if word not in ["pm","dm","private chat","private message","direct chat","direct message"] else "Against rules"

            if warnings[user_id] >= 3:
                try:
                    await update.effective_chat.ban_member(user_id)
                    await update.message.reply_text(f"🚫 @{username} banned! Reason: {reason}")
                except:
                    await update.message.reply_text(f"⚠️ Could not ban @{username}. Reason: {reason}")
            else:
                await update.message.reply_text(f"⚠️ @{username} warned ({warnings[user_id]}/3)! Reason: {reason}")
            return

# ------------------ WARN/UNWARN ------------------
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        user_id = user.id
        username = user.username or "NoUsername"
        reason = " ".join(context.args) if context.args else "No reason"
        warnings[user_id] = warnings.get(user_id,0)+1
        await update.message.reply_text(f"⚠️ @{username} warned ({warnings[user_id]}/3)! Reason: {reason}")

async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin = await update.effective_chat.get_member(update.message.from_user.id)
    if admin.status not in ["administrator", "creator"]:
        await update.message.reply_text("❌ Only admins can remove warnings")
        return
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        user_id = user.id
        if warnings.get(user_id,0)>0:
            warnings[user_id]-=1
            await update.message.reply_text(f"✅ Warning removed from @{user.username}")
        else:
            await update.message.reply_text("⚠️ User has no warnings")

# ------------------ AI RESPONSE ------------------
async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"user","content":msg}],
            max_tokens=150
        )
        answer = response.choices[0].message.content
        await update.message.reply_text(answer)
    except Exception as e:
        await update.message.reply_text("❌ AI error")

# ------------------ AI QUIZ ------------------
QUIZ_QUESTIONS = [
    {"question":"Capital of India?","options":["New Delhi","Mumbai","Kolkata"],"answer":"New Delhi"},
    {"question":"5 + 7 = ?","options":["11","12","13"],"answer":"12"},
    {"question":"Python is a?","options":["Snake","Programming Language","Car"],"answer":"Programming Language"},
]

async def send_quiz(context: ContextTypes.DEFAULT_TYPE):
    chat_id = GROUP_CHAT_ID
    q = random.choice(QUIZ_QUESTIONS)
    await context.bot.send_poll(
        chat_id=chat_id,
        question=q["question"],
        options=q["options"],
        type="quiz",
        correct_option_id=q["options"].index(q["answer"]),
        is_anonymous=False
    )

# ------------------ GUESS NUMBER ------------------
async def guess_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = update.message.from_user
    chat_id = update.effective_chat.id

    if chat_id not in data["guess_number"]:
        number = random.randint(1,100)
        data["guess_number"][chat_id] = {"number":number, "players":{}}
        save_data(data)
        await update.message.reply_text("🎯 Guess the number between 1 and 100!")
        return

    guess = int(update.message.text)
    number = data["guess_number"][chat_id]["number"]
    if guess == number:
        points = 5
        data["leaderboard"][str(user.id)] = data["leaderboard"].get(str(user.id),0)+points
        await update.message.reply_text(f"✅ Correct! You got {points} points!")
        del data["guess_number"][chat_id]
    elif guess < number:
        await update.message.reply_text("⬆️ Too low!")
    else:
        await update.message.reply_text("⬇️ Too high!")
    save_data(data)

# ------------------ WORD SCRAMBLE ------------------
WORDS = ["telegram","python","openai","developer","quiz","butter","bun"]

async def word_scramble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user = update.message.from_user
    chat_id = update.effective_chat.id

    if chat_id not in data["word_scramble"]:
        word = random.choice(WORDS)
        scrambled = "".join(random.sample(word,len(word)))
        data["word_scramble"][chat_id] = {"word":word, "scrambled":scrambled, "players":{}}
        save_data(data)
        await update.message.reply_text(f"🧩 Unscramble this word: {scrambled}")
        return

    guess = update.message.text.lower()
    correct_word = data["word_scramble"][chat_id]["word"]
    if guess == correct_word:
        points = 5
        data["leaderboard"][str(user.id)] = data["leaderboard"].get(str(user.id),0)+points
        await update.message.reply_text(f"✅ Correct! You got {points} points!")
        del data["word_scramble"][chat_id]
    else:
        await update.message.reply_text("❌ Wrong, try again!")
    save_data(data)

# ------------------ LEADERBOARD ------------------
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    leaderboard = data.get("leaderboard",{})
    if not leaderboard:
        await update.message.reply_text("🏆 No scores yet!")
        return
    sorted_lb = sorted(leaderboard.items(), key=lambda x:x[1], reverse=True)
    msg = "🏆 Leaderboard:\n"
    for uid, score in sorted_lb[:10]:
        msg += f"{uid}: {score} points\n"
    await update.message.reply_text(msg)

# ------------------ MAIN ------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_message))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_reply))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), guess_number))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), word_scramble))

    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("unwarn", unwarn))
    app.add_handler(CommandHandler("leaderboard", leaderboard))

    # AI quiz job every QUIZ_INTERVAL
    app.job_queue.run_repeating(send_quiz, interval=QUIZ_INTERVAL, first=10)

    print("🤖 Bun Butter Jam Bot Running...")
    app.run_polling()

if __name__=="__main__":
    main()