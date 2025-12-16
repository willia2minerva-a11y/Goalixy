import os
import requests
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import pytz

# ================================
# إعداد السجل (logging)
# ================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("goalixy")

# ================================
# تهيئة تطبيق Flask
# ================================
app = Flask(__name__)

# ================================
# متغيرات البيئة الأساسية
# ================================
VERIFY_TOKEN = os.environ.get('FACEBOOK_VERIFY_TOKEN', 'goalixy_123')
FB_PAGE_TOKEN = os.environ.get('FB_PAGE_TOKEN')
FB_PAGE_ID = os.environ.get('FB_PAGE_ID')
TIMEZONE = os.environ.get('TIMEZONE', 'Africa/Algiers')

# ================================
# إعدادات API (الخيارات المتاحة)
# ================================
API_CONFIGS = [
    # 1. ScoreBat API (الأفضل - مجاني بدون مفتاح)
    {
        'name': 'ScoreBat',
        'url': 'https://www.scorebat.com/video-api/v3/',
        'parser': 'parse_scorebat',
        'needs_key': False
    },
    # 2. Football-Data.org (يحتاج مفتاح مجاني)
    {
        'name': 'Football-Data',
        'url': 'https://api.football-data.org/v4/matches',
        'parser': 'parse_footballdata',
        'needs_key': True,
        'key_name': 'X-Auth-Token'
    },
    # 3. API-FOOTBALL (بديل من RapidAPI)
    {
        'name': 'API-FOOTBALL',
        'url': 'https://api-football-v1.p.rapidapi.com/v3/fixtures',
        'parser': 'parse_apifootball',
        'needs_key': True,
        'key_name': 'X-RapidAPI-Key'
    }
]

# ================================
# دوال المساعدة
# ================================
def get_timezone():
    """الحصول على الوقت الحالي حسب المنطقة"""
    try:
        tz = pytz.timezone(TIMEZONE)
        return datetime.now(tz)
    except:
        return datetime.utcnow()

def format_time(date_str, from_tz='UTC'):
    """تنسيق الوقت"""
    try:
        # تنسيقات مختلفة للوقت
        for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S']:
            try:
                dt = datetime.strptime(date_str, fmt)
                local_dt = dt
                if from_tz != 'UTC':
                    # تحويل المنطقة الزمنية
                    pass
                return local_dt.strftime('%H:%M')
            except:
                continue
        return date_str[:5] if len(date_str) >= 5 else date_str
    except:
        return '--:--'

# ================================
# دوال تحليل الـ APIs
# ================================
def parse_scorebat(data):
    """تحليل بيانات ScoreBat API"""
    matches = []
    try:
        if isinstance(data, dict) and 'response' in data:
            items = data['response']
        else:
            items = data if isinstance(data, list) else []
        
        for item in items[:15]:  # أول 15 مباراة فقط
            if isinstance(item, dict):
                # ScoreBat له تنسيقات متعددة
                title = item.get('title', '')
                competition = item.get('competition', {}).get('name', '')
                
                # محاولة استخراج الفرق
                home_team = away_team = ''
                if ' - ' in title:
                    parts = title.split(' - ')
                    if len(parts) >= 2:
                        home_team = parts[0].strip()
                        away_team = parts[1].split('(')[0].strip() if '(' in parts[1] else parts[1].strip()
                elif ' vs ' in title.lower():
                    parts = title.lower().split(' vs ')
                    if len(parts) >= 2:
                        home_team = parts[0].strip().title()
                        away_team = parts[1].strip().title()
                
                # إذا لم نتمكن من استخراج الفرق، نستخدم العنوان كاملاً
                if not home_team or not away_team:
                    home_team = title[:20] + '...' if len(title) > 20 else title
                    away_team = competition[:20] + '...' if competition else '--'
                
                # الوقت
                date_str = item.get('date', '')
                time_str = format_time(date_str)
                
                # إضافة المباراة
                match_info = f"⏰ {time_str} | {home_team} 🆚 {away_team}"
                if competition:
                    match_info += f" | {competition[:15]}..."
                
                matches.append(match_info)
    except Exception as e:
        logger.error(f"خطأ في تحليل ScoreBat: {e}")
    
    return matches

