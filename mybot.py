from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os, sqlite3, random, requests, asyncio, datetime
from gtts import gTTS

# -------------------------
# ⚡ TOKENS
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# -------------------------
# ⚡ DATABASE (Persistent)
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

# Tables for scores, warns, leaderboard
cursor.execute("""CREATE TABLE IF NOT EXISTS score (
    user_id INTEGER PRIMARY KEY,
    points INTEGER DEFAULT 0,
    today_points INTEGER DEFAULT 0,
    week_points INTEGER DEFAULT 0
)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS warns (
    user_id INTEGER PRIMARY KEY,
    warn_count INTEGER DEFAULT 0
)""")
conn.commit()

# -------------------------
# ⚡ GLOBALS
bad_words = ["sex","porn","xxx","nude","fuck","bitch","dick","pussy","rape","pm","dm","potta","sunni","kiss","pvrt","mairu","gommala","ommala","oombu","ummbu","kotta","ummbi","thaniya"]
current_quiz = {}
quiz_active = False
games_list = ["guess_number","word_scramble"]  # AI games other than quiz
quiz_interval = 600  # 10 minutes

# -------------------------
# ⚡ HELPER FUNCTIONS

def add_points(uid, pts):
    cursor.execute("SELECT points, today_points, week_points FROM score WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE score SET points=?, today_points=?, week_points=? WHERE user_id=?",
                       (row[0]+pts, row[1]+pts, row[2]+pts, uid))
    else:
        cursor.execute("INSERT INTO score (user_id, points, today_points, week_points) VALUES (?,?,?,?)",
                       (uid, pts, pts, pts))
    conn.commit()

def reset_today_weekly():
    cursor.execute("UPDATE score SET today_points=0")
    cursor.execute("UPDATE score SET week_points=0")
    conn.commit()

# -------------------------
# ⚡ WELCOME
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        await update.message.reply_text(
f"""🔮 Welcome to 乃un 乃utter ﾌam 🔮

👤 Name: {user.first_name}
📛 Username: @{user.username if user.username else 'No username'}

📜 Rules:
🚫 No PM / DM
🚫 Avoid bad words
⚠️ Follow admins"""
        )

