# mybot.py
import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import openai

# -------------------------------
# Environment Variables
# -------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QUIZ_INTERVAL = int(os.getenv("QUIZ_INTERVAL", 600))  # default 10 mins

openai.api_key = OPENAI_API_KEY

# -------------------------------
# Globals
# -------------------------------
bad_words = [
    "sex","porn","xxx","nude","fuck","ass","bitch","cunt","dick",
    "cock","pussy","slut","whore","rape","masturbate","boobs","penis",
    "pm","dm","private chat","private message","direct chat","direct message",
    "punda","sunni","potta","thevudiya","thayoli","oombu","nudity","inbox","thevidya","ummbu","gommala","ommala","mairu","thayali"
]

warnings = {}       # chat_id: {user_id: warn_count}
leaderboards = {}   # chat_id: {user_id: points}
active_quiz = {}    # chat_id: quiz info

# -------------------------------
# Helper Functions
# -------------------------------
async def send_ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_text = update.message.text
    try:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=f"You are a friendly Telegram bot. Reply naturally to: {user_text}",
            max_tokens=150
        )
        answer = response.choices[0].text.strip()
        await update.message.reply_text(answer)
    except Exception as e:
        print(f"OpenAI Error: {e}")
        await update.message.reply_text("⚠️ AI reply error.")

def get_warns(chat_id, user_id):
    return warnings.get(chat_id, {}).get(user_id, 0)

def add_warn(chat_id, user_id):
    warnings.setdefault(chat_id, {})
    warnings[chat_id][user_id] = warnings[chat_id].get(user_id, 0) + 1
    return warnings[chat_id][user_id]

def remove_warn(chat_id, user_id):
    if chat_id in warnings and user_id in warnings[chat_id]:
        warnings[chat_id][user_id] -= 1
        if warnings[chat_id][user_id] <= 0:
            del warnings[chat_id][user_id]

def add_points(chat_id, user_id, points):
    leaderboards.setdefault(chat_id, {})
    leaderboards[chat_id][user_id] = leaderboards[chat_id].get(user_id, 0) + points

# -------------------------------
# Bad words handling
# -------------------------------
async def handle_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    msg = update.message.text.lower()
    chat_id = update.message.chat.id
    user = update.message.from_user
    username = user.username or user.first_name

    for word in bad_words:
        if word in msg:
            try: await update.message.delete()
            except: pass

            reason = "18+ behavior" if word not in ["pm","dm","private chat","private message","direct chat","direct message"] else "against rules"
            warn_count = add_warn(chat_id, user.id)

            if warn_count >= 3:
                try:
                    await update.effective_chat.ban_member(user.id)
                    await update.message.reply_text(f"🚫 @{username} banned! Reason: {reason}")
                except:
                    await update.message.reply_text(f"⚠️ Could not ban @{username}. Reason: {reason}")
            else:
                await update.message.reply_text(f"⚠️ @{username} warned ({warn_count}/3)! Reason: {reason}")
            return

# -------------------------------
# Commands
# -------------------------------
async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        username = target.username or target.first_name
        reason = " ".join(context.args) if context.args else "No reason"
        count = add_warn(chat_id, target.id)
        await update.message.reply_text(f"⚠️ @{username} warned ({count}/3)! Reason: {reason}")

async def unwarn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    user = update.message.from_user
    member = await update.effective_chat.get_member(user.id)
    if member.status not in ["administrator", "creator"]:
        await update.message.reply_text("❌ Only admins can remove warns")
        return
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        username = target.username or target.first_name
        remove_warn(chat_id, target.id)
        await update.message.reply_text(f"✅ @{username} warn removed by admin")

async def reset_warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    warnings[chat_id] = {}
    await update.message.reply_text("✅ All warns cleared")

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    if chat_id not in leaderboards or not leaderboards[chat_id]:
        await update.message.reply_text("📊 No scores yet!")
        return
    text = "🏆 Leaderboard:\n"
    for uid, pts in sorted(leaderboards[chat_id].items(), key=lambda x:x[1], reverse=True):
        text += f"- {pts} points\n"
    await update.message.reply_text(text)

# -------------------------------
# Games
# -------------------------------
async def start_guess_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = random.randint(1,50)
    context.chat_data["guess_number"] = number
    await update.message.reply_text("🎯 Guess a number between 1 and 50!")

async def guess_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat.id
    if "guess_number" not in context.chat_data:
        return
    try: guess = int(update.message.text)
    except: return
    number = context.chat_data["guess_number"]
    user = update.message.from_user
    username = user.username or user.first_name
    if guess == number:
        add_points(chat_id, user.id, 5)
        await update.message.reply_text(f"🎉 @{username} guessed correctly! +5 points")
        del context.chat_data["guess_number"]
    elif guess < number:
        await update.message.reply_text("🔼 Higher!")
    else:
        await update.message.reply_text("🔽 Lower!")

# -------------------------------
# AI Quiz
# -------------------------------
async def auto_ai_quiz(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    try:
        prompt = "Give an easy trivia question with 4 options. Format: question|option1,option2,option3,option4|answer"
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=150
        )
        data = response.choices[0].text.strip()
        parts = data.split("|")
        if len(parts) == 3:
            question, options, answer = parts
            options_list = options.split(",")
            active_quiz[chat_id] = {"question": question, "options": options_list, "answer": answer}
            buttons = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options_list]
            await context.bot.send_message(chat_id, f"🧠 Quiz Time!\n{question}", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        print(f"Quiz Error: {e}")

async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat.id
    user = query.from_user
    username = user.username or user.first_name
    if chat_id in active_quiz:
        correct = active_quiz[chat_id]["answer"]
        if query.data == correct:
            add_points(chat_id, user.id, 5)
            await query.edit_message_text(f"✅ @{username} answered correctly! +5 points")
        else:
            await query.edit_message_text(f"❌ @{username} answered wrong! Correct: {correct}")
        del active_quiz[chat_id]

# -------------------------------
# Welcome
# -------------------------------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        username = user.username or user.first_name
        await update.message.reply_text(f"🔮 Welcome to Bun Butter Jam,f"🎯 @{username}!\nRules:\n1️⃣ Don't PM/DM\n2️⃣ Avoid bad words\n3️⃣ Contact admin if issues")

# -------------------------------
# Main
# -------------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_bad_words))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), send_ai_reply))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), guess_number_handler))
    app.add_handler(CommandHandler("leaderboard", show_leaderboard))
    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("unwarn", unwarn_cmd))
    app.add_handler(CommandHandler("reset", reset_warn_cmd))
    app.add_handler(CommandHandler("guess", start_guess_number))
    app.add_handler(CallbackQueryHandler(quiz_answer))

    # Schedule auto-AI quiz for all groups
    app.job_queue.run_repeating(auto_ai_quiz, interval=QUIZ_INTERVAL, first=10)

    print("🤖 Bun Butter Jam Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()