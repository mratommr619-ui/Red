import time
import os
import re
import requests
import json
import gspread
import cv2
import easyocr
import yt_dlp
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials
from ntscraper import Nitter

# --- Configuration ---
START_TIME = time.time()
MAX_RUN_TIME = 19500 
OCR_READER = easyocr.Reader(['en'])
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))

# Google Sheets Connect
def get_sheet():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        gc = gspread.authorize(creds)
        # သင့် Sheet ID ကို ဒီမှာ သေချာစစ်ပါ
        return gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1
    except Exception as e:
        print(f"❌ Sheet Connection Error: {e}")
        return None

def find_binance_code(text):
    # စာလုံးကြီးနှင့် ဂဏန်း ၈ လုံးတွဲကို ရှာသည်
    return re.findall(r'\b[A-Z0-9]{8}\b', text)

def trigger_restart():
    url = f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/actions/workflows/main.yml/dispatches"
    headers = {"Authorization": f"token {os.getenv('GH_PAT')}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"ref": "main"})
    print("🔄 Restarting workflow for next cycle...")

async def main():
    print("🚀 Starting Red Packet Bot...")
    
    sheet = get_sheet()
    if not sheet: return

    client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                            int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    
    await client.start()
    print("✅ Telegram Client Started!")
    await client.send_message(MY_CHAT_ID, "🤖 Bot Is Now Online & Monitoring!")

    # ၁။ Telegram Monitor
    @client.on(events.NewMessage())
    async def code_listener(event):
        try:
            records = sheet.get_all_records()
            # @ ပါတာတွေကို ဖြုတ်ပြီး username သီးသန့်ယူမယ်
            tg_list = [r['Link'].strip().replace('@', '').split('/')[-1] for r in records if r['Type'].upper() == 'TG']
            
            chat = await event.get_chat()
            username = getattr(chat, 'username', None)

            if username in tg_list:
                print(f"📩 New Message from {username}: {event.raw_text[:50]}...")
                codes = find_binance_code(event.raw_text.upper())
                for c in codes:
                    print(f"🎯 Found Code: {c}")
                    await client.send_message(MY_CHAT_ID, f"🎁 **Telegram Code:** `{c}`\n🔗 From: @{username}")
        except Exception as e:
            print(f"⚠️ Listener Error: {e}")

    # ၂။ Add Link Command
    @client.on(events.NewMessage(pattern='/add'))
    async def add_link(event):
        if event.sender_id != MY_CHAT_ID: return
        try:
            parts = event.raw_text.split(' ')
            p_type, p_link = parts[1].upper(), parts[2]
            sheet.append_row([p_type, p_link])
            await event.respond(f"✅ Added to Sheet: [{p_type}] {p_link}")
            print(f"📝 Added new link: {p_link}")
        except:
            await event.respond("❌ Format: `/add TG @channel`")

    # ၃။ Periodic Scraper (X & YouTube)
    while True:
        print("🔍 Checking X and YouTube for new codes...")
        try:
            records = sheet.get_all_records()
            x_links = [r['Link'] for r in records if r['Type'].upper() == 'X']
            scraper = Nitter()

            for link in x_links:
                user = link.strip().split('/')[-1]
                print(f"🐦 Checking X user: {user}")
                tweets = scraper.get_tweets(user, mode='user', number=2)
                for t in tweets['tweets']:
                    codes = find_binance_code(t['text'].upper())
                    for c in codes:
                        await client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 User: {user}")
        except Exception as e:
            print(f"⚠️ Scraper Loop Error: {e}")

        # ၅ နာရီခွဲပြည့်ရင် Restart လုပ်မယ်
        if time.time() - START_TIME > MAX_RUN_TIME:
            trigger_restart()
            break
            
        print("💤 Sleeping for 10 minutes...")
        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
