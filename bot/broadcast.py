import os
import sys
import time
import requests
import django
from dotenv import load_dotenv

# --- DJANGO SETUP FOR STANDALONE RUNNING ---
# This allows you to run this script directly from your terminal while interacting with your models!
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")  # Replace 'config' with your main project folder name if different
django.setup()

# Import your database models now that Django is initialized
from bot.models import FleetCustomer

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

def send_whatsapp_template(to_phone, template_name, customer_name=None, vehicle_number=None):
    """
    Fires an official approved Meta message template to a target customer.
    """
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    template_payload = {
        "name": template_name,
        "language": {
            "code": "en_US"
        }
    }
    
    # Inject variables dynamic checking (if using custom alerts)
    if template_name != "hello_world" and (customer_name or vehicle_number):
        template_payload["components"] = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": customer_name if customer_name else ""},
                    {"type": "text", "text": vehicle_number if vehicle_number else ""}
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
        return response.status_code == 200
    except Exception:
        return False


def run_massive_broadcast(template_name):
    """
    Queries your 10,000 active database customers and loops them 
    safely with built-in speed pacing to avoid Meta rate blocks.
    """
    # Pull only active customers to avoid wasting money on un-subscribed users
    active_customers = FleetCustomer.objects.filter(is_active=True)
    total_count = active_customers.count()
    
    print(f"🚀 Found {total_count} active fleet accounts in database.")
    print(f"🎬 Initiating streaming broadcast loops using template: '{template_name}'...")
    
    success_count = 0
    fail_count = 0
    start_time = time.time()
    
    # .iterator() processes rows line-by-line out of your database to preserve memory
    # chunk_size=500 fetches them in clean database blocks
    for index, customer in enumerate(active_customers.iterator(chunk_size=500), 1):
        
        # Call the Meta delivery pipeline
        is_delivered = send_whatsapp_template(
            to_phone=customer.phone_number,
            template_name=template_name,
            customer_name=customer.owner_name,
            vehicle_number=customer.truck_number
        )
        
        if is_delivered:
            success_count += 1
        else:
            fail_count += 1
            
        # ⏱️ THROUGHPUT CONTROL (Pacing Guardrail):
        # Meta's standard limit allows 80 messages per second.
        # Adding a microscopic sleep delay ensures your script safely protects your network.
        time.sleep(0.02)  # Generates a maximum delivery pacing of ~50 messages per second
        
        # Log update metrics to terminal every 100 entries
        if index % 100 == 0 or index == total_count:
            print(f"📦 Progress Tracking: {index}/{total_count} processed... (Success: {success_count} | Failed: {fail_count})")
            
    end_time = time.time()
    total_duration = round(end_time - start_time, 2)
    
    print("\n🏁 --- BROADCAST PIPELINE REPORT ---")
    print(f"✅ Successful Deliveries: {success_count}")
    print(f"❌ Failed Deliveries: {fail_count}")
    print(f"⏱️ Total Operational Run Time: {total_duration} seconds")


if __name__ == "__main__":
    # Test it with 'hello_world' first! 
    # Switch to your custom dashboard name when ready.
    TARGET_TEMPLATE = "hello_world" 
    
    run_massive_broadcast(TARGET_TEMPLATE)