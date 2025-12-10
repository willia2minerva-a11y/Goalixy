import os
import requests
import json
import logging
from datetime import date
from flask import Flask, request, jsonify

# ================================
# إعداد السجل (logging)
# ================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("goalixy")

# ================================
# تهيئة تطبيق Flask
# ================================
app = Flask(__name__)

# ================================
# متغيرات البيئة الأساسية
# ================================
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN')
FB_PAGE_TOKEN = os.environ.get('FB_PAGE_TOKEN')
FB_PAGE_ID = os.environ.get('FB_PAGE_ID')

# مفتاح Football-Data.org (يمكن أن يكون None)
FOOTBALL_DATA_KEY = os.environ.get('FOOTBALL_DATA_KEY')

# ================================
# إعدادات API لمنطق Failover
# ================================
API_CONFIGS = [
    # 1. OpenLigaDB (الأولوية القصوى - مجاني، بدون مفتاح)
    {
        'HOST': 'api.openligadb.de',
        'KEY': None,
        'PATH': '/getmatchdata/',   # نكمل لاحقاً بمعرف الدوري أو /now حسب الاستخدام
        'NAME': 'OpenLigaDB',
        'DATE_FORMAT': '',  # لا يحتاج بارامتر تاريخ عند بعض endpoints
        'NEEDS_DATE': False
    },
    # 2. ScoreBat API (مجاني، بدون مفتاح)
    {
        'HOST': 'www.scorebat.com',
        'KEY': None,
        'PATH': '/video-api/v3/',
        'NAME': 'ScoreBat',
        'DATE_FORMAT': '',
        'NEEDS_DATE': False
    },
    # 3. Football-Data.org (مفتاح خارجي، سهل الحصول عليه)
    {
        'HOST': 'api.football-data.org',
        'KEY': FOOTBALL_DATA_KEY,
        'PATH': '/v4/matches',
        'NAME': 'Football-Data',
        'DATE_FORMAT': '%Y-%m-%d',
        'NEEDS_DATE': True
    }
]

# ================================
# متغيرات الصور الموحدة (استبدل بروابطك)
# ================================
IMAGE_URLS = {
    'GOAL': "https://your-domain.com/images/goal_icon.jpg",
    'START': "https://your-domain.com/images/start_match.jpg",
    'RED_CARD': "https://your-domain.com/images/red_card.jpg"
}

# ================================
# دوال المساعدة
# ================================

def safe_get(d, *keys, default="N/A"):
    """
    محاولة الحصول على قيمة من قاموس متداخل عبر عدة مفاتيح محتملة.
    safe_get(d, "Team1", "team1", default="N/A")
    """
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default

# دالة وهمية لنشر حدث هدف — حافظت على النداء كما في كودك
def publish_goal_event(details, scorer_name, score):
    """
    دالة مبدئية لنشر حدث هدف. يمكنك تعديلها لتتناسب مع منطقك (نشر على صفحة فيسبوك ...).
    """
    logger.info("publish_goal_event called with: %s | scorer: %s | score: %s", details, scorer_name, score)
    # هنا يمكنك تكوين مناداة لنشر المنشور على الصفحة باستخدام FB_PAGE_TOKEN
    # لا ننفّذ أي طلب خارجي افتراضياً حتى تضيف التهيئة المطلوبة.

# ================================
# دوال API الرياضي والردود (FAILOVER)
# ================================
def parse_openligadb_matches(data):
    """
    تحليل استجابة OpenLigaDB — نحاول دعم عدة أشكال (Team1/Team2 أو team1/team2).
    """
    matches_out = []
    # OpenLigaDB غالباً يعيد لائحة من المباريات
    if not isinstance(data, list):
        return matches_out

    for m in data:
        # دعم حقول متنوعة (Team1 vs team1)
        team1 = safe_get(m, 'Team1', 'team1', default={})
        team2 = safe_get(m, 'Team2', 'team2', default={})
        # team object قد يكون dict أو string — نتعامل مع الاثنين
        def extract_name(t):
            if isinstance(t, dict):
                return safe_get(t, 'TeamName', 'teamName', 'name', default='N/A')
            elif isinstance(t, str):
                return t
            else:
                return 'N/A'
        home = extract_name(team1)
        away = extract_name(team2)
        matches_out.append(f"• {home} vs {away}")
    return matches_out

