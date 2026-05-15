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

BLACKLIST = ["GIVEAWAY", "GRAPHICS", "AIRDROPS", "BINANCE", "CHANNELS", "REGISTER", "DOWNLOAD", "DAILYNEW", "FOLLOWED", "MESSAGES", "CRYPTOBOX"]
SENT_CODES = set()

# လောလောဆယ် အလုပ်ဖြစ်နိုင်ချေရှိသော Nitter Instances များ
NITTER_INSTANCES = [
    "https://nitter.net", "https://nitter.cz", "https://nitter.privacydev.net",
    "https://nitter.it", "https://nitter.no-logs.com", "https://nitter.perennialte.ch",
    "https://nitter.pw", "https://nitter.rawbit.ninja", "https://nitter.tokhmi.xyz",
    "https://nitter.unixfox.eu", "https://nitter.v0l.me", "https://nitter.bird.froth.zone"
]

def find_binance_code(text):
    if not text: return []
    found = re.findall(r'\b[A-Z0-9]{8,10}\b', text.upper())
    valid_codes = []
    for c in found:
        if c in BLACKLIST: continue
        if any(char.isdigit() for char in c):
            if not c.isalpha(): 
                valid_codes.append(c)
    return valid_codes

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
            await bot_client.send_message(MY_CHAT_ID, f"🎁 **Found Code:** `{c}`\n🔗 From: @{label}")
            SENT_CODES.add(c)

async def main():
    user_client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                                 int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    bot_client = TelegramClient('bot', int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))

    await user_client.start()
    await bot_client.start(bot_token=os.getenv("BOT_TOKEN"))
    print("🚀 Bot v4.1 (X Scraper Re-Fixed) Online!")

    # Sheet Initial Load
    sheet = get_sheet()
    tg_list = []
    if sheet:
        all_values = sheet.get_all_values()
        tg_list = [row[1].strip().replace('@', '').replace('https://t.me/', '').split('/')[-1] 
                   for row in all_values if len(row) >= 2 and row[0].upper() == 'TG']

    @user_client.on(events.NewMessage())
    async def handler(event):
        try:
            chat = await event.get_chat()
            username = getattr(chat, 'username', None)
            if username in tg_list:
                await process_tg_message(event, bot_client, username)
        except: pass

    # Scraper Loop
    scraper = Nitter()
    while True:
        if time.time() - START_TIME > MAX_RUN_TIME: break
        
        sheet = get_sheet()
        if not sheet: await asyncio.sleep(60); continue
        all_values = sheet.get_all_values()
        x_links = [row[1] for row in all_values if len(row) >= 2 and row[0].upper() == 'X']

        if x_links:
            print(f"🐦 Checking {len(x_links)} X Accounts...")
            for link in x_links:
                user = link.strip().split('/')[-1].split('?')[0]
                success = False
                # အလုပ်လုပ်တဲ့ Instance ကိုတွေ့တဲ့အထိ စမ်းမယ်
                for instance in NITTER_INSTANCES:
                    try:
                        scraper.instance = instance
                        tweets = scraper.get_tweets(user, mode='user', number=3)
                        if tweets and 'tweets' in tweets:
                            for t in tweets['tweets']:
                                for c in find_binance_code(t['text']):
                                    if c not in SENT_CODES:
                                        await bot_client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 From: {user}")
                                        SENT_CODES.add(c)
                            success = True
                            break # အောင်မြင်ရင် နောက် Instance စမ်းစရာမလိုတော့ဘူး
                    except:
                        continue # Error တက်ရင် နောက် Server တစ်ခုနဲ့ ထပ်စမ်းမယ်
                
                if not success:
                    print(f"⚠️ Failed to fetch {user} from all instances.")

        print("😴 Waiting 10 mins...")
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
