import time
import os
import re
import requests
import json
import gspread
import cv2
import easyocr
import yt_dlp
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials
from ntscraper import Nitter

# --- Config & Secrets ---
START_TIME = time.time()
MAX_RUN_TIME = 19000  # ၅ နာရီ ၁၅ မိနစ်ဝန်းကျင်
OCR_READER = easyocr.Reader(['en'])

def find_binance_code(text):
    """စာသားထဲက ၈ လုံးတွဲ Binance Code ကို ရှာပေးသည်"""
    return re.findall(r'\b[A-Z0-9]{8}\b', text)

# --- GitHub Restart Logic ---
def trigger_restart():
    url = f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/actions/workflows/main.yml/dispatches"
    headers = {
        "Authorization": f"token {os.getenv('GH_PAT')}",
        "Accept": "application/vnd.github.v3+json"
    }
    requests.post(url, headers=headers, json={"ref": "main"})
    print("Restart triggered for next cycle.")

# --- Google Sheets Interface ---
def get_links():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        gc = gspread.authorize(creds)
        # Sheet Link သို့မဟုတ် နာမည်ဖြင့် ဖွင့်ပါ
        sh = gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1
        records = sh.get_all_records()
        return records
    except Exception as e:
        print(f"Sheet Error: {e}")
        return []

# --- YouTube & X Scrapers ---
def scan_youtube(links, client, chat_id):
    # YouTube description/comment logic... (Simplified for performance)
    pass

def scan_x(links, client, chat_id):
    scraper = Nitter()
    for link in links:
        if 'x.com' in link or 'twitter.com' in link:
            username = link.split('/')[-1]
            try:
                tweets = scraper.get_tweets(username, mode='user', number=1)
                for tweet in tweets['tweets']:
                    codes = find_binance_code(tweet['text'])
                    for c in codes:
                        client.loop.create_task(client.send_message(chat_id, f"🐦 **X Code:** `{c}`"))
            except: pass

# --- Main Execution ---
async def main():
    api_id = int(os.getenv("TG_API_ID"))
    api_hash = os.getenv("TG_API_HASH")
    session = os.getenv("TG_STRING_SESSION")
    chat_id = int(os.getenv("MY_CHAT_ID"))

    client = TelegramClient(StringSession(session), api_id, api_hash)
    await client.start()
    print("Bot is LIVE and Monitoring...")

    # Telegram Real-time Monitor
    @client.on(events.NewMessage())
    async def handler(event):
        links = get_links()
        tg_channels = [r['Link'] for r in links if r['Type'].upper() == 'TG']
        if event.chat and getattr(event.chat, 'username', None) in [c.replace('@', '') for c in tg_channels]:
            codes = find_binance_code(event.raw_text)
            for c in codes:
                await client.send_message(chat_id, f"💎 **Telegram Code:** `{c}`")

    # Periodic Loop for YT & X
    while True:
        links_data = get_links()
        x_links = [r['Link'] for r in links_data if r['Type'].upper() == 'X']
        scan_x(x_links, client, chat_id)

        if time.time() - START_TIME > MAX_RUN_TIME:
            trigger_restart()
            break
        await time.sleep(600) # ၁၀ မိနစ်တစ်ခါ Check လုပ်မယ်

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
