import time
import os
import re
import json
import gspread
import requests
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials

# --- Config ---
START_TIME = time.time()
MAX_RUN_TIME = 19800 
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))
SENT_CODES = set()
BLACKLIST = ["GIVEAWAY", "GRAPHICS", "AIRDROPS", "BINANCE", "CHANNELS", "REGISTER", "DOWNLOAD", "DAILYNEW", "TWITTER", "TIMELINE", "FOLLOW"]

def find_binance_code(text):
    if not text: return []
    found = re.findall(r'\b[A-Z0-9]{8,10}\b', text.upper())
    return [c for c in found if c not in BLACKLIST]

def get_spreadsheet_client():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        return gspread.authorize(creds)
    except: return None

def trigger_restart():
    try:
        repo = os.getenv('GITHUB_REPOSITORY')
        url = f"https://api.github.com/repos/{repo}/dispatches"
        headers = {
            "Authorization": f"token {os.getenv('GH_PAT')}",
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.post(url, headers=headers, json={"event_type": "restart_bot"})
        if response.status_code == 204:
            print("🔄 Auto-Wakeup Signal Sent!")
        else:
            print(f"⚠️ Wakeup Signal Failed: {response.status_code}")
    except Exception as e:
        print(f"⚠️ Trigger Error: {e}")

def fetch_tweets_via_syndication(username):
    url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200: return res.text
    except: pass
    return ""

async def main():
    global SENT_CODES
    gc = get_spreadsheet_client()
    if not gc:
        print("❌ Google Sheet Connection Failed!")
        return
        
    doc = gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit")
    sheet1 = doc.sheet1
    
    try:
        sent_sheet = doc.worksheet("Sent")
        old_codes = sent_sheet.col_values(1)
        SENT_CODES.update(old_codes)
        print(f"💾 Loaded {len(old_codes)} codes from memory.")
    except gspread.exceptions.WorksheetNotFound:
        sent_sheet = doc.add_worksheet(title="Sent", rows="1000", cols="2")
        print("📁 Created new 'Sent' worksheet.")
    except Exception as e:
        print(f"⚠️ Memory Load Error: {e}")

    user_client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                                 int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    bot_client = TelegramClient('bot', int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))

    print("🔌 Connecting to Telegram...")
    await user_client.connect()
    await bot_client.start(bot_token=os.getenv("BOT_TOKEN"))
    print("🚀 Bot is Online (English Text Edition)!")

    all_values = sheet1.get_all_values()
    tg_list = [row[1].strip().replace('@', '').replace('https://t.me/', '').split('/')[-1] 
               for row in all_values if len(row) >= 2 and row[0].upper() == 'TG']

    # --- Telegram Monitor ---
    @user_client.on(events.NewMessage())
    async def handler(event):
        try:
            chat = await event.get_chat()
            username = getattr(chat, 'username', None)
            if username in tg_list:
                codes = find_binance_code(event.raw_text)
                for c in set(codes):
                    if c not in SENT_CODES:
                        # English စာသားအလှအပ ပုံစံ ပြောင်းလဲထားခြင်း
                        fancy_message = (
                            "✨ **New Binance Red Packet Code Detected!** ✨\n\n"
                            "Tap the code below to copy instantly:\n"
                            f"👉 `{c}` 👈\n\n"
                            "🎁 Good Luck! 🎁"
                        )
                        await bot_client.send_message(MY_CHAT_ID, fancy_message)
                        SENT_CODES.add(c)
                        sent_sheet.append_row([c])
                        print(f"✨ Sent & Saved (TG): {c}")
        except: pass

    # --- X Loop Monitoring ---
    while True:
        if time.time() - START_TIME > MAX_RUN_TIME:
            print("⏰ Time limit reached. Re-booting...")
            trigger_restart()
            break
        
        try:
            all_values = sheet1.get_all_values()
            x_links = [row[1] for row in all_values if len(row) >= 2 and row[0].upper() == 'X']
            tg_list = [row[1].strip().replace('@', '').replace('https://t.me/', '').split('/')[-1] 
                       for row in all_values if len(row) >= 2 and row[0].upper() == 'TG']
        except:
            await asyncio.sleep(60); continue

        if x_links:
            print(f"🐦 Checking {len(x_links)} X Accounts...")
            for link in x_links:
                username = link.strip().split('/')[-1].split('?')[0]
                raw_data = fetch_tweets_via_syndication(username)
                if raw_data:
                    codes = find_binance_code(raw_data)
                    for c in set(codes):
                        if c not in SENT_CODES:
                            # English စာသားအလှအပ ပုံစံ ပြောင်းလဲထားခြင်း
                            fancy_message = (
                                "✨ **New Binance Red Packet Code Detected!** ✨\n\n"
                                "Tap the code below to copy instantly:\n"
                                f"👉 `{c}` 👈\n\n"
                                "🎁 Good Luck! 🎁"
                            )
                            await bot_client.send_message(MY_CHAT_ID, fancy_message)
                            SENT_CODES.add(c)
                            sent_sheet.append_row([c])
                            print(f"🎯 Sent & Saved (X): {c}")
                await asyncio.sleep(3)

        print("😴 Waiting 5 mins...")
        await asyncio.sleep(300)

if __name__ == "__main__":
    asyncio.run(main())
