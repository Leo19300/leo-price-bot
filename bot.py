
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
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_KEY = os.getenv("TWELVE_DATA_API_KEY")

# Only this Telegram group can use the bot
ALLOWED_GROUP_ID = -1004383626747

PAIRS = {
    "gold": ("XAU/USD", "🥇 GOLD", 2),
    "btc": ("BTC/USD", "₿ BITCOIN", 2),
    "eurusd": ("EUR/USD", "💶 EUR/USD", 5),
    "gbpusd": ("GBP/USD", "💷 GBP/USD", 5),
}

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("leo_price_bot")


def is_allowed(update: Update) -> bool:
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
    if not is_allowed(update):
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
    if not is_allowed(update):
        return

    command = (
        update.message.text
        .split()[0]
        .split("@")[0]
        .replace("/", "")
        .lower()
    )

    if command not in PAIRS:
        return

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
        logger.error(
            "Price error for %s: %s",
            symbol,
            type(error).__name__,
        )
        await update.message.reply_text(
            f"❌ {symbol} price unavailable.\n"
            "Please try again later."
        )


async def all_prices(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not is_allowed(update):
        return

    results = await asyncio.gather(
        *(
            fetch_price(symbol)
            for symbol, _, _ in PAIRS.values()
        ),
        return_exceptions=True,
    )

    lines = [
        "📊 LEO MARKET PRICES",
        "━━━━━━━━━━━━━━━━━━",
        "",
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
        "⚡ Latest Available Market Quotes",
    ])

    await update.message.reply_text(
        "\n".join(lines)
    )


def main():
    if not TOKEN:
        raise RuntimeError(
            "Telegram token missing"
        )

    if not API_KEY:
        raise RuntimeError(
            "Twelve Data API key missing"
        )

    app = (
        ApplicationBuilder()
        .token(TOKEN)
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

    print(
        "Leo Price Bot V3 - Private Group Lock Active",
        flush=True,
    )

    app.run_polling()


if __name__ == "__main__":
    main()
