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

def trigger_restart():
    repo = os.getenv('GITHUB_REPOSITORY')
    url = f"https://api.github.com/repos/{repo}/dispatches"
    headers = {"Authorization": f"token {os.getenv('GH_PAT')}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"event_type": "restart_bot"})

async def main():
    user_client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                                 int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    bot_client = TelegramClient('bot', int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))

    await user_client.start()
    await bot_client.start(bot_token=os.getenv("BOT_TOKEN"))
    print("🚀 Bot (Stable X & TG) is Online!")

    # --- Telegram Monitoring ---
    @user_client.on(events.NewMessage())
    async def handler(event):
        try:
            sheet = get_sheet()
            if not sheet: return
            all_v = sheet.get_all_values()
            tg_list = [r[1].strip().replace('@', '').replace('https://t.me/', '').split('/')[-1] 
                       for r in all_v if len(r) >= 2 and r[0].upper() == 'TG']
            
            chat = await event.get_chat()
            username = getattr(chat, 'username', None)
            if username in tg_list or str(event.chat_id) in tg_list:
                codes = find_binance_code(event.raw_text)
                if event.photo:
                    photo = await event.download_media("tg_img.jpg")
                    for (_, t, _) in READER.readtext(photo):
                        codes.extend(find_binance_code(t))
                    os.remove(photo)
                for c in set(codes):
                    await bot_client.send_message(MY_CHAT_ID, f"🎁 **Telegram Code:** `{c}`")
        except: pass

    # --- Scraper Loop (X/Twitter Only) ---
    while True:
        if time.time() - START_TIME > MAX_RUN_TIME:
            trigger_restart(); break
        
        sheet = get_sheet()
        if not sheet: await asyncio.sleep(60); continue
        
        all_values = sheet.get_all_values()
        x_links = [r[1] for r in all_values if len(r) >= 2 and r[0].upper() == 'X']

        if x_links:
            print(f"🐦 Checking {len(x_links)} X Accounts...")
            try:
                # Stable ဖြစ်တဲ့ Nitter Instance တွေကို Manual သုံးမယ်
                scraper = Nitter(instances=["https://nitter.net", "https://nitter.cz", "https://nitter.privacydev.net"])
                for link in x_links:
                    try:
                        user = link.strip().split('/')[-1].split('?')[0]
                        tweets = scraper.get_tweets(user, mode='user', number=2)
                        if tweets and 'tweets' in tweets:
                            for t in tweets['tweets']:
                                for c in find_binance_code(t['text']):
                                    await bot_client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 From: {user}")
                    except: continue
            except Exception as e:
                print(f"⚠️ X Error: {e}")

        print("😴 Waiting 10 mins...")
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
