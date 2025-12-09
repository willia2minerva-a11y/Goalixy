import os
from flask import Flask, request

# تهيئة تطبيق Flask
app = Flask(__name__)

# --- متغيرات البيئة ---
# يجب تعيين هذا المتغير في إعدادات Render (VERIFY_TOKEN)
VERIFY_TOKEN = os.environ.get('VERIFY_TOKEN', 'GOALIXY_SECRET_TOKEN') 
# رمز الوصول للصفحة (نحتاجه لاحقاً لإرسال الردود)
PAGE_ACCESS_TOKEN = os.environ.get('PAGE_ACCESS_TOKEN')

# المسار الرئيسي للـ Webhook
# يجب أن يكون هذا هو الرابط الذي أدخلته في Meta Developers (مثلاً: https://your-app.onrender.com/webhook)
@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    # 1. التحقق من الـ Webhook (GET Request)
    if request.method == 'GET':
        # الحصول على البارامترات من فيسبوك
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        # التأكد من صحة الوضع ورمز التحقق
        if mode and token:
            if mode == 'subscribe' and token == VERIFY_TOKEN:
                print('WEBHOOK_VERIFIED')
                # إذا كان الرمز صحيحاً، نُرجع الـ challenge
                return challenge, 200
            else:
                # رمز التحقق غير مطابق
                return 'Verification token mismatch', 403
        
        # إذا لم يتم إرسال البارامترات المطلوبة
        return 'Missing required parameters', 400

    # 2. استقبال الأحداث (POST Request)
    elif request.method == 'POST':
        data = request.json
        print('Received Webhook Data:', data)

        # المنطق لمعالجة رسائل الماسنجر أو أحداث المنشورات يوضع هنا لاحقاً
        
        # --- معالجة الرسائل (مثال بسيط) ---
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for messaging_event in entry.get('messaging', []):
                    # نحدد هنا ما إذا كانت رسالة
                    if messaging_event.get('message'):
                        sender_id = messaging_event['sender']['id']
                        message_text = messaging_event['message']['text']
                        print(f"Message from {sender_id}: {message_text}")
                        
                        # هنا ستضيف المنطق للرد التلقائي على أوامر مثل "مباريات اليوم"
                        
                        # يجب أن نُرجع 200 OK لفيسبوك لتجنب إرسال الحدث مجدداً
        return 'EVENT_RECEIVED', 200

# تشغيل التطبيق (للتجربة المحلية فقط، Render يستخدم gunicorn)
if __name__ == '__main__':
    app.run(debug=True)
