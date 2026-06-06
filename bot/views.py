import os
import json
import requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv
from groq import Groq
from .models import ChatMessage

load_dotenv()

ai_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")


def get_ai_response(user_phone, new_user_message):
    """Saves text, extracts past context history, and uses Llama 3 to formulate responses."""
    try:
        # 1. Save new user message to database
        ChatMessage.objects.create(phone_number=user_phone, role='user', content=new_user_message)
        
        system_prompt = (
            "You are an AI assistant representing Purple Technologies. "
            "Be professional, polite, and helpful. If the user introduces themselves, "
            "acknowledge their name and company details. Always attempt to professionally gather "
            "their business address or direct them to call +919618743699. Keep answers concise."
        )
        
        messages_payload = [{"role": "system", "content": system_prompt}]
        
        # 2. Get history (Safely filter and fetch up to last 6 entries chronologically)
        history_queryset = ChatMessage.objects.filter(phone_number=user_phone).order_by('timestamp')
        count = history_queryset.count()
        
        # Get last 6 entries safely
        start_index = max(0, count - 6)
        history = history_queryset[start_index:count]
        
        for msg in history:
            messages_payload.append({"role": msg.role, "content": msg.content})
            
        # 3. Request LLM generation
        completion = ai_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=messages_payload,
            temperature=0.5,
        )
        
        ai_reply = completion.choices[0].message.content
        
        # 4. Save AI reply to database
        ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=ai_reply)
        return ai_reply

    except Exception as e:
        print(f"System processing error inside AI loop: {e}")
        return "Thank you for reaching out to Fuel Tracks Technologies Private Limited. How can we help you?"


def send_whatsapp_message(to_phone, text_content):
    """Dispatches payload to Meta Graph Servers."""
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "text",
        "text": {"body": text_content}
    }
    try:
        res = requests.post(url, json=payload, headers=headers)
        print(f"Meta Graph Server Response Status: {res.status_code}")
    except Exception as e:
        print(f"Failed to post outgoing message via Meta API: {e}")


@csrf_exempt
def whatsapp_webhook(request):
    """Processes verification GET queries and messaging POST actions from Meta."""
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        
        # Make sure values match up with .env configurations
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("Webhook verification checklist passed successfully!")
            return HttpResponse(challenge, content_type="text/plain")
        
        print("Webhook verification checklist failed: Token mismatch.")
        return HttpResponse("Verification Token Mismatch", status=403)

    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            
            # Defensive check: Ensure it's a real messaging update event loop array
            if "object" in data and data["object"] == "whatsapp_business_account":
                entry = data.get("entry", [{}])[0]
                changes = entry.get("changes", [{}])[0]
                value = changes.get("value", {})
                
                if "messages" in value:
                    message_obj = value["messages"][0]
                    user_phone = message_obj["from"]
                    
                    if message_obj.get("type") == "text":
                        user_text = message_obj["text"]["body"]
                        print(f"Received text message: '{user_text}' from phone number: {user_phone}")
                        
                        # Process using AI with database thread memory
                        bot_reply = get_ai_response(user_phone, user_text)
                        send_whatsapp_message(user_phone, bot_reply)
                        
        except Exception as e:
            print(f"Ignored or handled payload structural message notification error: {e}")
            
        # Meta expects a clean 200 JSON OK status wrapper response to confirm receipt
        return JsonResponse({"status": "success"})