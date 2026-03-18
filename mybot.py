from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
import os

TOKEN = os.getenv("TOKEN")

bad_words = [
    "sex","porn","xxx","nude","fuck","ass","bitch","cunt","dick",
    "cock","pussy","slut","whore","rape","masturbate","boobs","penis",
    "pm","dm","private chat","private message","direct chat","direct message",
    "punda","sunni","potta","thevidiya","thayali","oombu","nudity","inbox","ommala"
]

warnings = {}

# ✅ WELCOME MESSAGE (NO IMAGE)
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        name = user.first_name
        username = f"@{user.username}" if user.username else "No username"
        group_id = update.effective_chat.id

        text = f"""
🔮 Welcome to Bun Butter Jam

👤 Name: {name}
📛 Username: {username}
🆔 Group ID: {group_id}

📜 Rules:
🚫 Don't PM / DM
🚫 Avoid bad words
⚠️ Follow group rules

📞 If any issue, contact admin
        """

        await update.message.reply_text(text)

# ✅ AUTO MODERATION
async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return

    msg = update.message.text.lower()
    user = update.message.from_user
    user_id = user.id
    username = f"@{user.username}" if user.username else user.first_name

    for word in bad_words:
        if word in msg:

            # delete message
            try:
                await update.message.delete()
            except:
                pass

            # warning count
            warnings[user_id] = warnings.get(user_id, 0) + 1

            # reason
            if word in ["pm","dm","private chat","private message","direct chat","direct message"]:
                reason = "No PM / DM"
            elif word in ["sex","porn","xxx","nude","fuck","pussy","dick"]:
                reason = "18+ behaviour"
            else:
                reason = "Against group rules"

            # warn or ban
            if warnings[user_id] >= 3:
                try:
                    await update.effective_chat.ban_member(user_id)
                    await update.message.reply_text(
                        f"🚫 {username} banned!\nReason: {reason}"
                    )
                except:
                    await update.message.reply_text(
                        f"⚠️ Cannot ban {username}"
                    )
            else:
                await update.message.reply_text(
                    f"⚠️ {username} warned ({warnings[user_id]}/3)\nReason: {reason}"
                )
            return

# ✅ MANUAL WARN
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        user_id = user.id
        username = f"@{user.username}" if user.username else user.first_name

        warnings[user_id] = warnings.get(user_id, 0) + 1

        await update.message.reply_text(
            f"⚠️ {username} warned ({warnings[user_id]}/3)"
        )

# ✅ MAIN
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_message))
app.add_handler(CommandHandler("warn", warn))

print("🤖 Bot running...")
app.run_polling()