# -------------------------
# ⚡ WARN SYSTEM
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    msg = update.message.text.lower()
    user = update.message.from_user
    uid = user.id
    username = f"@{user.username}" if user.username else user.first_name

    # Check bad words
    for word in bad_words:
        if word in msg:
            try:
                await update.message.delete()
            except:
                pass
            # Increase warn count
            cursor.execute("SELECT warn_count FROM warns WHERE user_id=?", (uid,))
            row = cursor.fetchone()
            if row:
                warn_count = row[0]+1
                cursor.execute("UPDATE warns SET warn_count=? WHERE user_id=?", (warn_count, uid))
            else:
                warn_count = 1
                cursor.execute("INSERT INTO warns (user_id, warn_count) VALUES (?,?)", (uid, warn_count))
            conn.commit()

            # Reason
            reason = "🚫 No PM/DM" if word in ["pm","dm"] else "🔞 18+ / Bad words"
            # Reply in group
            keyboard = [[InlineKeyboardButton("✅ Remove Warn", callback_data=f"unwarn_{uid}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"⚠️ {username} warned ({warn_count}/3)\nReason: {reason}\nWord: {word}",
                reply_markup=reply_markup
            )
            # Auto-ban if 3 warnings
            if warn_count >= 3:
                try:
                    await update.effective_chat.ban_member(uid)
                    await update.message.reply_text(f"🚫 {username} banned (3 warnings)")
                except:
                    await update.message.reply_text(f"❌ Cannot ban {username}, check admin rights")
            return

# -------------------------
# ⚡ REMOVE WARN BUTTON
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = int(query.data.split("_")[1])
    admin = await update.effective_chat.get_member(query.from_user.id)
    if admin.status not in ["administrator", "creator"]:
        await query.edit_message_text("❌ Only admin can remove warn")
        return
    cursor.execute("SELECT warn_count FROM warns WHERE user_id=?", (uid,))
    row = cursor.fetchone()
    if row and row[0] > 0:
        cursor.execute("UPDATE warns SET warn_count=? WHERE user_id=?", (row[0]-1, uid))
        conn.commit()
        await query.edit_message_text("✅ Warning removed (admin only)")
    else:
        await query.edit_message_text("⚠️ User has no warnings")

# -------------------------
# ⚡ BAN COMMAND
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Reply to a user to ban")
        return
    user = update.message.reply_to_message.from_user
    uid = user.id
    username = f"@{user.username}" if user.username else user.first_name
    try:
        await update.effective_chat.ban_member(uid)
        await update.message.reply_text(f"🚫 {username} banned")
    except:
        await update.message.reply_text("❌ Cannot ban, bot not admin")

# -------------------------
# ⚡ AI REPLY
async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        return
    lang = "English"
    if any('\u0b80' <= c <= '\u0bff' for c in text):
        lang = "Tamil"
    elif any(w in text.lower() for w in ["da","machan","epdi"]):
        lang = "Tanglish"
    try:
        res = requests.post(
            "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2",
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={"inputs": f"Reply in {lang}: {text}"}
        )
        data = res.json()
        if isinstance(data, list):
            reply = data[0].get("generated_text","🤖 No response")
        else:
            reply = "⚠️ AI busy"
        await update.message.reply_text(reply)
    except:
        await update.message.reply_text("⚠️ AI error")

# -------------------------
# ⚡ VOICE COMMAND
async def voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("❌ Use /voice <text>")
        return
    tts = gTTS(text)
    tts.save("voice.mp3")
    await update.message.reply_voice(voice=open("voice.mp3","rb"))
    os.remove("voice.mp3")

# -------------------------
# ⚡ AI QUIZ SYSTEM (automatic every 10 mins)
async def ai_quiz_runner(app):
    global quiz_active
    await asyncio.sleep(5)  # wait for bot start
    while True:
        try:
            quiz_active = True
            chat_ids = [c.chat_id for c in await app.bot.get_updates()]
            if chat_ids:
                chat_id = chat_ids[-1]  # last active group
                # AI generates question
                res = requests.post(
                    "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2",
                    headers={"Authorization": f"Bearer {HF_TOKEN}"},
                    json={"inputs": "Ask a fun general knowledge quiz question with options A,B,C,D"}
                )
                data = res.json()
                if isinstance(data,list):
                    question = data[0].get("generated_text","What is 2+2? A)2 B)3 C)4 D)5")
                else:
                    question = "What is 2+2? A)2 B)3 C)4 D)5"
                current_quiz[chat_id] = question
                await app.bot.send_message(chat_id=chat_id, text=f"❓ AI Quiz:\n{question}")
            await asyncio.sleep(quiz_interval)
        except Exception as e:
            print("Quiz runner error:", e)
            await asyncio.sleep(60)

# -------------------------
# CHECK QUIZ ANSWER
async def check_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in current_quiz:
        return
    # Simple check: if user replies with answer letter
    answer = update.message.text.strip().lower()
    correct = "c"  # in real AI, we parse AI options to determine
    if answer == correct:
        uid = update.message.from_user.id
        add_points(uid,5)
        await update.message.reply_text("✅ Correct! +5 points")
        del current_quiz[chat_id]

# -------------------------
# UNIQUE GAMES
async def guess_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = random.randint(1,10)
    uid = update.message.from_user.id
    await update.message.reply_text(f"🎲 Guess a number between 1-10")
    # Store answer in context
    context.user_data["guess_number"] = number

async def guess_number_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "guess_number" not in context.user_data:
        return
    try:
        guess = int(update.message.text)
        number = context.user_data["guess_number"]
        uid = update.message.from_user.id
        if guess == number:
            add_points(uid,5)
            await update.message.reply_text("🎉 Correct! +5 points")
        else:
            await update.message.reply_text(f"❌ Wrong! The number was {number}")
        del context.user_data["guess_number"]
    except:
        return

async def word_scramble(update: Update, context: ContextTypes.DEFAULT_TYPE):
    words = ["telegram","banana","butter","computer","python"]
    word = random.choice(words)
    scrambled = ''.join(random.sample(word,len(word)))
    uid = update.message.from_user.id
    context.user_data["word_scramble"] = word
    await update.message.reply_text(f"Unscramble this word: {scrambled}")

async def word_scramble_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "word_scramble" not in context.user_data:
        return
    answer = update.message.text.lower()
    word = context.user_data["word_scramble"]
    uid = update.message.from_user.id
    if answer == word:
        add_points(uid,5)
        await update.message.reply_text("🎉 Correct! +5 points")
    else:
        await update.message.reply_text(f"❌ Wrong! Correct: {word}")
    del context.user_data["word_scramble"]

# -------------------------
# LEADERBOARD
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🏆 Leaderboard:\n\n"
    cursor.execute("SELECT user_id, points FROM score ORDER BY points DESC LIMIT 5")
    rows = cursor.fetchall()
    for i,r in enumerate(rows,1):
        text += f"{i}. {r[0]} - {r[1]} pts\n"
    await update.message.reply_text(text)

# -------------------------
# MAIN
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Handlers
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_message))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_quiz_answer))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), ai_reply))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), guess_number_check))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), word_scramble_check))

app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("voice", voice))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("quiz", lambda u,c: None))  # AI auto
app.add_handler(CommandHandler("guess_number", guess_number))
app.add_handler(CommandHandler("word_scramble", word_scramble))
app.add_handler(CallbackQueryHandler(button_handler))

# Start AI quiz runner
asyncio.create_task(ai_quiz_runner(app))

print("🔥 Power Bot Running...")
app.run_polling()