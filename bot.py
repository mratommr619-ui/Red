import time
import os
import re
import requests
import json
import gspread
import asyncio
import easyocr
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials
from ntscraper import Nitter

# --- Config ---
START_TIME = time.time()
MAX_RUN_TIME = 19800 
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))
READER = easyocr.Reader(['en'], gpu=False) 
BLACKLIST = ["GIVEAWAY", "GRAPHICS", "AIRDROPS", "BINANCE", "CHANNELS", "REGISTER", "DOWNLOAD", "DAILYNEW"]

# ထပ်နေတာတွေ မပို့အောင် မှတ်ထားရန်
SENT_CODES = set()

def find_binance_code(text):
    if not text: return []
    found = re.findall(r'\b[A-Z0-9]{8}\b', text.upper())
    return [c for c in found if c not in BLACKLIST and any(char.isdigit() for char in c)]

def get_sheet():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        gc = gspread.authorize(creds)
        return gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1
    except: return None

# Telegram OCR Function
async def process_tg_message(event, bot_client, username):
    codes = find_binance_code(event.raw_text)
    if event.photo:
        photo = await event.download_media("tg_img.jpg")
        for (_, text, _) in READER.readtext(photo):
            codes.extend(find_binance_code(text))
        if os.path.exists(photo): os.remove(photo)
    
    for c in set(codes):
        if c not in SENT_CODES:
            await bot_client.send_message(MY_CHAT_ID, f"🎁 **Telegram Code:** `{c}`\n🔗 From: @{username}")
            SENT_CODES.add(c)
            print(f"✨ Found and Sent: {c}")

async def main():
    user_client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                                 int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    bot_client = TelegramClient('bot', int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))

    await user_client.start()
    await bot_client.start(bot_token=os.getenv("BOT_TOKEN"))
    print("🚀 Bot History Scanner is Online!")

    # --- ၁။ Startup History Scan (Telegram) ---
    print("🔍 Scanning Telegram History for last posts...")
    sheet = get_sheet()
    if sheet:
        all_values = sheet.get_all_values()
        tg_list = [row[1].strip().replace('@', '').replace('https://t.me/', '').split('/')[-1] 
                   for row in all_values if len(row) >= 2 and row[0].upper() == 'TG']
        
        for channel in tg_list:
            try:
                # နောက်ဆုံးစာ ၅ စောင်ကို အရင်လှန်ဖတ်မည်
                async for message in user_client.iter_messages(channel, limit=5):
                    await process_tg_message(message, bot_client, channel)
            except: pass

    # --- ၂။ New Message Monitoring ---
    @user_client.on(events.NewMessage())
    async def handler(event):
        try:
            chat = await event.get_chat()
            username = getattr(chat, 'username', None) or str(event.chat_id)
            await process_tg_message(event, bot_client, username)
        except: pass

    # --- ၃။ Scraper Loop (X + History) ---
    while True:
        if time.time() - START_TIME > MAX_RUN_TIME: break
        
        sheet = get_sheet()
        if not sheet: await asyncio.sleep(60); continue
        
        all_values = sheet.get_all_values()
        x_links = [row[1] for row in all_values if len(row) >= 2 and row[0].upper() == 'X']

        if x_links:
            print(f"🐦 Checking {len(x_links)} X Accounts for last tweets...")
            try:
                scraper = Nitter(instances=["https://nitter.net", "https://nitter.cz", "https://nitter.privacydev.net"])
                for link in x_links:
                    user = link.strip().split('/')[-1].split('?')[0]
                    # နောက်ဆုံးတင်ထားတဲ့ ၃ ခုကို အမြဲစစ်မည်
                    tweets = scraper.get_tweets(user, mode='user', number=3)
                    if tweets and 'tweets' in tweets:
                        for t in tweets['tweets']:
                            codes = find_binance_code(t['text'])
                            for c in set(codes):
                                if c not in SENT_CODES:
                                    await bot_client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 From: {user}")
                                    SENT_CODES.add(c)
                                    print(f"✨ Found on X: {c}")
            except Exception as e:
                print(f"⚠️ X Scraper Error: {e}")

        print("😴 Waiting 10 mins...")
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
