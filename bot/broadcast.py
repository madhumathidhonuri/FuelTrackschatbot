from bot.models import FleetCustomer, ChatMessage, BroadcastTask, BroadcastRecipient, WhatsAppTemplate
import os
import sys
import time
import json
import asyncio
import requests
import httpx
import django
from dotenv import load_dotenv


def safe_print(*args, **kwargs):
    try:
        import builtins
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            safe_args = [
                str(arg).encode(
                    'ascii', errors='backslashreplace').decode('ascii')
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
try:
    django.setup()
except Exception:
    pass


load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

# Default Tier Warning Thresholds (Tier 1 = 1,000, Tier 2 = 10,000, Tier 3 = 100,000)
DAILY_TIER_LIMIT = 100000
MAX_RETRIES = 3


def get_template_config(template_name):
    """
    Fetches and caches template configuration from DB to eliminate DB lookups per contact.
    """
    template_config = {
        'has_variables': False,
        'var_count': 0,
        'has_header': False,
        'header_type': 'none',
        'header_image_url': '',
        'header_file_url': None,
        'header_media_id': '',
        'category': 'utility'
    }
    try:
        template_obj = WhatsAppTemplate.objects.filter(template_name=template_name).first()
        if template_obj:
            template_config['category'] = template_obj.category.lower() if template_obj.category else 'utility'
            template_config['has_variables'] = template_obj.has_variables
            template_config['var_count'] = getattr(template_obj, 'var_count', 0)
            template_config['has_header'] = template_obj.has_header
            template_config['header_type'] = template_obj.header_type
            template_config['header_image_url'] = template_obj.header_image_url
            template_config['header_media_id'] = template_obj.header_media_id
            if template_obj.header_file:
                site_url = os.getenv("SITE_URL", "https://whatsapp-ai-bot-dqot.onrender.com")
                if site_url.endswith("/"):
                    site_url = site_url[:-1]
                template_config['header_file_url'] = f"{site_url}{template_obj.header_file.url}"
        else:
            if template_name in ["fuel_alert", "fleet_update", "promo_blast"]:
                template_config['has_variables'] = True
                template_config['var_count'] = 2 if template_name in ["fuel_alert", "fleet_update"] else 1
            if template_name in ["gps_tracking_device", "ais_140_gps_mining_device", "promo_blast"]:
                template_config['category'] = 'marketing'
    except Exception:
        pass
    return template_config


def build_template_payload(to_phone, template_name, customer_name=None, vehicle_number=None,
                           language_code="en_US", template_config=None):
    """
    Constructs the exact Meta Cloud API payload for template messages.
    """
    if template_config is None:
        template_config = get_template_config(template_name)

    category = template_config.get('category', 'utility')
    endpoint_path = "marketing_messages" if category == 'marketing' else "messages"
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/{endpoint_path}"

    template_payload = {
        "name": template_name,
        "language": {"code": language_code}
    }

    components = []
    has_header = template_config.get('has_header', False)
    header_type = template_config.get('header_type', 'none')
    header_media_id = template_config.get('header_media_id', '')
    header_file_url = template_config.get('header_file_url', None)
    header_image_url = template_config.get('header_image_url', '')

    if has_header and header_type in ('image', 'video', 'document'):
        media_data = {}
        if header_media_id:
            media_data = {"id": header_media_id}
        else:
            media_url_or_id = header_file_url or header_image_url
            if media_url_or_id:
                if media_url_or_id.startswith("http://") or media_url_or_id.startswith("https://"):
                    media_data = {"link": media_url_or_id}
                else:
                    media_data = {"id": media_url_or_id}

        if media_data:
            components.append({
                "type": "header",
                "parameters": [{header_type: media_data, "type": header_type}]
            })

    has_variables = template_config.get('has_variables', False)
    var_count = template_config.get('var_count', 0)
    if has_variables and var_count > 0:
        params = []
        if var_count >= 1:
            params.append({"type": "text", "text": customer_name or "Customer"})
        if var_count >= 2:
            params.append({"type": "text", "text": vehicle_number or "N/A"})

        if params:
            components.append({
                "type": "body",
                "parameters": params
            })

    if components:
        template_payload["components"] = components

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_phone,
        "type": "template",
        "template": template_payload
    }

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    return url, headers, payload


