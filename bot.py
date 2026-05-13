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
MAX_RUN_TIME = 19500  # ၅ နာရီ ၂၅ မိနစ်ခန့်
OCR_READER = easyocr.Reader(['en'])
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))

# Google Sheets Setup
def get_sheet():
    creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scope)
    gc = gspread.authorize(creds)
    return gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1

sheet = get_sheet()

def find_binance_code(text):
    return re.findall(r'\b[A-Z0-9]{8}\b', text)

def trigger_restart():
    url = f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/actions/workflows/main.yml/dispatches"
    headers = {"Authorization": f"token {os.getenv('GH_PAT')}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"ref": "main"})

# --- Main Bot Logic ---
async def main():
    client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                            int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    await client.start()
    print("Red Packet Bot is ONLINE!")

    # ၁။ Telegram ကနေ ကုဒ်ဖမ်းခြင်း
    @client.on(events.NewMessage())
    async def code_listener(event):
        # Sheet ထဲက TG channel စာရင်းကို စစ်မယ်
        records = sheet.get_all_records()
        tg_list = [r['Link'].replace('@', '') for r in records if r['Type'].upper() == 'TG']
        
        if event.chat and getattr(event.chat, 'username', None) in tg_list:
            codes = find_binance_code(event.raw_text)
            for c in codes:
                await client.send_message(MY_CHAT_ID, f"🎁 **Telegram Code:** `{c}`")

    # ၂။ Command ဖြင့် Link အသစ်ထည့်ခြင်း (/add Type Link)
    @client.on(events.NewMessage(pattern='/add'))
    async def add_link(event):
        if event.sender_id != MY_CHAT_ID: return
        try:
            _, p_type, p_link = event.raw_text.split(' ')
            sheet.append_row([p_type.upper(), p_link])
            await event.respond(f"✅ ပေါင်းထည့်ပြီးပါပြီ - [{p_type}] {p_link}")
        except:
            await event.respond("⚠️ ပုံစံမှားနေပါသည်။ `/add TG @channel` ဟု ရိုက်ပါ။")

    # ၃။ ပတ်ချာလည်စစ်ဆေးမည့် Loop (YouTube & X)
    while True:
        # X (Twitter) ကို စစ်ဆေးခြင်း
        records = sheet.get_all_records()
        x_links = [r['Link'] for r in records if r['Type'].upper() == 'X']
        scraper = Nitter()
        for link in x_links:
            try:
                user = link.split('/')[-1]
                tweets = scraper.get_tweets(user, mode='user', number=1)
                for t in tweets['tweets']:
                    codes = find_binance_code(t['text'])
                    for c in codes:
                        await client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`")
            except: pass

        # အချိန်စစ်ပြီး Restart လုပ်ခြင်း
        if time.time() - START_TIME > MAX_RUN_TIME:
            trigger_restart()
            break
            
        await time.sleep(600) # ၁၀ မိနစ်တစ်ခါ Loop ပတ်မယ်

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