def parse_footballdata(data):
    """تحليل بيانات Football-Data.org"""
    matches = []
    try:
        if isinstance(data, dict) and 'matches' in data:
            for match in data['matches'][:15]:
                home = match.get('homeTeam', {}).get('name', 'Home')
                away = match.get('awayTeam', {}).get('name', 'Away')
                time_str = format_time(match.get('utcDate', ''))
                competition = match.get('competition', {}).get('name', '')
                
                match_info = f"⏰ {time_str} | {home} 🆚 {away}"
                if competition:
                    match_info += f" | {competition[:15]}..."
                
                matches.append(match_info)
    except Exception as e:
        logger.error(f"خطأ في تحليل Football-Data: {e}")
    
    return matches

def parse_apifootball(data):
    """تحليل بيانات API-FOOTBALL"""
    matches = []
    try:
        if isinstance(data, dict) and 'response' in data:
            for item in data['response'][:15]:
                fixture = item.get('fixture', {})
                teams = item.get('teams', {})
                league = item.get('league', {})
                
                home = teams.get('home', {}).get('name', 'Home')
                away = teams.get('away', {}).get('name', 'Away')
                time_str = format_time(fixture.get('date', ''))
                competition = league.get('name', '')
                
                match_info = f"⏰ {time_str} | {home} 🆚 {away}"
                if competition:
                    match_info += f" | {competition[:15]}..."
                
                matches.append(match_info)
    except Exception as e:
        logger.error(f"خطأ في تحليل API-FOOTBALL: {e}")
    
    return matches

