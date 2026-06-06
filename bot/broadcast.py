import os
import requests
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

def send_whatsapp_template(to_phone, template_name, customer_name=None, vehicle_number=None):
    """
    Fires an official approved Meta message template to a target customer.
    Bypasses the 24-hour service restriction to open Case B billing.
    """
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 1. Base template structure
    template_payload = {
        "name": template_name,
        "language": {
            "code": "en_US"
        }
    }
    
    # 2. Add parameters ONLY if we are NOT using the default 'hello_world' template.
    # This prevents the (#132000) parameter mismatch error during sandbox testing!
    if template_name != "hello_world" and (customer_name or vehicle_number):
        template_payload["components"] = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": customer_name if customer_name else ""
                    },
                    {
                        "type": "text",
                        "text": vehicle_number if vehicle_number else ""
                    }
                ]
            }
        ]
        
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "template",
        "template": template_payload
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()
        
        if response.status_code == 200:
            display_name = customer_name if customer_name else "Customer"
            print(f"✅ Template successfully delivered to {display_name} ({to_phone})")
        else:
            print(f"❌ Meta API error for {to_phone}: {response_data.get('error', {}).get('message')}")
            
    except Exception as e:
        print(f"💥 Network connection failed during broadcast task: {e}")


# --- TEST MASS BROADCAST EXECUTION ---
if __name__ == "__main__":
    # For local sandbox testing, use Meta's built-in "hello_world".
    # Change this to "fueltracks_utility_alert" later once approved in your dashboard!
    MY_APPROVED_TEMPLATE = "hello_world"
    
    # Mock data array
    fleet_customers = [
        {"phone": "916281670029", "name": "Madhu", "vehicle": "TS-09-EQ-1234"},
    ]
    
    print(f"🚀 Starting automated tracking update broadcast to {len(fleet_customers)} devices...")
    
    # Loop over your array and execute individually
    for customer in fleet_customers:
        send_whatsapp_template(
            to_phone=customer["phone"],
            template_name=MY_APPROVED_TEMPLATE,
            customer_name=customer["name"],
            vehicle_number=customer["vehicle"]
        )
        
    print("🏁 Broadcast pipeline completed successfully.")