def parse_scorebat_matches(data):
    """
    تحليل استجابة ScoreBat v3
    الشكل المتوقع:
    {
      "response": {
        "list": [ { "title": "TeamA vs TeamB", ... }, ... ]
      }
    }
    أو في بعض النسخ قد تحتوي العناصر على side1/side2.
    """
    matches_out = []
    if isinstance(data, dict):
        resp = data.get('response', {})
        lst = resp.get('list', []) if isinstance(resp, dict) else []
        # بعض الأحيان API القديم قد يرجع مباشرة قائمة
        if not lst and isinstance(data.get('list'), list):
            lst = data.get('list')
        # إن كانت القائمة نفسها هي data (نادر مع v3) فتعامل معها
        if not lst and isinstance(data, list):
            lst = data

        for item in lst:
            if not isinstance(item, dict):
                continue
            title = item.get('title')
            if title:
                matches_out.append(f"• {title}")
                continue
            # بديل: استخدام side1/side2
            side1 = safe_get(item, 'side1', default={})
            side2 = safe_get(item, 'side2', default={})
            def name_from_side(s):
                if isinstance(s, dict):
                    return safe_get(s, 'name', default='N/A')
                return 'N/A'
            if side1 or side2:
                matches_out.append(f"• {name_from_side(side1)} vs {name_from_side(side2)}")
                continue
            # أخيراً، حقل competition + title-like fields
            comp = item.get('competition')
            matches_out.append(f"• {item.get('title','N/A')} ({comp})")
    elif isinstance(data, list):
        # دعم الحالة إن أعاد القائمة مباشرة
        for it in data:
            title = it.get('title', 'N/A') if isinstance(it, dict) else str(it)
            matches_out.append(f"• {title}")
    return matches_out

def parse_football_data_matches(data):
    matches_out = []
    if not isinstance(data, dict):
        return matches_out
    matches = data.get('matches', [])
    if not isinstance(matches, list):
        return matches_out
    for m in matches:
        home = safe_get(m.get('homeTeam', {}), 'name', default='N/A')
        away = safe_get(m.get('awayTeam', {}), 'name', default='N/A')
        matches_out.append(f"• {home} vs {away}")
    return matches_out

