import os
import openai
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler, CallbackQueryHandler, CallbackContext
from collections import defaultdict, deque

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MEMORY_LENGTH = 5

openai.api_key = OPENAI_API_KEY
user_memory = defaultdict(lambda: deque(maxlen=MEMORY_LENGTH))
last_reply = {}

def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    raw_text = update.message.text.strip()
    user_memory[user_id].append(raw_text)
    full_context = "\n\n".join(user_memory[user_id])

    prompt = f"""Based on the WhatsApp chat below, suggest 3 different response options the user can send. 
Each response should be natural and slightly varied in tone.

Chat:
{full_context}

Reply options:"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You help the user draft smart and natural replies."},
                {"role": "user", "content": prompt}
            ]
        )
        reply_text = response.choices[0].message.content.strip()
        options = [opt.strip() for opt in reply_text.split("Option") if opt.strip()]
        keyboard = []
        for i, opt in enumerate(options):
            if ':' in opt:
                _, text = opt.split(':', 1)
            else:
                text = opt
            keyboard.append([InlineKeyboardButton(f"💬 Use Option {i+1}", callback_data=text.strip())])
        reply_with_buttons = "\n\n".join([f"Option {i+1}:\n{text.strip()}" for i, text in enumerate(options)])
        update.message.reply_text(reply_with_buttons, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        print("❌ Exception occurred while calling OpenAI:")
        traceback.print_exc()  # Shows the full error trace
        update.message.reply_text("Error generating options. Please try again.")

def handle_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    selected_reply = query.data
    last_reply[user_id] = selected_reply
    query.message.reply_text(f"✅ Suggested reply:\n\n{selected_reply}\n\n✏️ To revise, type: /revise your instruction")

def handle_revise(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    instruction = update.message.text.replace("/revise", "").strip()
    if user_id not in last_reply:
        update.message.reply_text("⚠️ No previous reply found. Please select a reply option first.")
        return
    base_reply = last_reply[user_id]
    revision_prompt = f"""Here is a WhatsApp reply I’m about to send:\n\n{base_reply}\n\nPlease revise it based on this instruction: "{instruction}"\nReturn just the revised message, nothing else."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You revise WhatsApp replies based on user instructions."},
                {"role": "user", "content": revision_prompt}
            ]
        )
        revised = response.choices[0].message.content.strip()
        last_reply[user_id] = revised
        update.message.reply_text(f"✏️ Revised Reply:\n\n{revised}")
    except Exception as e:
        print("❌ Revision error:", e)
        update.message.reply_text("⚠️ Couldn't revise the message. Try again later.")

def reset_memory(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_memory[user_id].clear()
    update.message.reply_text("🧹 Chat memory cleared.")

def main():
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("reset", reset_memory))
    dp.add_handler(CommandHandler("revise", handle_revise))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(CallbackQueryHandler(handle_callback))
    print("🤖 Bot with buttons is running...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    import os
    main()
