import os
import requests
import json
from datetime import date, datetime
from flask import Flask, request, jsonify

# تهيئة تطبيق Flask
app = Flask(__name__)

# --- متغيرات البيئة (يتم جلبها من إعدادات Render) ---
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN') 
FB_PAGE_TOKEN = os.environ.get('FB_PAGE_TOKEN') 
FB_PAGE_ID = os.environ.get('FB_PAGE_ID')

# متغيرات API الرياضي
RAPIDAPI_HOST = os.environ.get('RAPIDAPI_HOST')
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY')

# --- متغيرات الصور الموحدة (يجب استبدالها بروابط عامة خاصة بك) ---
# يجب تغيير هذه الروابط قبل الدفع!
IMAGE_URLS = {
    'GOAL': "https://your-domain.com/images/goal_icon.jpg",  # رابط صورة الهدف
    'START': "https://your-domain.com/images/start_match.jpg", # رابط صورة بداية المباراة
    'RED_CARD': "https://your-domain.com/images/red_card.jpg" # رابط صورة البطاقة الحمراء
}


# =================================================================
#                         وظائف النشر (POSTING)
# =================================================================

def post_to_facebook(message, image_url, language='ar'):
    """
    تنشر رسالة وصورة على الصفحة مع تصفية الجمهور (Targeting) حسب اللغة.
    """
    if not FB_PAGE_TOKEN or not FB_PAGE_ID:
        print("Error: FB_PAGE_TOKEN or FB_PAGE_ID is missing.")
        return

    # تحديد إعدادات التصفية (Targeting)
    if language == 'ar':
        # الجمهور العربي (الدول العربية + اللغة العربية)
        # 6 = رمز اللغة العربية
        targeting = {
            "geo_locations": {"countries": ["DZ", "EG", "SA", "AE", "MA", "TN", "QA", "KW"]},
            "locales": [6] 
        }
    else: # English (en)
        # الجمهور الأجنبي (بعض الدول غير العربية + اللغة الإنجليزية)
        # 1 = رمز اللغة الإنجليزية
        targeting = {
            "geo_locations": {"countries": ["US", "GB", "FR", "DE", "CA", "ES"]},
            "locales": [1] 
        }
    
    # تحويل التصفية إلى نص JSON
    targeting_json = json.dumps(targeting)

    # نقطة النهاية لنشر صورة ورسالة
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


# --- دوال الأحداث المُحددة ---

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
#                       وظائف API الرياضي والردود
# =================================================================

def get_today_matches():
    """
    جلب مباريات اليوم من RapidAPI وعرضها في قائمة بسيطة.
    ** تم تحديث المسار هنا **
    """
    if not RAPIDAPI_HOST or not RAPIDAPI_KEY:
        return "لا يمكن الاتصال بمصدر البيانات الرياضية حالياً. (راجع RAPIDAPI Keys)"

    # تحديد التاريخ اليوم بتنسيق YYYY-MM-DD
    today_date = date.today().strftime("%Y-%m-%d")

    # *****************************************************************
    # التعديل: استخدام المسار الصحيح للـ API الجديد
    # *****************************************************************
    url = f"https://{RAPIDAPI_HOST}/get-matches/events-by-date"
    
    # البارامتر المطلوب لجلب المباريات باليوم
    querystring = {"date": today_date}

    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        match_list = ["*مباريات اليوم:*\n"]
        
        # يجب تعديل هذا المنطق لاحقاً ليناسب هيكل JSON للـ API الجديد
        if data and data.get('response'):
            matches = data['response']
            
            if not matches:
                return "لا توجد مباريات مقررة لهذا اليوم."
                
            for match in matches:
                # هذه الحقول مفترضة، وقد تحتاج تعديلها لتناسب الـ API الجديد
                home_team = match.get('home_team', 'فريق غير معروف')
                away_team = match.get('away_team', 'فريق غير معروف')
                match_time = match.get('time', 'N/A')
                league_name = match.get('league_name', 'غير محددة')
                
                match_list.append(f"*{match_time}* | {home_team} - {away_team} ({league_name})")
                
            return "\n".join(match_list)
        
        # إذا فشل تحليل JSON، نطبع رسالة خطأ
        return f"حدث خطأ في استقبال بيانات المباريات. (الرد: {data})"

    except requests.exceptions.RequestException as e:
        print(f"RapidAPI Error in get_today_matches: {e}")
        return "آسف، فشل الاتصال بخدمة النتائج الرياضية."


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
