import os
import requests
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

def send_whatsapp_template(to_phone, template_name, customer_name, vehicle_number):
    """
    Fires an official approved Meta message template to a target customer.
    This bypasses the 24-hour service restriction to open Case B billing.
    """
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Meta structures templates with a language code and parameters array matching variables like {{1}}, {{2}}
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": "en_US"
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": customer_name        # Replaces {{1}} inside your template layout
                        },
                        {
                            "type": "text",
                            "text": vehicle_number     # Replaces {{2}} inside your template layout
                        }
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()
        
        if response.status_code == 200:
            print(f"✅ Template successfully delivered to {customer_name} ({to_phone})")
        else:
            print(f"❌ Meta API error for {to_phone}: {response_data.get('error', {}).get('message')}")
            
    except Exception as e:
        print(f"💥 Network connection failed during broadcast task: {e}")


# --- TEST MASS BROADCAST EXECUTION ---
if __name__ == "__main__":
    # 1. Provide your exact template name registered in Meta Dashboard
    # Example template string: "Hello {{1}}, your fleet vehicle {{2}} tracker is reporting abnormal fuel metrics."
    MY_APPROVED_TEMPLATE = "fueltracks_utility_alert"
    
    # 2. Mock list mimicking data pulled from your Django customer model tables
    fleet_customers = [
        {"phone": "916281670029", "name": "Madhu", "vehicle": "TS-09-EQ-1234"},
    ]
    
    print(f"🚀 Starting automated tracking update broadcast to {len(fleet_customers)} devices...")
    
    # Loop over your client array and deploy the templates individually
    for customer in fleet_customers:
        send_whatsapp_template(
            to_phone=customer["phone"],
            template_name=MY_APPROVED_TEMPLATE,
            customer_name=customer["name"],
            vehicle_number=customer["vehicle"]
        )
        
    print("🏁 Broadcast pipeline completed successfully.")