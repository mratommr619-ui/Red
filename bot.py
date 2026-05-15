import time
import os
import re
import requests
import json
import gspread
import asyncio
import cv2
import easyocr
import feedparser
import yt_dlp
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials
from ntscraper import Nitter

# --- Global Config ---
START_TIME = time.time()
MAX_RUN_TIME = 19800 # 5.5 hours
MY_CHAT_ID = int(os.getenv("MY_CHAT_ID"))
READER = easyocr.Reader(['en'], gpu=False) 
PROCESSED_VIDEOS = set()

# ၈ လုံးရှိပေမဲ့ code မဟုတ်တဲ့ စာလုံးများ (အမှိုက်စာသားဖယ်ရန်)
BLACKLIST = ["GIVEAWAY", "GRAPHICS", "AIRDROPS", "BINANCE", "CHANNELS", "REGISTER", "DOWNLOAD", "DAILYNEW"]

# Google Sheets Connect
def get_sheet():
    try:
        creds_json = json.loads(os.getenv("GOOGLE_SHEETS_JSON"))
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_json, scopes=scope)
        gc = gspread.authorize(creds)
        return gc.open_by_url("https://docs.google.com/spreadsheets/d/1ZDHya5Gep3kvVyQqgdRlJIgquP7pYZv9ZSW7hV2YTyE/edit").sheet1
    except: return None

# Binance Code စစ်ထုတ်သည့် စနစ် (ဂဏန်းပါမှယူမည်)
def find_binance_code(text):
    if not text: return []
    found = re.findall(r'\b[A-Z0-9]{8}\b', text.upper())
    return [c for c in found if c not in BLACKLIST and any(char.isdigit() for char in c)]

# Video တစ်ခုလုံးကို Scan ဖတ်မည့် Logic
async def scan_video_content(video_url):
    print(f"📥 Scanning Video Content: {video_url}")
    video_file = "temp_video.mp4"
    codes_found = set()
    
    ydl_opts = {'format': 'worst', 'outtmpl': video_file, 'quiet': True, 'no_warnings': True}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        
        cap = cv2.VideoCapture(video_file)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        interval = int(fps * 5) # ၅ စက္ကန့်ခြားတစ်ခါ ဖတ်မည်
        
        for frame_no in range(0, total_frames, interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
            success, frame = cap.read()
            if not success: break
            
            results = READER.readtext(frame)
            for (_, text, _) in results:
                for c in find_binance_code(text):
                    codes_found.add(c)
        cap.release()
    except Exception as e:
        print(f"❌ Video Scan Error: {e}")
    finally:
        if os.path.exists(video_file): os.remove(video_file)
            
    return codes_found

def trigger_restart():
    repo = os.getenv('GITHUB_REPOSITORY')
    url = f"https://api.github.com/repos/{repo}/dispatches"
    headers = {"Authorization": f"token {os.getenv('GH_PAT')}", "Accept": "application/vnd.github.v3+json"}
    requests.post(url, headers=headers, json={"event_type": "restart_bot"})

async def main():
    user_client = TelegramClient(StringSession(os.getenv("TG_STRING_SESSION")), 
                                 int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))
    bot_client = TelegramClient('bot', int(os.getenv("TG_API_ID")), os.getenv("TG_API_HASH"))

    await user_client.start()
    await bot_client.start(bot_token=os.getenv("BOT_TOKEN"))
    print("🚀 All-in-One Bot (Video OCR + X + TG) is Online!")

    while True:
        if time.time() - START_TIME > MAX_RUN_TIME:
            trigger_restart(); break
        
        sheet = get_sheet()
        if not sheet: await asyncio.sleep(60); continue
            
        records = sheet.get_all_records()

        # --- ၁။ YouTube Scan (Video Content OCR) ---
        yt_links = [r['Link'] for r in records if r['Type'].upper() == 'YT']
        for rss_url in yt_links:
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries:
                    v_id = entry.yt_videoid if 'yt_videoid' in entry else entry.link
                    if v_id in PROCESSED_VIDEOS: continue
                    
                    # Video ထဲကို ဝင်ဖတ်မည်
                    found_codes = await scan_video_content(entry.link)
                    if found_codes:
                        for c in found_codes:
                            await bot_client.send_message(MY_CHAT_ID, f"🎁 **Found Inside Video:** `{c}`\n🔗 {entry.link}")
                    
                    PROCESSED_VIDEOS.add(v_id)
            except: pass

        # --- ၂။ X (Twitter) Scan ---
        x_links = [r['Link'] for r in records if r['Type'].upper() == 'X']
        if x_links:
            scraper = Nitter()
            for link in x_links:
                try:
                    user = link.strip().split('/')[-1]
                    tweets = scraper.get_tweets(user, mode='user', number=2)
                    for t in tweets['tweets']:
                        codes = find_binance_code(t['text'])
                        for c in set(codes):
                            await bot_client.send_message(MY_CHAT_ID, f"🐦 **X Code:** `{c}`\n👤 From: {user}")
                except: pass

        # --- ၃။ TG Monitoring ကတော့ Background မှာ အလုပ်လုပ်နေပါမည် ---

        await asyncio.sleep(600) # ၁၀ မိနစ်တစ်ခါ စစ်မည်

if __name__ == "__main__":
    asyncio.run(main())
