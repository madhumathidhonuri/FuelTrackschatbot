import os
import sys
import time
import requests
import django
from dotenv import load_dotenv

def safe_print(*args, **kwargs):
    try:
        import builtins
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            safe_args = [
                str(arg).encode('ascii', errors='backslashreplace').decode('ascii')
                for arg in args
            ]
            import builtins
            builtins.print(*safe_args, **kwargs)
        except Exception:
            pass

print = safe_print

# --- DJANGO SETUP FOR STANDALONE RUNNING ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from bot.models import FleetCustomer, ChatMessage

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

# ✅ Set this to your Meta tier limit (1000 for new accounts, 10000 after upgrade)
DAILY_TIER_LIMIT = 1000

# ✅ Max retry attempts if Meta returns a temporary error
MAX_RETRIES = 3


def send_whatsapp_template(to_phone, template_name, customer_name=None, vehicle_number=None, language_code="en_US"):
    """
    Fires an approved Meta message template to a single customer.
    Returns (success: bool, error_reason: str)
    """
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    template_payload = {
        "name": template_name,
        "language": {"code": language_code}
    }

    # ✅ FIX 4: Only inject body parameters for custom templates that actually have placeholders
    TEMPLATES_WITH_VARIABLES = ["fuel_alert", "fleet_update", "promo_blast"]  # Add your real template names here

    if template_name in TEMPLATES_WITH_VARIABLES and (customer_name or vehicle_number):
        template_payload["components"] = [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": customer_name or "Customer"},
                    {"type": "text", "text": vehicle_number or "N/A"}
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

    # ✅ FIX 3: Retry loop for temporary failures
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)

            # ✅ FIX 1: Meta returns 200 OR 201 for success depending on endpoint version
            if response.status_code in (200, 201):
                try:
                    TEMPLATE_DESCRIPTIONS = {
                        "hello_world": "Welcome to Fuel Tracks Technologies! We offer high-end GPS Tracking Systems and Smart Fuel Monitoring.",
                        "gps_tracking_device": "Marketing message promoting our AIS 140 certified GPS tracking devices.",
                        "fuel_alert": "Utility alert warning about vehicle fuel drop/theft.",
                        "fleet_update": "Fleet status update summary."
                    }
                    desc = TEMPLATE_DESCRIPTIONS.get(template_name, f"Broadcast template: {template_name}")
                    ChatMessage.objects.create(
                        phone_number=to_phone,
                        role='assistant',
                        content=f"[System Sent Broadcast: {desc}]"
                    )
                except Exception as e:
                    print(f"Failed to record broadcast message in history: {e}")
                return True, None

            # ✅ FIX 2: Safely extract error reason from Meta response without crashing on HTML responses
            try:
                resp_json = response.json()
                error_msg = resp_json.get("error", {}).get("message", "Unknown error")
                error_code = resp_json.get("error", {}).get("code", "?")
            except Exception:
                error_msg = response.text[:200]
                error_code = f"HTTP_{response.status_code}"

            # If it's a rate limit error (code 4 or 130429), wait and retry
            if error_code in (4, 130429) and attempt < MAX_RETRIES:
                print(f"   ⚠️  Rate limit hit for {to_phone}. Waiting 30s before retry {attempt}/{MAX_RETRIES}...")
                time.sleep(30)
                continue

            # Non-retryable error — return immediately
            return False, f"[Code {error_code}] {error_msg}"

        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES:
                print(f"   ⚠️  Timeout for {to_phone}. Retry {attempt}/{MAX_RETRIES}...")
                time.sleep(5)
                continue
            return False, "Request timed out after all retries"

        except Exception as e:
            return False, str(e)

    return False, "All retries exhausted"


def run_massive_broadcast(template_name, language_code="en_US"):
    """
    Loops through all active customers and sends the template safely,
    with tier limit protection, retry logic, and detailed failure logging.
    """
    active_customers = FleetCustomer.objects.filter(is_active=True)
    total_count = active_customers.count()

    print(f"🚀 Found {total_count} active fleet accounts in database.")

    # ✅ FIX 5: Warn if total exceeds your current tier limit
    if total_count > DAILY_TIER_LIMIT:
        print(f"⚠️  WARNING: You have {total_count} customers but your daily tier limit is {DAILY_TIER_LIMIT}.")
        print(f"   Only the first {DAILY_TIER_LIMIT} messages will succeed today.")
        print(f"   Run again tomorrow for the remaining {total_count - DAILY_TIER_LIMIT}.")
        confirm = input("   Type YES to continue anyway, or anything else to abort: ").strip()
        if confirm != "YES":
            print("❌ Broadcast cancelled.")
            return

    print(f"🎬 Starting broadcast using template: '{template_name}'...\n")

    success_count = 0
    fail_count = 0
    failed_numbers = []  # Track who failed for re-attempt later
    start_time = time.time()

    for index, customer in enumerate(active_customers.iterator(chunk_size=500), 1):

        # ✅ FIX 5: Hard stop at daily tier limit
        if index > DAILY_TIER_LIMIT:
            print(f"\n🛑 Daily tier limit of {DAILY_TIER_LIMIT} reached. Stopping safely.")
            break

        success, error_reason = send_whatsapp_template(
            to_phone=customer.phone_number,
            template_name=template_name,
            customer_name=customer.owner_name,
            vehicle_number=customer.truck_number,
            language_code=language_code
        )

        if success:
            success_count += 1
        else:
            fail_count += 1
            failed_numbers.append((customer.phone_number, customer.owner_name, error_reason))

        # Safe pacing — 50 messages/second (well within Meta's 80/sec limit)
        time.sleep(0.02)

        # Progress log every 100 entries
        if index % 100 == 0 or index == total_count:
            elapsed = round(time.time() - start_time, 1)
            print(f"📦 {index}/{total_count} | ✅ {success_count} sent | ❌ {fail_count} failed | ⏱️ {elapsed}s elapsed")

    # Final report
    total_duration = round(time.time() - start_time, 2)
    print("\n🏁 --- BROADCAST REPORT ---")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed:     {fail_count}")
    print(f"⏱️  Duration:  {total_duration} seconds")

    # ✅ FIX 2: Print all failures with reasons so you can investigate
    if failed_numbers:
        print("\n📋 Failed Deliveries (phone | name | reason):")
        for phone, name, reason in failed_numbers:
            print(f"   {phone} | {name} | {reason}")

        # Save failures to a file for easy re-processing
        with open("failed_broadcast.txt", "w") as f:
            for phone, name, reason in failed_numbers:
                f.write(f"{phone} | {name} | {reason}\n")
        print("\n💾 Failures saved to failed_broadcast.txt")


if __name__ == "__main__":
    # Use 'hello_world' to test with 1-2 contacts first before running on full list
    TARGET_TEMPLATE = "gps_tracking_device"
    TARGET_LANGUAGE = "en"  # "en" for English, "en_US" for English (US), etc.

    run_massive_broadcast(TARGET_TEMPLATE, TARGET_LANGUAGE)