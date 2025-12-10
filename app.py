import os
import requests
import json
from datetime import date
from flask import Flask, request

# تهيئة تطبيق Flask
app = Flask(__name__)

# --- متغيرات البيئة الأساسية ---
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN') 
FB_PAGE_TOKEN = os.environ.get('FB_PAGE_TOKEN') 
FB_PAGE_ID = os.environ.get('FB_PAGE_ID')

# --- إعدادات API لمنطق Failover وتنسيق التاريخ ---
API_CONFIGS = [
    {
        'HOST': os.environ.get('RAPIDAPI_HOST1'),
        'KEY': os.environ.get('RAPIDAPI_KEY1'),
        'PATH': '/football-get-matches-by-date', # API 1: المسار الذي يحتاج YYYYMMDD
        'NAME': 'API 1 (Free-Live)',
        'DATE_FORMAT': '%Y%m%d', # تنسيق التاريخ المطلوب: 20241107
        'NEEDS_DATE': True
    },
    {
        'HOST': os.environ.get('RAPIDAPI_HOST2'), 
        'KEY': os.environ.get('RAPIDAPI_KEY2'),
        'PATH': '/latestsoccer.php', # API 2: لا يحتاج بارامتر date
        'NAME': 'API 2 (TheSportsDB)',
        'DATE_FORMAT': '', 
        'NEEDS_DATE': False # لا نرسل بارامتر التاريخ لهذا API
    },
    {
        'HOST': os.environ.get('RAPIDAPI_HOST3'), 
        'KEY': os.environ.get('RAPIDAPI_KEY3'),
        'PATH': '/get-matches/events-by-date', # API 3: المسار الذي يحتاج YYYY-MM-DD
        'NAME': 'API 3 (LiveScore)',
        'DATE_FORMAT': '%Y-%m-%d', # تنسيق التاريخ الشائع: 2024-11-07
        'NEEDS_DATE': True
    }
]

# --- متغيرات الصور الموحدة (يجب استبدالها بروابط عامة خاصة بك) ---
IMAGE_URLS = {
    'GOAL': "https://your-domain.com/images/goal_icon.jpg",  
    'START': "https://your-domain.com/images/start_match.jpg", 
    'RED_CARD': "https://your-domain.com/images/red_card.jpg" 
}


# =================================================================
#                         وظائف النشر (POSTING)
# =================================================================

def post_to_facebook(message, image_url, language='ar'):
    """ تنشر رسالة وصورة مع تصفية الجمهور. """
    if not FB_PAGE_TOKEN or not FB_PAGE_ID:
        print("Error: FB_PAGE_TOKEN or FB_PAGE_ID is missing.")
        return

    # تحديد إعدادات التصفية (Targeting)
    if language == 'ar':
        targeting = {
            "geo_locations": {"countries": ["DZ", "EG", "SA", "AE", "MA", "TN", "QA", "KW"]},
            "locales": [6] 
        }
    else: 
        targeting = {
            "geo_locations": {"countries": ["US", "GB", "FR", "DE", "CA", "ES"]},
            "locales": [1] 
        }
    
    targeting_json = json.dumps(targeting)
    url = f"https://graph.facebook.com/v18.0/{FB_PAGE_ID}/photos"

    payload = {
        'message': message,
        'url': image_url,
        'access_token': FB_PAGE_TOKEN,
        'targeting': targeting_json, 
        'published': 'true'
    }

    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print(f"Post successful for language {language}: {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Error publishing post: {e}")
        if response is not None:
             print(f"Response details: {response.text}")

def publish_start_event(match_details):
    """ تنشئ منشور بداية المباراة """
    
    # 1. المنشور العربي
    arabic_message = (
        f"🚨 بداية المباراة!\n"
        f"{match_details['home_team']} 🆚 {match_details['away_team']}\n"
        f"🏆 البطولة: {match_details['league_name']}\n"
        f"🎙️ المعلق: [اسم المعلق]\n"
        f"📺 القناة: [اسم القناة]"
    )
    post_to_facebook(arabic_message, IMAGE_URLS['START'], language='ar')
    
    # 2. المنشور الإنجليزي
    english_message = (
        f"🚨 Match KICK-OFF!\n"
        f"{match_details['home_team']} 🆚 {match_details['away_team']}\n"
        f"🏆 Competition: {match_details['league_name']}\n"
        f"🎙️ Commentator: [Commentator Name]\n"
        f"📺 Channel: [Channel Name]"
    )
    post_to_facebook(english_message, IMAGE_URLS['START'], language='en')

def publish_goal_event(match_details, scorer, current_result):
    """ تنشئ منشور هدف جديد """
    
    # 1. المنشور العربي
    arabic_message = (
        f"⚽️ هـدف! سجل اللاعب {scorer} هدفاً.\n"
        f"النتيجة الحالية: {current_result}\n"
        f"المباراة: {match_details['home_team']} ضد {match_details['away_team']}"
    )
    post_to_facebook(arabic_message, IMAGE_URLS['GOAL'], language='ar')

    # 2. المنشور الإنجليزي
    english_message = (
        f"⚽️ GOAL! {scorer} scores a stunning goal.\n"
        f"Current Score: {current_result}\n"
        f"Match: {match_details['home_team']} vs {match_details['away_team']}"
    )
    post_to_facebook(english_message, IMAGE_URLS['GOAL'], language='en')

