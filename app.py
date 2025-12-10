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

# مفتاح Football-Data.org (يجب وضعه كمتغير بيئة في Render)
FOOTBALL_DATA_KEY = os.environ.get('FOOTBALL_DATA_KEY') 
# ملاحظة: قم بتغيير اسم RAPIDAPI_KEY3 إلى FOOTBALL_DATA_KEY في Render

# --- إعدادات API لمنطق Failover (الخطة الجديدة) ---
API_CONFIGS = [
    # 1. OpenLigaDB (الأولوية القصوى - مجاني، بدون مفتاح)
    {
        'HOST': 'api.openligadb.de', 
        'KEY': None, 
        'PATH': '/getmatchdata/', 
        'NAME': 'OpenLigaDB',
        'DATE_FORMAT': '', # لا يحتاج بارامتر تاريخ
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

# --- متغيرات الصور الموحدة (يجب استبدالها بروابط عامة خاصة بك) ---
IMAGE_URLS = {
    'GOAL': "https://your-domain.com/images/goal_icon.jpg",  
    'START': "https://your-domain.com/images/start_match.jpg", 
    'RED_CARD': "https://your-domain.com/images/red_card.jpg" 
}


# =================================================================
#                       وظائف API الرياضي والردود (FAILOVER)
# =================================================================

def get_today_matches():
    """ جلب مباريات اليوم باستخدام منطق Failover (تجربة 3 APIs جديدة). """
    from datetime import date
    
    for config in API_CONFIGS:
        host = config.get('HOST')
        key = config.get('KEY')
        path = config.get('PATH')
        api_name = config.get('NAME')
        date_format = config.get('DATE_FORMAT')
        needs_date = config.get('NEEDS_DATE')
        
        # تخطي إذا كان API يتطلب مفتاحاً ولم يتم إعداده
        if api_name == 'Football-Data' and not key:
            continue
            
        url = f"https://{host}{path}"
        querystring = {}
        headers = {}
        
        # إعداد الرؤوس والمفاتيح (لـ Football-Data فقط)
        if api_name == 'Football-Data': 
            headers = {"X-Auth-Token": key}
            
        # إعداد بارامتر التاريخ
        if needs_date:
            today_date_formatted = date.today().strftime(date_format)
            
            if api_name == 'Football-Data':
                # هذا API يستخدم dateFrom/dateTo
                querystring = {"dateFrom": today_date_formatted, "dateTo": today_date_formatted}
            else:
                querystring = {"date": today_date_formatted}


        try:
            print(f"Attempting connection with API: {api_name} at {url}")
            response = requests.get(url, headers=headers, params=querystring, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # --- تحليل البيانات والرد عند النجاح ---
            
            match_list = [f"*مباريات اليوم (المصدر: {api_name}):*\n"]
            
            # 1. تحليل هيكل OpenLigaDB (مصفوفة JSON مباشرة)
            if api_name == 'OpenLigaDB' and isinstance(data, list):
                if not data:
                    return f"لا توجد مباريات مقررة لهذا اليوم (المصدر: {api_name})."
                    
                for match in data:
                    home_team = match.get('team1', {}).get('teamName', 'N/A')
                    away_team = match.get('team2', {}).get('teamName', 'N/A')
                    match_list.append(f"• {home_team} vs {away_team}")
                return "\n".join(match_list)
            
            # 2. تحليل هيكل ScoreBat (مصفوفة JSON مباشرة)
            elif api_name == 'ScoreBat' and isinstance(data, list):
                if not data:
                    return f"لا توجد مباريات مقررة لهذا اليوم (المصدر: {api_name})."
                    
                for match in data:
                    home_team = match.get('side1', {}).get('name', 'N/A')
                    away_team = match.get('side2', {}).get('name', 'N/A')
                    match_list.append(f"• {home_team} vs {away_team}")
                return "\n".join(match_list)

            # 3. تحليل هيكل Football-Data.org (يحتوي على حقل 'matches')
            elif api_name == 'Football-Data' and data.get('matches'):
                 matches = data['matches']
                 if matches:
                     for match in matches:
                         home_team = match.get('homeTeam', {}).get('name', 'N/A')
                         away_team = match.get('awayTeam', {}).get('name', 'N/A')
                         match_list.append(f"• {home_team} vs {away_team}")
                     return "\n".join(match_list)
            
            # إذا تم الاتصال ونجح (200 OK)، ولكن لم يتم تحليل البيانات
            return f"تم الاتصال بـ {api_name}، لكن لا توجد مباريات اليوم أو هيكل البيانات غير مدعوم."
            
        except requests.exceptions.RequestException as e:
            # فشل الاتصال، نطبع الخطأ وننتقل للتجربة التالية
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
        # أمر لاختبار النشر والتصفية
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