def get_today_matches():
    """
    جلب مباريات اليوم باستخدام منطق Failover عبر API_CONFIGS.
    يعيد نصاً مناسباً للرد على المستخدم.
    """
    today = date.today()
    for config in API_CONFIGS:
        host = config.get('HOST')
        key = config.get('KEY')
        path = config.get('PATH')
        api_name = config.get('NAME')
        date_format = config.get('DATE_FORMAT')
        needs_date = config.get('NEEDS_DATE')

        # إذا كان API يتطلب مفتاح ولم يُعدَّ، نتجاوزه
        if api_name == 'Football-Data' and not key:
            logger.info("Skipping %s because KEY is not configured.", api_name)
            continue

        # بناء الـ URL
        # ملاحظة: بعض المسارات مثل OpenLigaDB يحتاج إضافة league id أو /now
        url = f"https://{host}{path}"

        params = {}
        headers = {}
        # إعداد رؤوس Football-Data
        if api_name == 'Football-Data':
            headers = {"X-Auth-Token": key}

        # إعداد بارامترات التاريخ إن لزم
        if needs_date:
            formatted = today.strftime(date_format)
            if api_name == 'Football-Data':
                params = {"dateFrom": formatted, "dateTo": formatted}
            else:
                params = {"date": formatted}

        # بعض APIs مثل OpenLigaDB: لجلب مباريات الآن يمكن استخدام /getmatchdata/bl1/now أو /getmatchdata/now
        if api_name == 'OpenLigaDB':
            # نستخدم endpoint عام للـ today: بعض السيرفرات تسمح ب /getmatchdata/bl1 أو /getmatchdata/now
            # سنحاول أولاً endpoint 'now' العام ثم الرجوع إلى base path
            try_paths = [f"{url}now", url]
        else:
            try_paths = [url]

        success = False
        for try_url in try_paths:
            try:
                logger.info("Attempting connection with API: %s at %s (params=%s)", api_name, try_url, params)
                response = requests.get(try_url, headers=headers, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
                # تحليل البيانات اعتماداً على المصدر
                matches = []
                if api_name == 'OpenLigaDB':
                    # حاول التحليل بعدة طرق
                    if isinstance(data, list):
                        matches = parse_openligadb_matches(data)
                    elif isinstance(data, dict) and data.get('matches'):
                        matches = parse_openligadb_matches(data.get('matches'))
                    else:
                        # بعض الأحيان يجب أن نطلب بالمسار /getmatchdata/{league}/{date}
                        matches = parse_openligadb_matches(data if isinstance(data, list) else [])
                elif api_name == 'ScoreBat':
                    matches = parse_scorebat_matches(data)
                elif api_name == 'Football-Data':
                    matches = parse_football_data_matches(data)
                else:
                    # Generic attempt
                    if isinstance(data, list):
                        matches = [str(x) for x in data]
                    elif isinstance(data, dict):
                        # حاول اقتطاع أي قائمة داخل dict
                        for k in ('matches', 'data', 'response', 'list', 'events'):
                            if isinstance(data.get(k), list):
                                matches = [str(item) for item in data.get(k)]
                                break

                if matches:
                    header = f"*مباريات اليوم (المصدر: {api_name}):*\n"
                    return header + "\n".join(matches)
                else:
                    # تم الاتصال ولكن لم يُستدل على مباريات - قد يكون السبب اختلاف endpoint
                    logger.info("Connected to %s but no matches parsed. Response keys: %s", api_name, list(data.keys()) if isinstance(data, dict) else type(data))
                    # إذا كانت هذه OpenLigaDB وحاولنا /now ولم يكن فيه شيء، فنجرب الصيغة العامة
                    success = True  # يعني أن الاتصال نجح لكن لا توجد مباريات
                    # دعنا نكمل إلى المصادر التالية بدل إعادة رسالة فورية
                    break

            except requests.exceptions.RequestException as e:
                logger.warning("API Failed: %s. Error: %s", api_name, e)
                # نجرب المسار التالي أو الـ API التالي
                continue

        # إذا كان الاتصال نجح لكن لم يعيد مباريات، نكمل لمصدر آخر
        continue

    # إذا فشلت جميع المحاولات أو لا توجد مباريات
    return "آسف، لم أتمكن من جلب مباريات اليوم من المصادر المتاحة الآن."

# ================================
# دوال فيسبوك: إرسال الرسائل
# ================================
def send_message(recipient_id, message_text):
    """ إرسال رسالة نصية بسيطة إلى مستخدم عبر Facebook Messenger """
    if not FB_PAGE_TOKEN:
        logger.error("Error: FB_PAGE_TOKEN is not configured.")
        return

    params = {"access_token": FB_PAGE_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }

    url = "https://graph.facebook.com/v18.0/me/messages"

    try:
        response = requests.post(url, params=params, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        logger.info("Message sent successfully to %s", recipient_id)
    except requests.exceptions.RequestException as e:
        logger.error("Error sending message to %s: %s", recipient_id, e)

# ================================
# معالجة الرسائل الواردة
# ================================
def handle_message(sender_id, message_text):
    """ تعالج الرسائل الواردة وتحدد الرد المناسب بناءً على الأمر. """
    lower_text = (message_text or "").lower().strip()
    response_text = "آسف، لم أجد طلبك. الأوامر المتاحة هي: 'مباريات اليوم'."

    if lower_text == 'مباريات اليوم':
        response_text = get_today_matches()
    elif lower_text in ['مرحبا', 'سلام', 'hi', 'hello']:
        response_text = "أهلاً بك في Goalixy! لمعرفة آخر النتائج، اكتب 'مباريات اليوم'."
    elif lower_text == 'اختبار هدف':
        # أمر لاختبار النشر والتصفية
        test_details = {
            'home_team': 'الجزائر',
            'away_team': 'السنغال',
            'league_name': 'كأس الأمم'
        }
        publish_goal_event(test_details, "رياض محرز", "1-0")
        response_text = "تم نشر هدف تجريبي بنجاح على الصفحة (تحقق من تصفية الجمهور)!"

    send_message(sender_id, response_text)

# ================================
# Webhook الرئيسي
# ================================
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. التحقق من الـ Webhook (GET Request)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')

        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                logger.info('WEBHOOK_VERIFIED')
                return challenge, 200
            else:
                return 'Verification token mismatch', 403

        return 'Missing required parameters', 400

    # 2. استقبال الأحداث ومعالجتها (POST Request)
    elif request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        logger.debug("Webhook POST received: %s", data)

        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    sender_id = messaging_event.get('sender', {}).get('id')
                    if not sender_id:
                        continue

                    # معالجة الرسائل النصية الواردة
                    if messaging_event.get('message'):
                        msg = messaging_event['message']
                        if 'text' in msg:
                            message_text = msg['text']
                            handle_message(sender_id, message_text)

                    # معالجة الـ Postbacks
                    elif messaging_event.get('postback'):
                        payload = messaging_event['postback'].get('payload')
                        logger.info("Received Postback Payload from %s: %s", sender_id, payload)

        return 'EVENT_RECEIVED', 200

    return 'Invalid method', 405

# ================================
# نقطة التشغيل
# ================================
if __name__ == '__main__':
    # Gunicorn on Render سيستخدم WSGI، لكن عند التشغيل محلياً: app.run مفيد للـ debug
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() in ('1', 'true', 'yes')
    logger.info("Starting app on port %s (debug=%s)", port, debug)
    app.run(debug=debug, host='0.0.0.0', port=port)