# =================================================================
#                       وظائف API الرياضي والردود (FAILOVER)
# =================================================================

def get_today_matches():
    """
    جلب مباريات اليوم باستخدام منطق Failover (تجربة أكثر من API).
    """
    from datetime import date
    
    # تجربة كل إعدادات API بالترتيب
    for config in API_CONFIGS:
        host = config.get('HOST')
        key = config.get('KEY')
        path = config.get('PATH')
        api_name = config.get('NAME')
        date_format = config.get('DATE_FORMAT')
        needs_date = config.get('NEEDS_DATE')
        
        # تخطي إذا كانت المتغيرات غير مُعرفة في Render
        if not host or not key:
            continue
            
        url = f"https://{host}{path}"
        querystring = {}
        
        # إعداد بارامتر التاريخ إذا كان الـ API يتطلبه
        if needs_date:
            today_date = date.today().strftime(date_format)
            querystring = {"date": today_date}

        headers = {
            "X-RapidAPI-Key": key,
            "X-RapidAPI-Host": host
        }

        try:
            print(f"Attempting connection with API: {api_name} at {url}")
            response = requests.get(url, headers=headers, params=querystring, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # --- تحليل البيانات والرد عند النجاح ---
            if data and data.get('response'):
                
                match_list = [f"*مباريات اليوم (المصدر: {api_name}):*\n"]
                matches = data['response']
                
                if not matches:
                    return f"لا توجد مباريات مقررة لهذا اليوم (المصدر: {api_name})."
                    
                # NOTE: يجب أن يتم تعديل منطق تحليل JSON هنا ليناسب هيكل كل API
                for match in matches:
                    try:
                        # هذا نموذج تحليل مبسط؛ قد تحتاج إلى تعديله
                        home_team = match.get('teams', {}).get('home', {}).get('name', 'N/A')
                        away_team = match.get('teams', {}).get('away', {}).get('name', 'N/A')
                        match_list.append(f"{home_team} vs {away_team}")
                    except:
                        # في حال فشل تحليل هيكل البيانات لهذا الـ API
                        match_list.append(f"تم جلب البيانات من {api_name}، لكن تحليل الهيكل فشل.")
                        break 
                        
                return "\n".join(match_list)
            
        except requests.exceptions.RequestException as e:
            # فشل الاتصال بهذا API (403, 404, Timeout)، نطبع الخطأ وننتقل للتجربة التالية
            print(f"API Failed: {api_name}. Error: {e}")
            continue 
            
    # إذا فشلت جميع محاولات الاتصال
    return "آسف، فشلت جميع محاولات الاتصال بمصادر النتائج الرياضية."


def send_message(recipient_id, message_text):
    """ إرسال رسالة نصية بسيطة إلى مستخدم معين. """
    if not FB_PAGE_TOKEN:
        print("Error: FB_PAGE_TOKEN is not configured.")
        return

    params = {"access_token": FB_PAGE_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    
    url = "https://graph.facebook.com/v18.0/me/messages" 
    
    try:
        response = requests.post(url, params=params, headers=headers, json=data)
        response.raise_for_status()
        print(f"Message sent successfully to {recipient_id}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to {recipient_id}: {e}")


def handle_message(sender_id, message_text):
    """ تعالج الرسائل الواردة وتحدد الرد المناسب بناءً على الأمر. """
    lower_text = message_text.lower().strip()
    response_text = "آسف، لم أجد طلبك. الأوامر المتاحة هي: 'مباريات اليوم'."
    
    if lower_text == 'مباريات اليوم':
        response_text = get_today_matches() 
    
    elif lower_text in ['مرحبا', 'سلام', 'hi', 'hello']:
        response_text = "أهلاً بك في Goalixy! لمعرفة آخر النتائج، اكتب 'مباريات اليوم'."
        
    elif lower_text == 'اختبار هدف':
        # أمر للاختبار اليدوي لعمل دالة النشر والتصفية
        test_details = {
            'home_team': 'الجزائر', 
            'away_team': 'السنغال', 
            'league_name': 'كأس الأمم'
        }
        publish_goal_event(test_details, "رياض محرز", "1-0")
        response_text = "تم نشر هدف تجريبي بنجاح على الصفحة (تحقق من تصفية الجمهور)!"
        
    send_message(sender_id, response_text)


# =================================================================
#                      مسار الـ Webhook الرئيسي
# =================================================================

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. التحقق من الـ Webhook (GET Request)
    if request.method == 'GET':
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                print('WEBHOOK_VERIFIED')
                return challenge, 200
            else:
                return 'Verification token mismatch', 403
        
        return 'Missing required parameters', 400

    # 2. استقبال الأحداث ومعالجتها (POST Request)
    elif request.method == 'POST':
        data = request.json

        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    
                    sender_id = messaging_event['sender']['id']
                    
                    # معالجة الرسائل النصية الواردة
                    if messaging_event.get('message'):
                        if 'text' in messaging_event['message']:
                            message_text = messaging_event['message']['text']
                            handle_message(sender_id, message_text)
                            
                    # معالجة الـ Postbacks 
                    elif messaging_event.get('postback'):
                        payload = messaging_event['postback']['payload']
                        print(f"Received Postback Payload: {payload}")

        return 'EVENT_RECEIVED', 200
        
    return 'Invalid method', 405


# أمر تشغيل التطبيق (Render يستخدم Gunicorn)
if __name__ == '__main__':
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