def send_whatsapp_template(to_phone, template_name, customer_name=None,
                           vehicle_number=None, language_code="en_US",
                           template_config=None, record_chat_message=True):
    """
    Synchronous fallback for sending a single template message to one recipient.
    Returns (success: bool, error_reason: str)
    """
    if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID:
        return False, "WHATSAPP_TOKEN or PHONE_NUMBER_ID missing in environment"

    url, headers, payload = build_template_payload(
        to_phone, template_name, customer_name, vehicle_number, language_code, template_config
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code in (200, 201):
                msg_id = None
                try:
                    resp_data = response.json()
                    messages = resp_data.get("messages", [])
                    msg_id = messages[0].get("id") if messages else None
                except Exception:
                    pass

                if record_chat_message:
                    try:
                        ChatMessage.objects.create(
                            phone_number=to_phone,
                            role='assistant',
                            content=f"[System Sent Broadcast: {template_name}]",
                            message_id=msg_id
                        )
                    except Exception:
                        pass
                return True, None

            try:
                resp_json = response.json()
                error_msg = resp_json.get("error", {}).get("message", "Unknown error")
                error_code = resp_json.get("error", {}).get("code", "?")
            except Exception:
                error_msg = response.text[:200]
                error_code = f"HTTP_{response.status_code}"

            if error_code == 132001 and payload.get("template", {}).get("language", {}).get("code") == "en":
                payload["template"]["language"]["code"] = "en_US"
                continue

            if error_code in (4, 130429) and attempt < MAX_RETRIES:
                time.sleep(15 * attempt)
                continue

            return False, f"[Code {error_code}] {error_msg}"

        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES:
                time.sleep(5)
                continue
            return False, "Request timed out"
        except Exception as e:
            return False, str(e)

    return False, "Retries exhausted"


def _db_call(func, *args, **kwargs):
    from django.db import connection
    try:
        return func(*args, **kwargs)
    finally:
        connection.close()


class AsyncBroadcastEngine:
    """
    High-throughput async broadcast engine designed for 50,000+ recipients.
    Features:
    - Connection pooling (httpx.AsyncClient)
    - Token-bucket rate limiter pacing requests up to target RPS (e.g. 50 msg/sec)
    - Auto backoff on Meta HTTP 429 / Error 130429
    - Bulk database status updates
    - Live pause/resume state checking
    """

    def __init__(self, task_id, rate_limit_per_sec=50):
        self.task_id = task_id
        self.rate_limit_per_sec = min(max(rate_limit_per_sec, 5), 80)  # Safe bounds: 5-80 msg/sec
        self.semaphore = asyncio.Semaphore(self.rate_limit_per_sec)
        self.lock = asyncio.Lock()
        self.is_paused = False

    async def _send_single_async(self, client, recipient, template_config, task_obj):
        """
        Sends template to a single recipient asynchronously with rate-limit protection.
        """
        async with self.semaphore:
            # Token pacing: ensure smooth distribution per second
            await asyncio.sleep(1.0 / self.rate_limit_per_sec)

            # Check if task was paused or cancelled in DB
            if self.is_paused:
                return recipient.id, False, "Paused", None, "TASK_PAUSED"

            success, error_reason = await asyncio.to_thread(
                _db_call,
                send_whatsapp_template,
                to_phone=recipient.phone_number,
                template_name=task_obj.template_name,
                customer_name=recipient.owner_name,
                vehicle_number=recipient.truck_number,
                language_code=task_obj.language_code,
                template_config=template_config,
                record_chat_message=False
            )
            if success:
                return recipient.id, True, None, "fake_wamid", None
            else:
                return recipient.id, False, error_reason or "Send failed", None, "FAILED"


    async def run_broadcast_async(self):
        """
        Executes the async broadcast in parallel batches with bulk DB commits.
        """
        from django.utils import timezone
        try:
            task_obj = await asyncio.to_thread(_db_call, BroadcastTask.objects.get, id=self.task_id)
        except BroadcastTask.DoesNotExist:
            print(f"❌ BroadcastTask {self.task_id} not found.")
            return

        task_obj.status = 'running'
        await asyncio.to_thread(_db_call, task_obj.save)

        template_config = await asyncio.to_thread(_db_call, get_template_config, task_obj.template_name)

        # HTTPX Client with pooled connections for max speed
        limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
        async with httpx.AsyncClient(limits=limits) as client:
            
            # Fetch pending recipients in chunks of 1000
            BATCH_SIZE = 1000
            while True:
                # Refresh task status to check for admin Pause/Cancel signals
                task_obj = await asyncio.to_thread(_db_call, BroadcastTask.objects.get, id=self.task_id)
                if task_obj.status in ('paused', 'cancelled', 'stopped'):
                    print(f"🛑 BroadcastTask {self.task_id} status changed to '{task_obj.status}'. Halting workers.")
                    return

                def fetch_pending():
                    return list(BroadcastRecipient.objects.filter(
                        task_id=self.task_id, status__in=['pending', 'queued']
                    )[:BATCH_SIZE])

                pending_recipients = await asyncio.to_thread(_db_call, fetch_pending)

                if not pending_recipients:
                    break  # All recipients processed!

                # Mark batch as 'queued'
                recipient_ids = [r.id for r in pending_recipients]
                def mark_queued():
                    BroadcastRecipient.objects.filter(id__in=recipient_ids).update(status='queued')

                await asyncio.to_thread(_db_call, mark_queued)

                # Dispatch async send tasks concurrently
                tasks = [
                    self._send_single_async(client, recipient, template_config, task_obj)
                    for recipient in pending_recipients
                ]

                results = await asyncio.gather(*tasks)

                # Prepare bulk database updates
                updated_recipients = []
                chat_logs_to_create = []
                recipients_dict = {r.id: r for r in pending_recipients}
                batch_success = 0
                batch_failed = 0

                for r_id, success, err_msg, wamid, err_code in results:
                    rec = recipients_dict.get(r_id)
                    if not rec:
                        continue

                    if success:
                        rec.status = 'sent'
                        rec.wamid = wamid
                        rec.sent_at = timezone.now()
                        batch_success += 1
                        chat_logs_to_create.append(ChatMessage(
                            phone_number=rec.phone_number,
                            role='assistant',
                            content=f"[System Sent Broadcast: {task_obj.template_name}]",
                            message_id=wamid
                        ))
                    else:
                        rec.status = 'failed'
                        rec.error_message = err_msg
                        rec.error_code = err_code
                        batch_failed += 1

                    updated_recipients.append(rec)

                # Perform high-performance bulk DB update
                def perform_bulk_update():
                    BroadcastRecipient.objects.bulk_update(
                        updated_recipients,
                        ['status', 'wamid', 'error_message', 'error_code', 'sent_at']
                    )
                await asyncio.to_thread(_db_call, perform_bulk_update)

                if chat_logs_to_create:
                    try:
                        def perform_bulk_create_logs():
                            ChatMessage.objects.bulk_create(
                                chat_logs_to_create,
                                ignore_conflicts=True
                            )
                        await asyncio.to_thread(_db_call, perform_bulk_create_logs)
                    except Exception:
                        pass

                # Update main task progress
                def update_task_progress():
                    t = BroadcastTask.objects.get(id=self.task_id)
                    t.processed_records += len(results)
                    t.success_count += batch_success
                    t.failed_count += batch_failed
                    t.save()

                await asyncio.to_thread(_db_call, update_task_progress)



                # Update Task counters in DB
                task_obj.processed_records += len(results)
                task_obj.success_count += batch_success
                task_obj.failed_count += batch_failed

                if task_obj.processed_records >= task_obj.total_records:
                    task_obj.status = 'completed'

                await asyncio.to_thread(task_obj.save)
                print(f"📦 Task {self.task_id} Progress: {task_obj.processed_records}/{task_obj.total_records} | Success: {task_obj.success_count} | Failed: {task_obj.failed_count}")

        # Final check
        task_obj = await asyncio.to_thread(BroadcastTask.objects.get, id=self.task_id)
        if task_obj.processed_records >= task_obj.total_records:
            task_obj.status = 'completed'
            await asyncio.to_thread(task_obj.save)
            print(f"🏁 BroadcastTask {self.task_id} Completed Successfully!")


async def _process_chunk_async(task_id, chunk_size=1000):
    """
    Asynchronously processes a single chunk of up to `chunk_size` pending recipients.
    Designed for Render Free Tier (completes in ~15-20s, well within Render's 100s timeout).
    """
    from django.utils import timezone
    try:
        task_obj = await asyncio.to_thread(BroadcastTask.objects.get, id=task_id)
    except BroadcastTask.DoesNotExist:
        return {"error": f"BroadcastTask #{task_id} not found"}

    if task_obj.status in ('paused', 'cancelled', 'stopped'):
        return {
            "status": task_obj.status,
            "processed": task_obj.processed_records,
            "total": task_obj.total_records,
            "success": task_obj.success_count,
            "failed": task_obj.failed_count,
            "percent": round((task_obj.processed_records / task_obj.total_records) * 100, 1) if task_obj.total_records > 0 else 0
        }

    task_obj.status = 'running'
    await asyncio.to_thread(task_obj.save)

    template_config = await asyncio.to_thread(get_template_config, task_obj.template_name)
    engine = AsyncBroadcastEngine(task_id, rate_limit_per_sec=task_obj.rate_limit_per_sec)

    pending_recipients = await asyncio.to_thread(
        list,
        BroadcastRecipient.objects.filter(
            task_id=task_id, status__in=['pending', 'queued']
        )[:chunk_size]
    )

    if not pending_recipients:
        task_obj.status = 'completed'
        await asyncio.to_thread(task_obj.save)
        return {
            "status": "completed",
            "processed": task_obj.processed_records,
            "total": task_obj.total_records,
            "success": task_obj.success_count,
            "failed": task_obj.failed_count,
            "percent": 100.0
        }

    recipient_ids = [r.id for r in pending_recipients]
    await asyncio.to_thread(
        BroadcastRecipient.objects.filter(id__in=recipient_ids).update,
        status='queued'
    )

    limits = httpx.Limits(max_keepalive_connections=50, max_connections=100)
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [
            engine._send_single_async(client, recipient, template_config, task_obj)
            for recipient in pending_recipients
        ]
        results = await asyncio.gather(*tasks)

    updated_recipients = []
    chat_logs_to_create = []
    recipients_dict = {r.id: r for r in pending_recipients}
    batch_success = 0
    batch_failed = 0

    for r_id, success, err_msg, wamid, err_code in results:
        rec = recipients_dict.get(r_id)
        if not rec:
            continue
        if success:
            rec.status = 'sent'
            rec.wamid = wamid
            rec.sent_at = timezone.now()
            batch_success += 1
            chat_logs_to_create.append(ChatMessage(
                phone_number=rec.phone_number,
                role='assistant',
                content=f"[System Sent Broadcast: {task_obj.template_name}]",
                message_id=wamid
            ))
        else:
            rec.status = 'failed'
            rec.error_message = err_msg
            rec.error_code = err_code
            batch_failed += 1
        updated_recipients.append(rec)

    await asyncio.to_thread(
        BroadcastRecipient.objects.bulk_update,
        updated_recipients,
        ['status', 'wamid', 'error_message', 'error_code', 'sent_at']
    )

    if chat_logs_to_create:
        try:
            await asyncio.to_thread(
                ChatMessage.objects.bulk_create,
                chat_logs_to_create,
                ignore_conflicts=True
            )
        except Exception:
            pass


    task_obj.processed_records += len(results)
    task_obj.success_count += batch_success
    task_obj.failed_count += batch_failed

    if task_obj.processed_records >= task_obj.total_records:
        task_obj.status = 'completed'

    await asyncio.to_thread(task_obj.save)

    percent = round((task_obj.processed_records / task_obj.total_records) * 100, 1) if task_obj.total_records > 0 else 100.0

    return {
        "status": task_obj.status,
        "processed": task_obj.processed_records,
        "total": task_obj.total_records,
        "success": task_obj.success_count,
        "failed": task_obj.failed_count,
        "chunk_size": len(results),
        "percent": percent
    }


def process_broadcast_chunk(task_id, chunk_size=1000):
    """
    Synchronous wrapper for processing a single chunk of up to `chunk_size` pending recipients.
    Returns status dict.
    """
    return asyncio.run(_process_chunk_async(task_id, chunk_size))



def create_broadcast_campaign(template_name, language_code="en_US",
                              csv_or_excel_path=None, rate_limit_per_sec=50):
    """
    Initializes a BroadcastTask and populates 50,000+ BroadcastRecipient rows in bulk.
    Returns task_id.
    """
    from bot.utils import parse_excel_or_csv, normalize_phone_number

    recipients_to_create = []

    if csv_or_excel_path:
        print(f"📖 Parsing customers from file: {csv_or_excel_path}")
        customers_data = parse_excel_or_csv(csv_or_excel_path)

        for cust in customers_data:
            phone = normalize_phone_number(cust.get('phone_number'))
            if not phone or len(phone) < 10:
                continue
            recipients_to_create.append({
                'phone_number': phone,
                'owner_name': cust.get('owner_name', ''),
                'truck_number': cust.get('truck_number', '')
            })
    else:
        print("📖 Loading active customers from database...")
        active_customers = FleetCustomer.objects.filter(is_active=True)
        for cust in active_customers.iterator(chunk_size=2000):
            recipients_to_create.append({
                'phone_number': cust.phone_number,
                'owner_name': cust.owner_name or '',
                'truck_number': cust.truck_number or ''
            })

    total_count = len(recipients_to_create)
    if total_count == 0:
        print("❌ No valid active phone numbers found for broadcast.")
        return None

    # Deduplicate phone numbers per task to avoid duplicate sends
    seen_phones = set()
    unique_recipients = []
    for item in recipients_to_create:
        p = item['phone_number']
        if p not in seen_phones:
            seen_phones.add(p)
            unique_recipients.append(item)

    total_unique = len(unique_recipients)

    task_obj = BroadcastTask.objects.create(
        template_name=template_name,
        language_code=language_code,
        excel_file_name=os.path.basename(csv_or_excel_path) if csv_or_excel_path else "Database Active Customers",
        status='pending',
        total_records=total_unique,
        processed_records=0,
        success_count=0,
        failed_count=0,
        rate_limit_per_sec=rate_limit_per_sec
    )

    print(f"🚀 Creating {total_unique} BroadcastRecipient records in bulk for Task #{task_obj.id}...")

    recipient_objects = [
        BroadcastRecipient(
            task=task_obj,
            phone_number=item['phone_number'],
            owner_name=item['owner_name'],
            truck_number=item['truck_number'],
            status='pending'
        )
        for item in unique_recipients
    ]

    # Bulk insert in batches of 2000
    _db_call(BroadcastRecipient.objects.bulk_create, recipient_objects, batch_size=2000)
    print(f"✅ Successfully initialized BroadcastTask #{task_obj.id} with {total_unique} recipients.")
    from django.db import connection
    connection.close()
    return task_obj.id



def execute_broadcast_task_sync(task_id):
    """
    Synchronous wrapper to launch the async broadcast engine.
    Safe for threading / background execution.
    """
    try:
        task_obj = _db_call(BroadcastTask.objects.get, id=task_id)
        engine = AsyncBroadcastEngine(task_id, rate_limit_per_sec=task_obj.rate_limit_per_sec)
        asyncio.run(engine.run_broadcast_async())
    except Exception as e:
        print(f"❌ Execution error on Task #{task_id}: {e}")
        try:
            task_obj = _db_call(BroadcastTask.objects.get, id=task_id)
            task_obj.status = 'failed'
            task_obj.failed_details = str(e)
            _db_call(task_obj.save)
        except Exception:
            pass




def run_massive_broadcast(template_name, language_code="en_US", csv_or_excel_path=None, rate_limit_per_sec=50):
    """
    Main entry point for CLI or standalone script running.
    """
    print(f"🎬 Initializing massive broadcast campaign for template: '{template_name}'...")
    task_id = create_broadcast_campaign(template_name, language_code, csv_or_excel_path, rate_limit_per_sec)
    if task_id:
        print(f"⚡ Starting high-speed broadcast engine for Task #{task_id}...")
        execute_broadcast_task_sync(task_id)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run High-Speed WhatsApp Template Broadcast for 50,000+ recipients.")
    parser.add_argument("--file", help="Path to Excel (.xlsx, .xls) or CSV (.csv) file containing customer list.")
    parser.add_argument("--template", default="hello_world", help="Name of Meta message template to send.")
    parser.add_argument("--language", default="en_US", help="Language code of the template (e.g. en_US, hi).")
    parser.add_argument("--rate", type=int, default=50, help="Max requests per second (e.g. 50).")

    args = parser.parse_args()

    file_path = args.file
    if not file_path:
        from django.conf import settings
        media_dir = os.path.join(settings.BASE_DIR, 'media')
        default_files = ['broadcast_list.xlsx', 'broadcast_list.xls', 'broadcast_list.csv']
        for df_name in default_files:
            p = os.path.join(media_dir, df_name)
            if os.path.exists(p):
                file_path = p
                print(f"📂 Found default uploaded file at {file_path}.")
                break

    run_massive_broadcast(args.template, args.language, file_path, args.rate)
