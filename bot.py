import time
import os
import re
import requests
import gspread
import cv2
import easyocr
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from googleapiclient.discovery import build
from ntscraper import Nitter
from google.oauth2.service_account import Credentials

# --- Settings & Secrets ---
# (Secrets တွေထဲမှာ အကုန်ထည့်ထားရပါမယ်)
START_TIME = time.time()
MAX_RUN_TIME = 19000 
reader = easyocr.Reader(['en']) # OCR အတွက်

# Google Sheet Setup
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# JSON Key ကို GitHub Secret ထဲမှာ string အနေနဲ့ ထည့်ထားပါ
creds_dict = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
gc = gspread.authorize(creds)
sheet = gc.open("RedPacketBot_DB").sheet1 # Sheet အမည်

def get_links_from_sheet():
    """Sheet ထဲက Link စာရင်းကို Platform အလိုက် ခွဲထုတ်ပေးသည်"""
    records = sheet.get_all_records()
    data = {"TG": [], "YT": [], "X": []}
    for row in records:
        link = row['Link']
        p_type = row['Type'].upper()
        if p_type in data: data[p_type].append(link)
    return data

def find_code(text):
    """စာသားထဲက Binance Code ဖော်မတ်ကို ရှာပေးသည်"""
    return re.findall(r'\b[A-Z0-9]{8}\b', text)

# --- Platform Scrapers ---

async def monitor_telegram(client, channels):
    @client.on(events.NewMessage(chats=channels))
    async def handler(event):
        codes = find_code(event.raw_text)
        for c in codes:
            await client.send_message(int(os.getenv("MY_CHAT_ID")), f"🎯 **TG Code:** `{c}`")

def check_twitter(accounts):
    scraper = Nitter()
    for acc in accounts:
        # Link ထဲကနေ username ထုတ်ယူခြင်း
        username = acc.split('/')[-1]
        tweets = scraper.get_tweets(username, mode='user', number=2)
        for tweet in tweets['tweets']:
            codes = find_code(tweet['text'])
            # ပို့ပေးမယ့် logic... (Telegram bot api သုံးပြီး ပို့ရန်)

def check_youtube(channel_links):
    # YouTube API သို့မဟုတ် Description/Comment စစ်သည့် logic...
    pass

# --- Main Logic ---

async def main():
    # Telegram Client စတင်ခြင်း
    client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                            int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    await client.start()

    print("Bot Started...")
    
    while True:
        links = get_links_from_sheet()
        
        # ၁။ Telegram Monitor က Background မှာ အလုပ်လုပ်နေပါမယ်
        
        # ၂။ Twitter ကို Polling လုပ်မယ် (၁၀ မိနစ်တစ်ခါ)
        check_twitter(links['X'])
        
        # ၃။ YouTube ကို Polling လုပ်မယ်
        check_youtube(links['YT'])

        # အချိန်စစ်ပြီး Restart လုပ်ခြင်း
        if time.time() - START_TIME > MAX_RUN_TIME:
            # Trigger GitHub API to restart
            trigger_restart()
            break
        
        await time.sleep(600) # ၁၀ မိနစ်နားမယ်

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
