
import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    level=logging.INFO,
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_KEY = os.getenv("TWELVE_DATA_API_KEY")

# Only this Telegram group is allowed to use the bot.
# You can override this in FadeHost Environment Variables if needed.
ALLOWED_GROUP_ID = int(os.getenv("ALLOWED_GROUP_ID", "-1004383626747"))

PAIRS = {
    "gold": ("XAU/USD", "🥇 GOLD", 2),
    "btc": ("BTC/USD", "₿ BITCOIN", 2),
    "eurusd": ("EUR/USD", "💶 EUR/USD", 5),
    "gbpusd": ("GBP/USD", "💷 GBP/USD", 5),
}


def is_allowed_group(update: Update) -> bool:
    """Return True only for the configured Telegram group/supergroup."""
    chat = update.effective_chat
    return (
        chat is not None
        and chat.type in ("group", "supergroup")
        and chat.id == ALLOWED_GROUP_ID
    )



def current_time():
    return datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%d %b %Y | %I:%M:%S %p IST")


async def fetch_price(symbol):
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            "https://api.twelvedata.com/price",
            params={
                "symbol": symbol,
                "apikey": API_KEY,
            },
        )

        response.raise_for_status()
        data = response.json()

        if "price" not in data:
            raise ValueError(
                data.get("message", "Price unavailable")
            )

        return float(data["price"])


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_allowed_group(update):
        return

    message = (
        "🤖 LEO PRICE BOT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📊 MARKET PRICE COMMANDS\n\n"
        "🥇 /gold - Gold (XAUUSD)\n"
        "₿ /btc - Bitcoin (BTCUSD)\n"
        "💶 /eurusd - EUR/USD\n"
        "💷 /gbpusd - GBP/USD\n"
        "📈 /all - All Market Prices\n\n"
        "⚡ Latest Available Market Quotes"
    )

    await update.message.reply_text(message)


async def price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_allowed_group(update):
        return

    command = (
        update.message.text
        .split()[0]
        .split("@")[0]
        .replace("/", "")
        .lower()
    )

    symbol, label, digits = PAIRS[command]

    try:
        price = await fetch_price(symbol)

        message = (
            "📊 LEO MARKET UPDATE\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"{label}\n\n"
            f"💰 Price: {price:,.{digits}f}\n\n"
            f"🕒 Checked: {current_time()}\n"
            "━━━━━━━━━━━━━━━━━━"
        )

        await update.message.reply_text(message)

    except Exception as error:
        print(f"PRICE ERROR [{symbol}]: {type(error).__name__}: {error}")

        await update.message.reply_text(
            f"❌ {symbol} price unavailable.\n"
            "Please try again later."
        )


async def all_prices(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_allowed_group(update):
        return

    results = await asyncio.gather(
        *(
            fetch_price(symbol)
            for symbol, _, _ in PAIRS.values()
        ),
        return_exceptions=True
    )

    lines = [
        "📊 LEO MARKET PRICES",
        "━━━━━━━━━━━━━━━━━━",
        ""
    ]

    for (_, (symbol, label, digits)), result in zip(
        PAIRS.items(), results
    ):
        if isinstance(result, BaseException):
            lines.append(f"{label}: Unavailable")
        else:
            lines.append(
                f"{label}: {result:,.{digits}f}"
            )

    lines.extend([
        "",
        f"🕒 Checked: {current_time()}",
        "━━━━━━━━━━━━━━━━━━",
        "⚡ Latest Available Market Quotes"
    ])

    await update.message.reply_text(
        "\n".join(lines)
    )



async def startup_check(app):
    me = await app.bot.get_me()
    print(f"TELEGRAM CONNECTED AS: @{me.username} (id={me.id})")
    print(f"ALLOWED GROUP ID: {ALLOWED_GROUP_ID}")


async def debug_incoming_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    if chat and message:
        print(
            f"INCOMING UPDATE: chat_id={chat.id}, "
            f"chat_type={chat.type}, text={message.text!r}, "
            f"allowed={is_allowed_group(update)}"
        )


async def log_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"TELEGRAM ERROR: {context.error!r}")


def main():
    if not TOKEN:
        raise RuntimeError(
            "Telegram token missing in .env"
        )

    if not API_KEY:
        raise RuntimeError(
            "Twelve Data API key missing in .env"
        )

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(startup_check)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    for command in PAIRS:
        app.add_handler(
            CommandHandler(command, price_command)
        )

    app.add_handler(
        CommandHandler("all", all_prices)
    )

    # Diagnostic logger: confirms whether Telegram is delivering group commands.
    app.add_handler(
        MessageHandler(filters.COMMAND, debug_incoming_command),
        group=1,
    )
    app.add_error_handler(log_error)

    print("Leo Price Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