# ================================
# دالة جلب المباريات الرئيسية
# ================================
def get_today_matches():
    """جلب مباريات اليوم"""
    logger.info("🎯 جلب مباريات اليوم...")
    
    # أولاً: نجرب ScoreBat (مجاني بدون مفتاح)
    try:
        logger.info("🔄 محاولة ScoreBat API...")
        response = requests.get(
            'https://www.scorebat.com/video-api/v3/',
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            matches = parse_scorebat(data)
            
            if matches:
                message = "⚽ *مباريات اليوم:* ⚽\n\n"
                message += "\n".join(matches[:10])  # أول 10 مباريات فقط
                message += "\n\n📱 *مصدر: ScoreBat API*"
                return message
    except Exception as e:
        logger.warning(f"❌ ScoreBat فشل: {e}")
    
    # ثانياً: نجرب Football-Data.org (إذا كان هناك مفتاح)
    football_data_key = os.environ.get('FOOTBALL_DATA_KEY')
    if football_data_key:
        try:
            logger.info("🔄 محاولة Football-Data.org...")
            today = datetime.now().strftime('%Y-%m-%d')
            response = requests.get(
                f'https://api.football-data.org/v4/matches',
                headers={'X-Auth-Token': football_data_key},
                params={'dateFrom': today, 'dateTo': today},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                matches = parse_footballdata(data)
                
                if matches:
                    message = "⚽ *مباريات اليوم:* ⚽\n\n"
                    message += "\n".join(matches[:10])
                    message += "\n\n📱 *مصدر: Football-Data.org*"
                    return message
        except Exception as e:
            logger.warning(f"❌ Football-Data فشل: {e}")
    
    # أخيراً: نجرب الـ RapidAPI الموجود عندك
    rapidapi_key = os.environ.get('RAPIDAPI_KEY1')
    if rapidapi_key:
        try:
            logger.info("🔄 محاولة API-FOOTBALL...")
            today = datetime.now().strftime('%Y-%m-%d')
            response = requests.get(
                'https://api-football-v1.p.rapidapi.com/v3/fixtures',
                headers={
                    'X-RapidAPI-Key': rapidapi_key,
                    'X-RapidAPI-Host': 'api-football-v1.p.rapidapi.com'
                },
                params={'date': today},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                matches = parse_apifootball(data)
                
                if matches:
                    message = "⚽ *مباريات اليوم:* ⚽\n\n"
                    message += "\n".join(matches[:10])
                    message += "\n\n📱 *مصدر: API-FOOTBALL*"
                    return message
        except Exception as e:
            logger.warning(f"❌ API-FOOTBALL فشل: {e}")
    
    # إذا فشل كل شيء
    return "⚠️ *عذراً، لا توجد مباريات متاحة حالياً.*\nيرجى المحاولة لاحقاً."

# ================================
# دوال فيسبوك
# ================================
def send_message(recipient_id, message_text):
    """إرسال رسالة عبر Messenger"""
    if not FB_PAGE_TOKEN:
        logger.error("❌ FB_PAGE_TOKEN غير موجود!")
        return False
    
    url = f"https://graph.facebook.com/v18.0/me/messages"
    params = {"access_token": FB_PAGE_TOKEN}
    headers = {"Content-Type": "application/json"}
    
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text},
        "messaging_type": "RESPONSE"
    }
    
    try:
        response = requests.post(url, params=params, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ تم إرسال رسالة إلى {recipient_id}")
            return True
        else:
            logger.error(f"❌ فشل إرسال الرسالة: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطأ في الإرسال: {e}")
        return False

# ================================
# معالجة الرسائل
# ================================
def handle_message(sender_id, message_text):
    """معالجة رسائل المستخدم"""
    lower_text = message_text.lower().strip()
    
    if 'مباريات اليوم' in lower_text or 'today' in lower_text:
        response = get_today_matches()
    elif 'مرحبا' in lower_text or 'hello' in lower_text or 'hi' in lower_text:
        response = "👋 *أهلاً بك في Goalixy!*\n\n" \
                   "⚽ أنا بوت أخبار كرة القدم\n" \
                   "📅 *الأوامر المتاحة:*\n" \
                   "• مباريات اليوم - عرض مباريات اليوم\n" \
                   "• مساعدة - عرض جميع الأوامر"
    elif 'مساعدة' in lower_text or 'help' in lower_text:
        response = "📋 *قائمة الأوامر:*\n\n" \
                   "⚽ *المباريات:*\n" \
                   "• مباريات اليوم - مباريات اليوم\n" \
                   "• مباريات مباشرة - المباريات الحية (قريباً)\n\n" \
                   "ℹ️ *معلومات:*\n" \
                   "• مساعدة - هذه القائمة\n" \
                   "• عن البوت - معلومات عن Goalixy"
    elif 'عن البوت' in lower_text:
        response = "🤖 *Goalixy Bot*\n\n" \
                   "⚽ بوت أخبار كرة القدم العربي\n" \
                   "📍 تحديثات مباشرة للمباريات\n" \
                   "🕒 يعمل 24/7\n" \
                   "🔔 تابعنا للمزيد!"
    else:
        response = "❓ لم أفهم طلبك!\n" \
                   "اكتب 'مساعدة' لرؤية الأوامر المتاحة."
    
    # إرسال الرد
    send_message(sender_id, response)

# ================================
# Webhook
# ================================
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """التحقق من Webhook"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logger.info("✅ تم التحقق من Webhook بنجاح!")
            return challenge
        else:
            logger.error("❌ توكن التحقق غير صحيح!")
            return 'Verification token mismatch', 403
    
    return 'Bad request', 400

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """معالجة أحداث Webhook"""
    try:
        data = request.get_json()
        logger.info(f"📩 بيانات واردة: {json.dumps(data)[:200]}...")
        
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    sender_id = messaging_event.get('sender', {}).get('id')
                    
                    if not sender_id:
                        continue
                    
                    # معالجة الرسائل النصية
                    if messaging_event.get('message'):
                        message_text = messaging_event['message'].get('text', '')
                        if message_text:
                            handle_message(sender_id, message_text)
                    
                    # معالجة Postbacks
                    elif messaging_event.get('postback'):
                        payload = messaging_event['postback'].get('payload', '')
                        logger.info(f"🔄 Postback من {sender_id}: {payload}")
        
        return 'EVENT_RECEIVED', 200
    
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة Webhook: {e}")
        return 'ERROR', 500

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Goalixy Bot ⚽</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #1e88e5; }
            .status { color: #4CAF50; font-weight: bold; }
            .command { background: #f0f0f0; padding: 10px; margin: 10px 0; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>⚽ Goalixy Bot</h1>
            <p class="status">✅ البوت يعمل بنجاح!</p>
            <p>بوت أخبار كرة القدم العربي</p>
            
            <div class="command">
                <strong>الأوامر المتاحة:</strong><br>
                • مباريات اليوم<br>
                • مساعدة
            </div>
            
            <p><a href="/webhook" target="_blank">رابط Webhook</a></p>
            <p>© 2024 Goalixy - جميع الحقوق محفوظة</p>
        </div>
    </body>
    </html>
    '''

@app.route('/health')
def health():
    """فحص صحة الخدمة"""
    return jsonify({
        'status': 'healthy',
        'service': 'Goalixy Bot',
        'time': datetime.now().isoformat(),
        'timezone': TIMEZONE
    })

# ================================
# نقطة التشغيل
# ================================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"🚀 بدء تشغيل Goalixy Bot على المنفذ {port}")
    logger.info(f"📍 المنطقة الزمنية: {TIMEZONE}")
    logger.info(f"📱 صفحة الفيسبوك: {FB_PAGE_ID}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)
