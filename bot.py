import time
import os
import re
import json
import gspread
import asyncio
import easyocr
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials
from twikit import Client

# --- Config ---
START_TIME = time.time()
MAX_RUN_TIME = 19800 
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))
READER = easyocr.Reader(['en'], gpu=False) 
SENT_CODES = set()
BLACKLIST = ["GIVEAWAY", "GRAPHICS", "AIRDROPS", "BINANCE", "CHANNELS", "REGISTER", "DOWNLOAD", "DAILYNEW"]

def find_binance_code(text):
    if not text: return []
    # ၈ လုံးကနေ ၁၀ လုံးကြား code တွေကို ရှာမယ်
    found = re.findall(r'\b[A-Z0-9]{8,10}\b', text.upper())
    return [c for c in found if c not in BLACKLIST]

def get_sheet():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        gc = gspread.authorize(creds)
        return gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1
    except: return None

async def process_tg_message(event, bot_client, label):
    codes = find_binance_code(event.raw_text)
    if event.photo:
        try:
            photo = await event.download_media("tg_img.jpg")
            for (_, text, _) in READER.readtext(photo):
                codes.extend(find_binance_code(text))
            if os.path.exists(photo): os.remove(photo)
        except: pass
    for c in set(codes):
        if c not in SENT_CODES:
            await bot_client.send_message(MY_CHAT_ID, f"🎁 **TG Code:** `{c}`\n🔗 From: @{label}")
            SENT_CODES.add(c)
            print(f"✨ Found on TG: {c}")

async def main():
    # --- X Client Setup ---
    x_client = Client('en-US')
    try:
        x_client.set_cookies({
            'auth_token': os.getenv("X_AUTH_TOKEN"),
            'ct0': os.getenv("X_CT0")
        })
        print("✅ X Cookie Loaded Successfully!")
    except Exception as e:
        print(f"❌ X Cookie Error: {e}")

    user_client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                                 int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    bot_client = TelegramClient('bot', int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))

    await user_client.start()
    await bot_client.start(bot_token=os.getenv("BOT_TOKEN"))
    print("🚀 Bot v5.1 (X Direct Edition) is Online!")

    # Google Sheet data ယူခြင်း
    sheet = get_sheet()
    tg_list = []
    if sheet:
        all_values = sheet.get_all_values()
        tg_list = [row[1].strip().replace('@', '').replace('https://t.me/', '').split('/')[-1] 
                   for row in all_values if len(row) >= 2 and row[0].upper() == 'TG']

    # Telegram စောင့်ကြည့်ခြင်း
    @user_client.on(events.NewMessage())
    async def handler(event):
        try:
            chat = await event.get_chat()
            username = getattr(chat, 'username', None)
            if username in tg_list:
                await process_tg_message(event, bot_client, username)
        except: pass

    # X Monitoring Loop
    while True:
        if time.time() - START_TIME > MAX_RUN_TIME: break
        
        sheet = get_sheet()
        if not sheet: await asyncio.sleep(60); continue
        all_values = sheet.get_all_values()
        x_links = [row[1] for row in all_values if len(row) >= 2 and row[0].upper() == 'X']

        if x_links:
            print(f"🐦 Checking {len(x_links)} X Accounts...")
            for link in x_links:
                try:
                    username = link.strip().split('/')[-1].split('?')[0]
                    user = await x_client.get_user_by_screen_name(username)
                    tweets = await user.get_tweets('Tweets', count=3)
                    
                    for t in tweets:
                        codes = find_binance_code(t.text)
                        for c in set(codes):
                            if c not in SENT_CODES:
                                await bot_client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 From: @{username}")
                                SENT_CODES.add(c)
                                print(f"✨ Found on X: {c}")
                except Exception as e:
                    print(f"⚠️ Error checking @{username}: {e}")

        print("😴 Waiting 5 mins...")
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())
