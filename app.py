import os
import requests
from flask import Flask, request, jsonify

# تهيئة تطبيق Flask
app = Flask(__name__)

# --- متغيرات البيئة (يتم جلبها من إعدادات Render) ---
# تأكد من أن هذه الأسماء مطابقة تماماً لما في Render
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN') 
FB_PAGE_TOKEN = os.environ.get('FB_PAGE_TOKEN') 
FB_PAGE_ID = os.environ.get('FB_PAGE_ID')

# --- دالة مساعدة: إرسال رسالة إلى الماسنجر ---
def send_message(recipient_id, message_text):
    """
    تستخدم لإرسال رسالة نصية بسيطة إلى مستخدم معين عبر Messenger Send API.
    """
    if not FB_PAGE_TOKEN:
        print("Error: FB_PAGE_TOKEN is not configured.")
        return

    params = {
        "access_token": FB_PAGE_TOKEN
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    }
    
    # نقطة النهاية (Endpoint) لإرسال رسائل الماسنجر
    url = "https://graph.facebook.com/v18.0/me/messages" 
    
    try:
        response = requests.post(url, params=params, headers=headers, json=data)
        response.raise_for_status() # إطلاق استثناء لأي رمز حالة HTTP غير ناجح (4xx أو 5xx)
        print(f"Message sent successfully to {recipient_id}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending message to {recipient_id}: {e}")
        if response is not None:
             print(f"Response details: {response.text}")


# --- دالة مساعدة: منطق الردود على الأوامر ---
def handle_message(sender_id, message_text):
    """
    تعالج الرسائل الواردة وتحدد الرد المناسب بناءً على الأمر.
    """
    lower_text = message_text.lower().strip()
    response_text = "آسف، لم أجد طلبك. الأوامر المتاحة هي: 'مباريات اليوم'."
    
    if lower_text == 'مباريات اليوم':
        # *** سيتم تحديث هذا الجزء لاحقاً لربط RapidAPI ***
        response_text = "جاري البحث عن مباريات اليوم (سيتم توفير النتائج قريباً بعد ربط API الرياضي)."
    
    elif lower_text in ['مرحبا', 'سلام', 'hi', 'hello']:
        response_text = "أهلاً بك في Goalixy! لمعرفة آخر النتائج، اكتب 'مباريات اليوم'."
        
    elif lower_text == 'النتيجة':
        response_text = "الرجاء تحديد المباراة أو الفريق الذي تبحث عن نتيجته."
        
    send_message(sender_id, response_text)


# --- المسار الرئيسي للـ Webhook ---
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
        print('Received Webhook Data:', data)

        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    
                    sender_id = messaging_event['sender']['id']
                    
                    # معالجة الرسائل النصية الواردة
                    if messaging_event.get('message'):
                        if 'text' in messaging_event['message']:
                            message_text = messaging_event['message']['text']
                            handle_message(sender_id, message_text)
                            
                    # معالجة الـ Postbacks (لتنفيذ الأوامر من الأزرار)
                    elif messaging_event.get('postback'):
                        payload = messaging_event['postback']['payload']
                        print(f"Received Postback Payload: {payload}")
                        # يمكن استدعاء handle_message(sender_id, payload) هنا أيضاً
                    
                    # ملاحظة: يمكنك إضافة منطق معالجة لأحداث feed هنا لاحقاً

        # يجب أن نُرجع 200 OK لفيسبوك لتجنب إعادة إرسال الحدث
        return 'EVENT_RECEIVED', 200
        
    return 'Invalid method', 405


# أمر تشغيل التطبيق (Render يستخدم Gunicorn)
if __name__ == '__main__':
    # ملاحظة: هذا التشغيل للتجربة المحلية فقط، وليس للإنتاج على Render
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
