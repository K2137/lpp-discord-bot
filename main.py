import discord
import asyncio
import aiohttp
import csv
import datetime
import json
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CONFIG_FILE = "config.json"


config = {
    "threshold_high": 15000,
    "threshold_low": 12000,
    "monitoring": False,
    "alert_high_sent": False,
    "alert_low_sent": False,
    "start_price": None,
    "last_summary_date": None
}


try:
    with open(CONFIG_FILE, "r") as f:
        config.update(json.load(f))
except FileNotFoundError:
    pass


def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)


async def fetch_lpp_price():
    url = "https://stooq.pl/q/l/?s=lpp.pl&i=1"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                lines = text.strip().split("\n")
                if len(lines) >= 2:
                    row = list(csv.reader([lines[1]]))[0]
                    return float(row[5])
    except:
        pass
    return None


def is_trading_time():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2)))
    return now.weekday() < 5 and datetime.time(8, 30) <= now.time() <= datetime.time(17, 30)


async def monitor_price(bot):
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)

    while not bot.is_closed():
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=2)))
        today = str(now.date())

        if config["monitoring"] and is_trading_time():
            price = await fetch_lpp_price()

            if price is not None:

                
                if config["start_price"] is None and now.time() >= datetime.time(8, 30):
                    config["start_price"] = price
                    save_config()
                    print(f"[INFO] Zapisano start_price: {price} zł")

                
                if price > config["threshold_high"] and not config["alert_high_sent"]:
                    await channel.send(f"Cena LPP przekroczyła próg górny: {price} zł")
                    config["alert_high_sent"] = True
                    config["alert_low_sent"] = False
                    save_config()

                elif price < config["threshold_low"] and not config["alert_low_sent"]:
                    await channel.send(f"Cena LPP spadła poniżej progu dolnego: {price} zł")
                    config["alert_low_sent"] = True
                    config["alert_high_sent"] = False
                    save_config()
            
            if now.time().hour == 17 and now.time().minute == 30:
                if config["last_summary_date"] != today and config["start_price"] is not None and price is not None:
                    difference = round(price - config["start_price"], 2)
                    await channel.send(
                        f"Podsumowanie dnia {today}:\n"
                        f"Cena początkowa: {config['start_price']} zł\n"
                        f"Cena końcowa: {price} zł\n"
                        f"Zmiana: {difference:+} zł"
                    )
                    config["last_summary_date"] = today
                    config["start_price"] = None
                    save_config()

        await asyncio.sleep(60)

# Konfiguracja Discord
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"✅ BOT URUCHOMIONY – zalogowano jako {bot.user}")
    bot.loop.create_task(monitor_price(bot))

@bot.event
async def on_message(message):
    if message.author.bot or message.channel.id != CHANNEL_ID:
        return

    content = message.content.lower()

    if content.startswith("!start"):
        config["monitoring"] = True
        save_config()
        await message.channel.send("✅ Monitoring uruchomiony.")

    elif content.startswith("!stop"):
        config["monitoring"] = False
        save_config()
        await message.channel.send("⛔ Monitoring zatrzymany.")

    elif content.startswith("!sethigh"):
        try:
            val = int(content.split()[1])
            config["threshold_high"] = val
            save_config()
            await message.channel.send(f"Ustawiono nowy próg górny: {val} zł")
        except:
            await message.channel.send("❌ Błąd: użyj `!sethigh 15000`")

    elif content.startswith("!setlow"):
        try:
            val = int(content.split()[1])
            config["threshold_low"] = val
            save_config()
            await message.channel.send(f"Ustawiono nowy próg dolny: {val} zł")
        except:
            await message.channel.send("❌ Błąd: użyj `!setlow 12000`")

    elif content.startswith("!status"):
        await message.channel.send(
            f"📊 Status:\nMonitoring: {'włączony' if config['monitoring'] else 'wyłączony'}\n"
            f"Próg górny: {config['threshold_high']} zł\n"
            f"Próg dolny: {config['threshold_low']} zł"
        )
    elif content.startswith("!price"):
        price = await fetch_lpp_price()
        if price is not None:
            await message.channel.send(f"Aktualna cena LPP: {price} zł")
        else:
            await message.channel.send("❌ Nie udało się pobrać aktualnej ceny.")
bot.run(TOKEN)
