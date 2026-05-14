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

# --- Config ---
START_TIME = time.time()
MAX_RUN_TIME = 19500 
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))

def get_sheet():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        gc = gspread.authorize(creds)
        # သင့် Sheet Link ကို ဒီမှာ အောက်ဆုံးထိ စစ်ပါ
        return gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1
    except Exception as e:
        print(f"❌ Sheet Error: {e}")
        return None

def find_binance_code(text):
    return re.findall(r'\b[A-Z0-9]{8}\b', text.upper())

async def main():
    print("🚀 Bot ကို စတင်နှိုးနေပါပြီ...")
    
    # Telegram Client ချိတ်ခြင်း
    client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                            int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    
    await client.start()
    print("✅ Telegram ချိတ်ဆက်မှု အောင်မြင်သည်!")
    
    # Bot အသက်ဝင်ကြောင်း သင့်ဆီ စာအရင်ပို့မည်
    await client.send_message(MY_CHAT_ID, "🤖 **Red Packet Bot တက်လာပါပြီ!**\nအခုကစပြီး စောင့်ကြည့်ပေးပါ့မယ်။")

    # ၁။ Telegram Monitor
    @client.on(events.NewMessage())
    async def handler(event):
        try:
            sheet = get_sheet()
            records = sheet.get_all_records()
            # Link ထဲက username ကိုပဲ သန့်ထုတ်ယူမယ်
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
    async def add(event):
        if event.sender_id != MY_CHAT_ID: return
        try:
            sheet = get_sheet()
            _, p_type, p_link = event.raw_text.split(' ')
            sheet.append_row([p_type.upper(), p_link])
            await event.respond(f"✅ ပေါင်းထည့်ပြီးပါပြီ: {p_link}")
        except:
            await event.respond("❌ Format: `/add TG @channel`")

    # ၃။ Scraping Loop (X & YouTube)
    while True:
        print("🔍 Scanning X for codes...")
        try:
            sheet = get_sheet()
            records = sheet.get_all_records()
            x_links = [r['Link'] for r in records if r['Type'].upper() == 'X']
            scraper = Nitter()

            for link in x_links:
                user = link.strip().split('/')[-1]
                tweets = scraper.get_tweets(user, mode='user', number=2)
                for t in tweets['tweets']:
                    codes = find_binance_code(t['text'])
                    for c in codes:
                        await client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 From: {user}")
        except: pass

        if time.time() - START_TIME > MAX_RUN_TIME:
            break
            
        await asyncio.sleep(600) # ၁၀ မိနစ်တစ်ခါ စစ်မယ်

if __name__ == "__main__":
    asyncio.run(main())
