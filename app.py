Goalixy Smart Football Bot

كامل – يعمل – مع Failover + Cache + Goal Detection

APIs مجانية: OpenLigaDB + ScoreBat + Football-Data

import os import time import json import requests import logging from datetime import datetime, date from flask import Flask, request

================================

Logging

================================

logging.basicConfig(level=logging.INFO) logger = logging.getLogger("goalixy")

================================

Flask App

================================

app = Flask(name)

================================

ENV VARS

================================

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN") FB_PAGE_ID = os.getenv("FB_PAGE_ID") FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY")

================================

SIMPLE CACHE (in‑memory)

================================

MATCH_CACHE = {} CACHE_TTL = 120  # seconds

================================

API CONFIGS

================================

APIS = [ { "name": "OpenLigaDB", "url": "https://api.openligadb.de/getmatchdata/bl1", "type": "list", }, { "name": "ScoreBat", "url": "https://www.scorebat.com/video-api/v3/", "type": "scorebat", }, { "name": "Football-Data", "url": "https://api.football-data.org/v4/matches", "type": "football-data", }, ]

================================

FACEBOOK SEND

================================

def send_message(psid, text): if not FB_PAGE_TOKEN: return url = "https://graph.facebook.com/v18.0/me/messages" payload = { "recipient": {"id": psid}, "message": {"text": text} } params = {"access_token": FB_PAGE_TOKEN} requests.post(url, params=params, json=payload, timeout=10)

================================

UTILS

================================

def cache_valid(key): return key in MATCH_CACHE and time.time() - MATCH_CACHE[key]['ts'] < CACHE_TTL

def store_cache(key, value): MATCH_CACHE[key] = {"ts": time.time(), "data": value}

================================

PARSERS

================================

def parse_openliga(data): out = [] for m in data: home = m['team1']['teamName'] away = m['team2']['teamName'] goals_home = m['matchResults'][-1]['pointsTeam1'] if m['matchResults'] else 0 goals_away = m['matchResults'][-1]['pointsTeam2'] if m['matchResults'] else 0 match_id = m['matchID'] out.append({ "id": match_id, "home": home, "away": away, "score": f"{goals_home}-{goals_away}" }) return out

def parse_scorebat(data): out = [] for m in data.get('response', {}).get('list', []): title = m.get('title', '') if ' vs ' in title: home, away = title.split(' vs ') out.append({ "id": title, "home": home, "away": away, "score": "0-0" }) return out

def parse_football_data(data): out = [] for m in data.get('matches', []): mid = m['id'] home = m['homeTeam']['name'] away = m['awayTeam']['name'] s = m['score']['fullTime'] out.append({ "id": mid, "home": home, "away": away, "score": f"{s['home']}‑{s['away']}" }) return out

================================

CORE FETCH

================================

def fetch_matches(): today_key = str(date.today())

if cache_valid(today_key):
    return MATCH_CACHE[today_key]['data']

for api in APIS:
    try:
        headers = {}
        if api['name'] == 'Football-Data':
            headers = {"X-Auth-Token": FOOTBALL_DATA_KEY}
        r = requests.get(api['url'], headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()

        if api['type'] == 'list':
            matches = parse_openliga(data)
        elif api['type'] == 'scorebat':
            matches = parse_scorebat(data)
        else:
            matches = parse_football_data(data)

        if matches:
            store_cache(today_key, matches)
            return matches
    except Exception as e:
        logger.warning("API %s failed: %s", api['name'], e)
        continue

return []

================================

SMART GOAL DETECTOR

================================

def detect_goals(new_matches): messages = [] for m in new_matches: mid = m['id'] score = m['score'] old = MATCH_CACHE.get(mid) if old and old['score'] != score: messages.append(f"⚽ هدف! {m['home']} {score} {m['away']}") MATCH_CACHE[mid] = m return messages

================================

WEBHOOK

================================

@app.route('/webhook', methods=['GET', 'POST']) def webhook(): if request.method == 'GET': if request.args.get('hub.verify_token') == VERIFY_TOKEN: return request.args.get('hub.challenge'), 200 return 'Forbidden', 403

data = request.get_json()
for entry in data.get('entry', []):
    for msg in entry.get('messaging', []):
        psid = msg['sender']['id']
        if 'text' in msg.get('message', {}):
            text = msg['message']['text'].lower()
            if text == 'مباريات اليوم':
                matches = fetch_matches()
                if not matches:
                    send_message(psid, "لا توجد مباريات حالياً")
                else:
                    txt = "📅 مباريات اليوم:\n"
                    for m in matches:
                        txt += f"• {m['home']} vs {m['away']} ({m['score']})\n"
                    send_message(psid, txt)
            else:
                send_message(psid, "اكتب: مباريات اليوم")
return 'ok', 200

================================

RUN

================================

if name == 'main': app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
