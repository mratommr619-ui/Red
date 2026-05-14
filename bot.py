import time
import os
import re
import requests
import json
import gspread
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials
from ntscraper import Nitter

# --- Configuration ---
START_TIME = time.time()
MAX_RUN_TIME = 19800  # ၅ နာရီ ၃၀ မိနစ် (GitHub Timeout မဖြစ်ခင် Restart ရန်)
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))

# Google Sheets ချိတ်ဆက်ခြင်း
def get_sheet():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        gc = gspread.authorize(creds)
        # သင့် Sheet Link (စစ်ဆေးပြီးသား)
        return gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1
    except Exception as e:
        print(f"❌ Sheet Error: {e}")
        return None

def find_binance_code(text):
    return re.findall(r'\b[A-Z0-9]{8}\b', text.upper())

def trigger_restart():
    """GitHub Actions ကို အသစ်ပြန်စရန် API မှတစ်ဆင့် လှမ်းနှိုးခြင်း"""
    print("🔄 Restarting workflow...")
    url = f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/dispatches"
    headers = {
        "Authorization": f"token {os.getenv('GH_PAT')}",
        "Accept": "application/vnd.github.v3+json"
    }
    requests.post(url, headers=headers, json={"event_type": "restart_bot"})

async def main():
    print("🚀 Bot is starting...")
    client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                            int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    
    await client.start()
    print("✅ Telegram Connected!")
    await client.send_message(MY_CHAT_ID, "🤖 **Bot Is Online!**\n(၅ နာရီခွဲတိုင်း အလိုအလျောက် Restart လုပ်ပါမည်။)")

    # ၁။ Telegram Monitor
    @client.on(events.NewMessage())
    async def telegram_handler(event):
        try:
            sheet = get_sheet()
            records = sheet.get_all_records()
            tg_list = [r['Link'].strip().replace('@', '').split('/')[-1] for r in records if r['Type'].upper() == 'TG']
            
            chat = await event.get_chat()
            username = getattr(chat, 'username', None)

            if username in tg_list:
                codes = find_binance_code(event.raw_text)
                for c in codes:
                    await client.send_message(MY_CHAT_ID, f"🎁 **TG Code:** `{c}`\n🔗 From: @{username}")
        except: pass

    # ၂။ Add Link Command (/add TG @channel)
    @client.on(events.NewMessage(pattern='/add'))
    async def add_command(event):
        if event.sender_id != MY_CHAT_ID: return
        try:
            sheet = get_sheet()
            parts = event.raw_text.split(' ')
            p_type, p_link = parts[1].upper(), parts[2]
            sheet.append_row([p_type, p_link])
            await event.respond(f"✅ Added: [{p_type}] {p_link}")
        except:
            await event.respond("❌ Format: `/add TG @channel`")

    # ၃။ Periodic Scraper (X & YouTube)
    while True:
        elapsed = time.time() - START_TIME
        print(f"⏳ Running time: {int(elapsed/60)} mins")

        try:
            sheet = get_sheet()
            records = sheet.get_all_records()
            
            # X (Twitter) Scraping
            x_links = [r['Link'] for r in records if r['Type'].upper() == 'X']
            scraper = Nitter()
            for link in x_links:
                user = link.strip().split('/')[-1]
                tweets = scraper.get_tweets(user, mode='user', number=2)
                for t in tweets['tweets']:
                    codes = find_binance_code(t['text'])
                    for c in codes:
                        await client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 From: {user}")
        except Exception as e:
            print(f"⚠️ Scraping Loop Error: {e}")

        # အချိန်စစ်ပြီး Restart လုပ်ခြင်း
        if elapsed > MAX_RUN_TIME:
            await client.send_message(MY_CHAT_ID, "🔄 ၅ နာရီခွဲပြည့်သဖြင့် Restart လုပ်နေပါသည်။")
            trigger_restart()
            break
            
        await asyncio.sleep(600) # ၁၀ မိနစ်တစ်ခါ စစ်မည်

if __name__ == "__main__":
    asyncio.run(main())
