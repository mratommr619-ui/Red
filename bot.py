import time
import os
import re
import requests
import json
import gspread
import asyncio
import easyocr
import feedparser
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials
from ntscraper import Nitter

# --- Global Configurations ---
START_TIME = time.time()
MAX_RUN_TIME = 19800  # 5.5 hours for GitHub Actions
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))
READER = easyocr.Reader(['en'])
PROCESSED_VIDEOS = set() # တစ်ကြိမ် run တိုင်း video အဟောင်းတွေ ထပ်မပို့ရန်

# Google Sheets Connection
def get_sheet():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        gc = gspread.authorize(creds)
        # မိတ်ဆွေရဲ့ Sheet URL ကို ဒီမှာ ပြန်စစ်ပေးပါ
        return gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1
    except Exception as e:
        print(f"❌ Sheet Connection Error: {e}")
        return None

# Binance Code ရှာဖွေသည့် Regex (၈ လုံးပါ စာသား)
def find_binance_code(text):
    if not text: return []
    return re.findall(r'\b[A-Z0-9]{8}\b', text.upper())

# GitHub ကို Restart လုပ်ခိုင်းသည့်စနစ်
def trigger_restart():
    repo = os.getenv('GITHUB_REPOSITORY')
    url = f"https://api.github.com/repos/{repo}/dispatches"
    headers = {
        "Authorization": f"token {os.getenv('GH_PAT')}",
        "Accept": "application/vnd.github.v3+json"
    }
    requests.post(url, headers=headers, json={"event_type": "restart_bot"})
    print("🔄 Restart signal sent to GitHub Actions.")

async def main():
    # ၁။ Telegram Clients (User client for monitor, Bot client for alert)
    user_client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                                 int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    bot_client = TelegramClient('bot', int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))

    await user_client.start()
    await bot_client.start(bot_token=os.getenv("BOT_TOKEN"))
    
    print("✅ Bot is Online and Running Native RSS Mode!")

    # --- Telegram Monitor (Incoming Messages) ---
    @user_client.on(events.NewMessage())
    async def handler(event):
        try:
            sheet = get_sheet()
            if not sheet: return
            records = sheet.get_all_records()
            tg_list = [r['Link'].strip().replace('@', '').replace('https://t.me/', '').split('/')[-1] 
                       for r in records if r['Type'].upper() == 'TG']
            
            chat = await event.get_chat()
            username = getattr(chat, 'username', None)
            
            if username in tg_list or str(event.chat_id) in tg_list:
                codes = find_binance_code(event.raw_text)
                for c in set(codes):
                    await bot_client.send_message(MY_CHAT_ID, f"🎁 **TG Code Found:** `{c}`\n🔗 From: @{username if username else event.chat_id}")
        except: pass

    # --- Scanning Loop (YouTube & X) ---
    while True:
        # ၅ နာရီခွဲပြည့်ရင် Restart လုပ်မည်
        if time.time() - START_TIME > MAX_RUN_TIME:
            trigger_restart()
            break
        
        sheet = get_sheet()
        if not sheet: 
            await asyncio.sleep(60)
            continue
            
        records = sheet.get_all_records()
        print(f"🔄 Scanning {len(records)} entries from Sheet...")

        # A. YouTube RSS Logic (Native Mode)
        yt_rss_links = [r['Link'] for r in records if r['Type'].upper() == 'YT']
        for rss_url in yt_rss_links:
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries:
                    v_id = entry.yt_videoid if 'yt_videoid' in entry else entry.link
                    if v_id in PROCESSED_VIDEOS: continue
                    
                    # ၁။ စာသားထဲမှာ ရှာမယ်
                    codes = find_binance_code(entry.title + " " + (entry.summary if 'summary' in entry else ""))
                    
                    # ၂။ Thumbnail OCR ဖတ်မယ်
                    img_url = f"https://img.youtube.com/vi/{v_id}/maxresdefault.jpg"
                    img_res = requests.get(img_url)
                    if img_res.status_code == 200:
                        with open('temp.jpg', 'wb') as f: f.write(img_res.content)
                        results = READER.readtext('temp.jpg')
                        for (_, text, _) in results:
                            codes.extend(find_binance_code(text))
                    
                    # Code တွေ့ရင် ပို့မယ်
                    final_codes = set(codes)
                    if final_codes:
                        for c in final_codes:
                            await bot_client.send_message(MY_CHAT_ID, f"📺 **YouTube Code:** `{c}`\n🔗 {entry.link}")
                    
                    PROCESSED_VIDEOS.add(v_id)
            except Exception as e:
                print(f"❌ YouTube RSS Error: {e}")

        # B. X (Twitter) Logic
        x_links = [r['Link'] for r in records if r['Type'].upper() == 'X']
        if x_links:
            scraper = Nitter()
            for link in x_links:
                try:
                    user = link.strip().split('/')[-1]
                    tweets = scraper.get_tweets(user, mode='user', number=2)
                    for t in tweets['tweets']:
                        for c in find_binance_code(t['text']):
                            await bot_client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 From: {user}")
                except: pass

        await asyncio.sleep(600) # ၁၀ မိနစ်တစ်ခါ စစ်မည်

if __name__ == "__main__":
    asyncio.run(main())
