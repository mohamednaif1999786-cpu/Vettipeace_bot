# mybot.py
import os
import asyncio
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
import nest_asyncio
nest_asyncio.apply()

# -------------------------------
# Environment Variables
# -------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
QUIZ_INTERVAL = int(os.getenv("QUIZ_INTERVAL", 600))  # default 10 min
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
warnings = {}        # user_id: warning_count
leaderboard = {}     # user_id: points
active_quiz = {}     # chat_id: {question, answer}

# -------------------------------
# Helper Functions
# -------------------------------

async def send_ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply to user message using OpenAI"""
    if not update.message or not update.message.text:
        return
    user_text = update.message.text
    chat_id = update.effective_chat.id
    try:
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=f"You are a helpful friend in a Telegram group. Reply to: {user_text}",
            max_tokens=150
        )
        answer = response.choices[0].text.strip()
        await update.message.reply_text(answer)
    except Exception as e:
        print(f"OpenAI Error: {e}")
        await update.message.reply_text("⚠️ AI reply error.")

async def handle_bad_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check for bad words, delete message, warn or ban"""
    if not update.message or not update.message.text:
        return

    msg_text = update.message.text.lower()
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name

    for word in bad_words:
        if word in msg_text:
            try: await update.message.delete()
            except: pass

            reason = (
                "18+ behavior" if word not in ["pm","dm","private chat","private message","direct chat","direct message"]
                else "against group rules"
            )
            warnings[user_id] = warnings.get(user_id,0)+1

            if warnings[user_id] >= 3:
                try:
                    await update.effective_chat.ban_member(user_id)
                    await update.message.reply_text(f"🚫 @{username} banned! Reason: {reason}")
                except:
                    await update.message.reply_text(f"⚠️ Could not ban @{username}. Reason: {reason}")
            else:
                await update.message.reply_text(f"⚠️ @{username} warned ({warnings[user_id]}/3)! Reason: {reason}")
            return

# -------------------------------
# Commands
# -------------------------------
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        user_id = target.id
        username = target.username or target.first_name
        reason = " ".join(context.args) if context.args else "No reason"
        warnings[user_id] = warnings.get(user_id,0)+1
        await update.message.reply_text(f"⚠️ @{username} warned ({warnings[user_id]}/3)! Reason: {reason}")

async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin only
    user_id = update.message.from_user.id
    member = await update.effective_chat.get_member(user_id)
    if member.status not in ["administrator","creator"]:
        await update.message.reply_text("❌ Only admins/owner can remove warns")
        return
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        target_id = target.id
        username = target.username or target.first_name
        if warnings.get(target_id,0)>0:
            warnings[target_id]-=1
            await update.message.reply_text(f"✅ @{username} warn removed by admin")
        else:
            await update.message.reply_text("⚠️ This user has no warnings")

async def reset_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    warnings.clear()
    await update.message.reply_text("✅ All warnings cleared")

# -------------------------------
# Games
# -------------------------------
async def start_guess_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = random.randint(1,50)
    context.chat_data["guess_number"] = number
    await update.message.reply_text("🎯 Guess a number between 1 and 50!")

async def guess_number_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "guess_number" not in context.chat_data:
        return
    try:
        guess = int(update.message.text)
    except:
        return
    number = context.chat_data["guess_number"]
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    if guess == number:
        leaderboard[user_id] = leaderboard.get(user_id,0)+5
        await update.message.reply_text(f"🎉 @{username} guessed correctly! +5 points")
        del context.chat_data["guess_number"]
    elif guess < number:
        await update.message.reply_text("🔼 Higher!")
    else:
        await update.message.reply_text("🔽 Lower!")

# -------------------------------
# Leaderboard
# -------------------------------
async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not leaderboard:
        await update.message.reply_text("📊 No scores yet!")
        return
    text = "🏆 Leaderboard:\n"
    for uid, pts in sorted(leaderboard.items(), key=lambda x: x[1], reverse=True):
        text += f"- {pts} points\n"
    await update.message.reply_text(text)

# -------------------------------
# Auto-AI Quiz
# -------------------------------
async def auto_ai_quiz_task(app):
    while True:
        try:
            chat_id = os.getenv("QUIZ_CHAT_ID")  # add the group chat id env variable
            if chat_id:
                prompt = "Give me an easy trivia question for a Telegram group with options, in format: question|option1,option2,option3,option4|answer"
                response = openai.Completion.create(
                    model="text-davinci-003",
                    prompt=prompt,
                    max_tokens=150
                )
                data = response.choices[0].text.strip()
                parts = data.split("|")
                if len(parts)==3:
                    question, options, answer = parts
                    active_quiz[int(chat_id)] = {"question": question, "options": options.split(","), "answer": answer}
                    buttons = [[InlineKeyboardButton(opt, callback_data=opt)] for opt in options.split(",")]
                    await app.bot.send_message(int(chat_id), f"🧠 Quiz Time!\n{question}", reply_markup=InlineKeyboardMarkup(buttons))
        except Exception as e:
            print(f"Quiz Error: {e}")
        await asyncio.sleep(QUIZ_INTERVAL)

async def quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    if chat_id in active_quiz:
        correct = active_quiz[chat_id]["answer"]
        if query.data == correct:
            leaderboard[user_id] = leaderboard.get(user_id,0)+5
            await query.edit_message_text(f"✅ @{username} answered correctly! +5 points")
            del active_quiz[chat_id]
        else:
            await query.edit_message_text(f"❌ @{username} answered wrong! Correct answer: {correct}")
            del active_quiz[chat_id]

# -------------------------------
# Welcome new members
# -------------------------------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        username = user.username or user.first_name
        user_id = user.id
        await update.message.reply_text(f"🔮 Welcome to Bun Butter Jam, @{username}!\nPlease follow the rules:\n1️⃣ Don't PM/DM\n2️⃣ Avoid bad words\n3️⃣ Contact admin if issues")

# -------------------------------
# Main
# -------------------------------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_bad_words))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), send_ai_reply))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), guess_number_handler))
    app.add_handler(CommandHandler("leaderboard", show_leaderboard))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("unwarn", unwarn))
    app.add_handler(CommandHandler("reset", reset_warnings))
    app.add_handler(CommandHandler("guess", start_guess_number))
    app.add_handler(CallbackQueryHandler(quiz_answer))

    # Start auto-AI quiz background task
    asyncio.create_task(auto_ai_quiz_task(app))

    print("🤖 Bun Butter Jam Bot Running...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except RuntimeError:
        import nest_asyncio
        nest_asyncio.apply()
        asyncio.get_event_loop().run_until_complete(main())