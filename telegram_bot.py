import os
import logging
import httpx
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY", "")
ALLOWED_CHAT_ID = int(os.environ.get("ALLOWED_CHAT_ID", "8451506277"))
BOKHALDSRAD_MCP = "https://mcp.bokhaldsrad.is/mcp"

chat_histories = {}

SYSTEM_PROMPT = """You are Jarvis, a highly capable personal AI assistant for Ragnar, a business owner in Iceland who runs Bokhaldsrad (bokhaldsrad.is). You have access to Bokhaldsrad data via MCP tools. Personality: Direct, intelligent, dry wit. Respond in Icelandic if Ragnar writes Icelandic, English if English."""

async def call_claude(user_message: str, chat_id: int) -> str:
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    chat_histories[chat_id].append({"role": "user", "content": user_message})
    messages = chat_histories[chat_id][-20:]
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": messages,
        "mcp_servers": [{"type": "url", "url": BOKHALDSRAD_MCP, "name": "bokhaldsrad"}]
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "mcp-client-2025-04-04"
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
        data = resp.json()
    if "error" in data:
        raise Exception(data["error"]["message"])
    reply = "".join(b["text"] for b in data.get("content", []) if b.get("type") == "text").strip()
    chat_histories[chat_id].append({"role": "assistant", "content": reply})
    return reply

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id != ALLOWED_CHAT_ID:
        return
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    try:
        reply = await call_claude(update.message.text, chat_id)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"// villa: {str(e)}")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    await update.message.reply_text("Jarvis online. Talaðu við mig.")

async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    chat_histories.pop(update.effective_chat.id, None)
    await update.message.reply_text("// samtal hreinsad")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ALLOWED_CHAT_ID: return
    h = len(chat_histories.get(update.effective_chat.id, []))
    await update.message.reply_text(f"// Jarvis online | skilabod: {h}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Jarvis bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
