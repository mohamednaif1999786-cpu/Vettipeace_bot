from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
from PIL import Image, ImageDraw, ImageFont
import io
import os

import os

# Get the token from Railway environment variable
TOKEN = os.getenv("TOKEN")  # TOKEN must be set in Railway Variables

bad_words = [
    "sex","porn","xxx","nude","fuck","ass","bitch","cunt","dick",
    "cock","pussy","slut","whore","rape","masturbate","boobs","penis",
    "pm","dm","private chat","private message","direct chat","direct message",
    "punda","sunni","potta","thevudiya","thayoli","oombu","nudity","inbox","thevidya","ummbu","gommala"
]

warnings = {}

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        name = user.first_name
        username = f"@{user.username}" if user.username else "No username"
        user_id = user.id

        image = Image.open("bun_butter_logo.png").convert("RGBA")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("Poppins-Bold.ttf", 40)

        draw.text((50,50), " Welcome to Bun Butter Jam! 🔮", fill="white", font=font)
        draw.text((50,120), f"👤 Name: {name}", fill="white", font=font)
        draw.text((50,180), f"💬 Username: {username}", fill="white", font=font)
        draw.text((50,240), f"🆔 ID: {user_id}", fill="white", font=font)

        bio = io.BytesIO()
        bio.name = "welcome.png"
        image.save(bio, "PNG")
        bio.seek(0)

        keyboard = [[InlineKeyboardButton("📜 Rules", callback_data='rules')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_photo(photo=InputFile(bio), caption="⚠️ Please follow the rules!", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'rules':
        rules_text = (
            "📜 *Group Rules*\n\n"
            "1️⃣ No 18+ content\n"
            "2️⃣ No spam\n"
            "3️⃣ Respect others\n"
            "4️⃣ No PM/DM for bad things\n"
            "5️⃣ Follow admins"
        )
        await query.edit_message_text(rules_text, parse_mode='Markdown')

async def check_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text:
        return
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "NoUsername"
    msg = update.message.text.lower()

    for word in bad_words:
        if word in msg:
            try: await update.message.delete()
            except: pass

            warnings[user_id] = warnings.get(user_id, 0) + 1

            reason = (
                "against group rules"
                if word in ["pm","dm","private chat","private message","direct chat","direct message"]
                else "18+ behavior"
            )

            if warnings[user_id] >= 3:
                try:
                    await update.effective_chat.ban_member(user_id)
                    await update.message.reply_text(f"🚫 @{username} has been banned! Reason: {reason}")
                except:
                    await update.message.reply_text(f"⚠️ Could not ban @{username}, Reason: {reason}")
            else:
                await update.message.reply_text(f"⚠️ @{username} warned ({warnings[user_id]}/3)! Reason: {reason}")
            return

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        username = update.message.reply_to_message.from_user.username or "NoUsername"
        reason = " ".join(context.args) if context.args else "No reason given"
        warnings[user_id] = warnings.get(user_id, 0) + 1
        await update.message.reply_text(f"⚠️ @{username} warned ({warnings[user_id]}/3)! Reason: {reason}")

async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    member = await update.effective_chat.get_member(user_id)
    if member.status not in ["administrator", "creator"]:
        await update.message.reply_text("❌ Only admins/owner can cancel warnings")
        return
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        username = update.message.reply_to_message.from_user.username or "NoUsername"
        if warnings.get(target_id,0) > 0:
            warnings[target_id] -= 1
            await update.message.reply_text(f"✅ Warning removed from @{username}")
        else:
            await update.message.reply_text("⚠️ This user has no warnings")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    member = await(update.effective_chat.get_member(user_id))
    if member.status not in ["administrator", "creator"]:
        await update.message.reply_text("❌ Only admins/owner can unban")
        return
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        username = update.message.reply_to_message.from_user.username or "NoUsername"
        try:
            await update.effective_chat.unban_member(target_id)
            await update.message.reply_text(f"✅ @{username} has been unbanned")
        except:
            await update.message.reply_text("⚠️ Could not unban user")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    warnings.clear()
    await update.message.reply_text("✅ All warnings cleared")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), check_message))
app.add_handler(CommandHandler("warn", warn))
app.add_handler(CommandHandler("unwarn", unwarn))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(CallbackQueryHandler(button_callback))

print("🤖 Bun Butter Jam Bot is running...")
app.run_polling()