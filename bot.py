import time
import os
import re
import requests
import json
import gspread
import asyncio
import cv2
import easyocr
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials
from ntscraper import Nitter

# --- Global Config ---
START_TIME = time.time()
MAX_RUN_TIME = 19800 
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))
YT_API_KEY = os.getenv("YT_API_KEY")
READER = easyocr.Reader(['en'])

# Quota Error မတက်အောင် Sheet ထဲက data တွေကို ဒီထဲမှာ ခဏသိမ်းထားမယ်
RECORDS_CACHE = []

# Google Sheets Connect
def get_sheet():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        gc = gspread.authorize(creds)
        return gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1
    except Exception as e:
        print(f"❌ Sheet Connection Error: {e}")
        return None

def update_cache():
    """Sheet ထဲက Link တွေကို မှတ်ဉာဏ်ထဲမှာ သိမ်းပေးသည်"""
    global RECORDS_CACHE
    sheet = get_sheet()
    if sheet:
        RECORDS_CACHE = sheet.get_all_records()
        print(f"🔄 Cache Updated: {len(RECORDS_CACHE)} links found.")

def find_binance_code(text):
    return re.findall(r'\b[A-Z0-9]{8}\b', text.upper())

def trigger_restart():
    url = f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/dispatches"
    headers = {"Authorization": f"token {os.getenv('GH_PAT')}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"event_type": "restart_bot"})

async def main():
    # ၁။ User Client (စောင့်ကြည့်ရန်)
    user_client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                                 int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    
    # ၂။ Bot Client (စာပို့ရန်)
    bot_client = TelegramClient('bot', int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))

    await user_client.start()
    await bot_client.start(bot_token=os.getenv("BOT_TOKEN"))
    
    # စစချင်း cache ကို အရင်ဖတ်မယ်
    update_cache()
    
    print("✅ Bot is Online and Optimized!")
    await bot_client.send_message(MY_CHAT_ID, "🚀 **Bot Is Online!**\nQuota Error မတက်အောင် Cache စနစ် ထည့်ထားပါတယ်။")

    # Telegram Monitor (Sheet ကို ခဏခဏ မဖတ်တော့ဘဲ cache ကနေပဲ စစ်မယ်)
    @user_client.on(events.NewMessage())
    async def handler(event):
        try:
            tg_list = [r['Link'].strip().replace('@', '').split('/')[-1] for r in RECORDS_CACHE if r['Type'].upper() == 'TG']
            chat = await event.get_chat()
            if getattr(chat, 'username', None) in tg_list:
                codes = find_binance_code(event.raw_text)
                for c in codes:
                    await bot_client.send_message(MY_CHAT_ID, f"🎁 **TG Code:** `{c}`\n🔗 From: @{chat.username}")
        except: pass

    # Link အသစ်ထည့်ပြီးရင် cache ပါ update လုပ်မည့် command
    @user_client.on(events.NewMessage(pattern='/add'))
    async def add_command(event):
        if event.sender_id != MY_CHAT_ID: return
        try:
            sheet = get_sheet()
            parts = event.raw_text.split(' ')
            p_type, p_link = parts[1].upper(), parts[2]
            sheet.append_row([p_type, p_link])
            update_cache() # cache ပါ update လုပ်မယ်
            await event.respond(f"✅ Added & Cache Updated: [{p_type}] {p_link}")
        except:
            await event.respond("❌ Format: `/add TG @channel`")

    # Loop (YouTube & X စစ်ဆေးခြင်း)
    while True:
        elapsed = time.time() - START_TIME
        if elapsed > MAX_RUN_TIME:
            trigger_restart()
            break
        
        # ၁၀ မိနစ်တစ်ခါ cache ကို refresh လုပ်မယ်
        update_cache()

        # YouTube Logic
        try:
            yt_channels = [r['Link'] for r in RECORDS_CACHE if r['Type'].upper() == 'YT']
            for url in yt_channels:
                handle = url.split('@')[-1].split('?')[0]
                search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&maxResults=1&order=date&q={handle}&key={YT_API_KEY}"
                resp = requests.get(search_url).json()
                if 'items' in resp and resp['items']:
                    v_id = resp['items'][0]['id']['videoId']
                    v_text = f"{resp['items'][0]['snippet']['title']} {resp['items'][0]['snippet']['description']}"
                    codes = find_binance_code(v_text)
                    # OCR
                    img_data = requests.get(resp['items'][0]['snippet']['thumbnails']['high']['url']).content
                    with open('t.jpg', 'wb') as f: f.write(img_data)
                    for (_, text, _) in READER.readtext('t.jpg'):
                        codes.extend(find_binance_code(text))
                    for c in set(codes):
                        await bot_client.send_message(MY_CHAT_ID, f"📺 **YouTube Code:** `{c}`\n🔗 https://youtu.be/{v_id}")
        except: pass

        # X Logic
        try:
            x_links = [r['Link'] for r in RECORDS_CACHE if r['Type'].upper() == 'X']
            scraper = Nitter()
            for link in x_links:
                user = link.strip().split('/')[-1]
                tweets = scraper.get_tweets(user, mode='user', number=2)
                for t in tweets['tweets']:
                    for c in find_binance_code(t['text']):
                        await bot_client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 From: {user}")
        except: pass

        await asyncio.sleep(600) # ၁၀ မိနစ်စောင့်မည်

if __name__ == "__main__":
    asyncio.run(main())
