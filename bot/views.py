import os
import re
import json
import hmac
import csv
import hashlib
import requests
import contextvars
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from django.db.models import Q
from dotenv import load_dotenv
from groq import Groq
from .models import ChatMessage, FleetCustomer, AdCampaign, AgentNotificationLog

load_dotenv()


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

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# Context variable to hold the phone number ID for the current request
_phone_number_id_ctx = contextvars.ContextVar("phone_number_id", default=None)

# 🌟 CONFIGURATION PARAMETER
# Include your full country code (e.g., +91...)
AGENT_NOTIFY_PHONE = "+919000666914"


def has_keyword_match(text, keywords):
    """
    Checks if any of the keywords match in the text, ensuring word boundaries.
    """
    for kw in keywords:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def is_simple_greeting(text):
    """
    Checks if the clean user text is a simple greeting or start trigger.
    """
    greetings = {
        "hi", "hello", "namaste", "start", "hey", "yo", "good morning", "good afternoon",
        "good evening", "hlo", "hi sir", "hello sir", "హాయ్", "హలో", "నమస్తే", "నమస్కారం",
        "hii", "hiii", "helloo", "helo"
    }
    # Remove simple punctuation like question marks or exclamation marks and
    # trim whitespace
    cleaned = "".join(c for c in text.lower()
                      if c.isalnum() or c.isspace()).strip()
    return cleaned in greetings


def find_device_catalog_match(text, history_messages=None):
    """
    Scans the text (and optionally history) to find which device catalog to send.
    Returns a tuple: (catalog_filename, catalog_name) or (None, None)
    """
    clean_text = text.strip().lower()

    wifi_camera_keywords = [
        "wifi camera",
        "wifi cam",
        "wi-fi camera",
        "వైఫై కెమెరా",
        "wifi security camera"]
    solar_cam_keywords = [
        "solar cam",
        "solar camera",
        "సోలార్ కెమెరా",
        "solar security camera",
        "solar 4g cam"]
    dash_cam_keywords = [
        "dashcam",
        "dash cam",
        "dash camera",
        "డ్యాష్‌కామ్",
        "dashcam dc 01 s",
        "dc 01 s",
        "dc01s"]
    ptz_camera_keywords = [
        "ptz camera",
        "ptz security",
        "ptz కెమెరా",
        "ptz cam"]
    borewell_rod_keywords = [
        "rod count",
        "rod counter",
        "borewell rod",
        "రోడ్ కౌంట్"]
    borewell_rpm_keywords = [
        "rpm count",
        "rpm counter",
        "borewell rpm",
        "rpm కౌంట్"]
    ac_sensor_keywords = [
        "ac sensor",
        "ac temperature sensor",
        "temperature sensor",
        "టెంపరేచర్ సెన్సార్",
        "ac temperature"]
    lcd_monitor_keywords = [
        "lcd monitor",
        "car lcd",
        "monitor screen",
        "మోనిటర్"]
    relay_switch_keywords = [
        "relay",
        "cutoff switch",
        "relay cutoff",
        "cutoff",
        "రిలే"]

    ais_keywords = [
        "ais 140", "ais140", "gps", "tracker", "trackers", "ట్రాకర్", "ట్రాకర్లు", "జిపిఎస్",
        "fmb120", "fmb 120", "fmb910", "fmb 910", "teltonika fmb120", "teltonika fmb910", "teltonika"
    ]
    fuel_keywords = [
        "fuel", "sensor", "sensors", "rod", "theft", "monitoring", "ఫ్యూయల్", "ఇంధన", "సెన్సార్",
        "fmb920", "fmb 920", "italon", "teltonika fmb920"
    ]
    product_keywords = [
        "product",
        "products",
        "catalog",
        "catalogs",
        "కేటలాగ్",
        "ఉత్పత్తులు",
        "catalogue",
        "catalogues"]

    # Match Wifi Camera
    if has_keyword_match(clean_text, wifi_camera_keywords):
        return "Wifi_Camera_Catalog.pdf", "Wifi Camera"
    # Match Solar Cam
    if has_keyword_match(clean_text, solar_cam_keywords):
        return "Solar_Cam_Catalog.pdf", "Solar Cam"
    # Match Dash Cam
    if has_keyword_match(clean_text, dash_cam_keywords):
        return "Dash_Cam_Catalog.pdf", "Dashcam"
    # Match PTZ Camera
    if has_keyword_match(clean_text, ptz_camera_keywords):
        return "PTZ_Camera_Catalog.pdf", "PTZ Camera"
    # Match Borewell Rod Count
    if has_keyword_match(clean_text, borewell_rod_keywords):
        return "Borewell_Rod_Count_Catalog.pdf", "Borewell Rod Count Solution"
    # Match Borewell RPM Count
    if has_keyword_match(clean_text, borewell_rpm_keywords):
        return "Borewell_RPM_Count_Catalog.pdf", "Borewell RPM Count Solution"
    # Match AC Temperature Sensor
    if has_keyword_match(clean_text, ac_sensor_keywords):
        return "AC_Temperature_Sensor_Catalog.pdf", "AC Temperature Sensor"
    # Match Car LCD Monitor
    if has_keyword_match(clean_text, lcd_monitor_keywords):
        return "Car_LCD_Monitor_Catalog.pdf", "Car LCD Monitor"
    # Match Relay Cutoff Switch
    if has_keyword_match(clean_text, relay_switch_keywords):
        return "Relay_Cutoff_Switch_Catalog.pdf", "Relay Cutoff Switch"
    # Match Smart Fuel Monitoring
    if has_keyword_match(clean_text, fuel_keywords):
        return "Smart_Fuel_Monitoring_Catalog.pdf", "Smart Fuel Monitoring"
    # Match AIS 140
    if has_keyword_match(clean_text, ais_keywords):
        return "AIS_140_GPS_Tracker_Catalog.pdf", "AIS 140 GPS Tracker"

    # If it's a generic catalog request, scan history
    generic_catalog_request_keywords = [
        "send catalogue", "send catalog", "send pdf", "share pdf", "share catalog",
        "share catalogue", "pampandi", "pampandi catalog", "pdf pampandi", "catalog pampandi",
        "send catalog pdf", "send details", "get catalog", "get pdf"
    ]
    if has_keyword_match(
            clean_text, generic_catalog_request_keywords) and history_messages:
        for msg in history_messages:
            res_file, res_name = find_device_catalog_match(msg)
            if res_file:
                # Bypass general catalog fallback during history check
                if res_file != "Fuel_Tracks_Catalog.pdf":
                    return res_file, res_name

    # Check product keywords (general catalog)
    if has_keyword_match(clean_text, product_keywords):
        return "Fuel_Tracks_Catalog.pdf", "official Fuel Tracks Product Catalog Guide!"

    return None, None


CATALOG_METADATA = {
    "Wifi_Camera_Catalog.pdf": {
        "te": "ఇదిగోండి వైఫై కెమెరా కేటలాగ్: 📄",
        "en": "Here is the WiFi Camera Catalog: 📄"
    },
    "Solar_Cam_Catalog.pdf": {
        "te": "ఇదిగోండి సోలార్ కెమెరా కేటలాగ్: 📄",
        "en": "Here is the Solar Cam Catalog: 📄"
    },
    "Dash_Cam_Catalog.pdf": {
        "te": "ఇదిగోండి డ్యాష్ కెమెరా కేటలాగ్: 📄",
        "en": "Here is the Dashcam Catalog: 📄"
    },
    "PTZ_Camera_Catalog.pdf": {
        "te": "ఇదిగోండి PTZ సెక్యూరిటీ కెమెరా కేటలాగ్: 📄",
        "en": "Here is the PTZ Camera Catalog: 📄"
    },
    "Borewell_Rod_Count_Catalog.pdf": {
        "te": "ఇదిగోండి బోర్ వెల్ రోడ్ కౌంట్ సొల్యూషన్స్ కేటలాగ్: 📄",
        "en": "Here is the Borewell Rod Count Solution Catalog: 📄"
    },
    "Borewell_RPM_Count_Catalog.pdf": {
        "te": "ఇదిగోండి బోర్ వెల్ RPM కౌంట్ సొల్యూషన్స్ కేటలాగ్: 📄",
        "en": "Here is the Borewell RPM Count Solution Catalog: 📄"
    },
    "AC_Temperature_Sensor_Catalog.pdf": {
        "te": "ఇదిగోండి ఏసి టెంపరేచర్ సెన్సార్ కేటలాగ్: 📄",
        "en": "Here is the AC Temperature Sensor Catalog: 📄"
    },
    "Car_LCD_Monitor_Catalog.pdf": {
        "te": "ఇదిగోండి కార్ LCD మానిటర్ కేటలాగ్: 📄",
        "en": "Here is the Car LCD Monitor Catalog: 📄"
    },
    "Relay_Cutoff_Switch_Catalog.pdf": {
        "te": "ఇదిగోండి రిలే కటాఫ్ స్విచ్ కేటలాగ్: 📄",
        "en": "Here is the Relay Cutoff Switch Catalog: 📄"
    },
    "Smart_Fuel_Monitoring_Catalog.pdf": {
        "te": "ఇదిగోండి స్మార్ట్ ఫ్యూయల్ మానిటరింగ్ సిస్టమ్ కేటలాగ్: 📄",
        "en": "Here is the Smart Fuel Monitoring Catalog: 📄"
    },
    "AIS_140_GPS_Tracker_Catalog.pdf": {
        "te": "ఇదిగోండి AIS 140 GPS ట్రాకర్ కేటలాగ్: 📄",
        "en": "Here is the AIS 140 GPS Tracker Catalog: 📄"
    },
    "Fuel_Tracks_Catalog.pdf": {
        "te": "ఇదిగోండి మా ఉత్పత్తుల కేటలాగ్: 📄",
        "en": "Here is our official Fuel Tracks Product Catalog Guide! 📄"
    }
}


CONTACT_KEYWORDS = [
    "give his number", "his phone number", "contact number", "give number",
    "number of the human", "number send", "number bodybuilding", "number ivvu",
    "number pampandi", "ph no", "phone no", "mobile number", "contact details",
    "phone number", "mobile", "whatsapp number", "karunakar number", "karunakar phone",
    "his number", "his contact", "agent number", "agent phone", "agent contact",
    "reddy number", "reddy phone", "provide phone number", "send phone number",
    "give phone number", "how can i contact", "how to contact", "how can we contact",
    "contact you", "contact us", "how to reach", "how can i reach",
    "sales", "contact sales", "talk to sales", "connect to sales", "call sales", "speak to sales",
    "sales team", "sales executive", "sales person", "sales guy", "sales manager", "sales representative",
    "sales dept", "sales department", "talk to agent", "contact agent", "connect to agent",
    "speak to agent", "call agent", "talk to an agent", "agent details", "contact human",
    "talk to human", "connect to human", "call human", "speak to human", "human agent",
    "human support", "live agent", "live support", "customer care", "customer support",
    "support number", "support phone", "support contact", "customer executive", "customer representative",
    "సేల్స్ టీమ్ని సంప్రదించండి", "సేల్స్ ని సంప్రదించండి", "సేల్స్ టీమ్ ని సంప్రదించండి",
    "సేల్స్ సంప్రదించండి", "సేల్స్ టీమ్", "సంప్రదించండి", "సపోర్ట్", "ఏజెంట్‌తో మాట్లాడండి",
    "ఏజెంట్ తో మాట్లాడండి", "ఏజెంట్", "సేల్స్"
]

# Keywords in user messages that indicate the agent (Karunakar Reddy) needs to be
# notified — shared between check_and_notify_agent() and whatsapp_webhook().
USER_ESCALATION_KEYWORDS = [
    "connect", "talk", "speak", "call", "agent", "human", "representative", "expert",
    "team", "karunakar", "reddy", "notary", "letterhead", "stamped", "signed", "poa",
    "power of attorney", "resolution", "trademark", "document", "paperwork", "contract",
    "agreement", "office location", "address"
]


def extract_customer_details_with_ai(user_text):
    """
    Intelligently scans the incoming user text using Llama 3.1 to catch
    names and vehicle numbers. Returns a structured data dictionary.
    """
    try:
        ai_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

        extraction_prompt = (
            "Analyze the following user message sent to a vehicle tracking business. "
            "Extract ONLY the sender's own name and their truck or vehicle number if explicitly stated. "
            "IMPORTANT: Do NOT extract names of company staff, agents, or businesses (e.g. 'Karunakar Reddy', 'Fuel Tracks'). "
            "Only extract a name if the user is clearly introducing themselves (e.g. 'I am Ravi', 'My name is Suresh'). "
            "Respond ONLY with a raw JSON object with keys 'name' and 'truck_number'. "
            "If a value is not explicitly stated by the user about themselves, set it to null. "
            "Do not include markdown formatting or backticks.\n"
            f"Message: '{user_text}'"
        )

        completion = ai_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": extraction_prompt}],
            temperature=0.0,
        )

        content = completion.choices[0].message.content
        if not isinstance(content, str):
            return {"name": None, "truck_number": None}
        content = content.strip()
        # Attempt to isolate JSON substring to handle markdown fences or
        # conversational preambles/postscripts
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            content = content[start_idx:end_idx + 1]
        else:
            if content.startswith("```"):
                lines = content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()

        extracted_data = json.loads(content)
        return extracted_data
    except Exception as e:
        print(f"[WARNING] Details extraction skipped or failed: {e}")
        return {"name": None, "truck_number": None}


def get_ai_response(user_phone, new_user_message, customer=None):
    """
    Extracts past context history from logs and dynamically routes the conversation
    into the exact language engine matching the user's latest incoming message script.
    """
    try:
        test_text = new_user_message.strip()
        test_text_lower = test_text.lower()

        # 👤 STATIC NAME RESOLUTION LOGIC
        # Always use "Sir" instead of customer.owner_name to avoid addressing
        # users by their business name.
        display_name = "Sir"

        # 🌟 HIGH-PRIORITY OVERRIDE 1: Contact Card Hijack
        if has_keyword_match(test_text_lower, CONTACT_KEYWORDS):
            handoff_intro = (
                "Here are the official business contact details for our Technical Sales Expert, "
                "Mr. Karunakar Reddy! 📞\n\n"
                "You can save his corporate contact card directly to your phone below to call "
                "or message him at your convenience:"
            )
            # ✅ FIX 11: Save only once; send only once — no duplicate save/send in this branch
            msg_id = send_whatsapp_message(user_phone, handoff_intro)

            ChatMessage.objects.create(
                phone_number=user_phone,
                role='assistant',
                content=handoff_intro,
                message_id=msg_id)

            corporate_vcard = {
                "first_name": "Karunakar Reddy",
                "last_name": "(Fuel Tracks)",
                "formatted_name": "Mr. Karunakar Reddy",
                "company": "Fuel Tracks Technologies Pvt Ltd",
                "phone_number": "+919000666914"  # ✅ FIX 9: No spaces so wa_id replace is clean
            }
            send_whatsapp_message(
                to_phone=user_phone,
                text_content="",
                contact_data=corporate_vcard)

            # Notify the agent
            agent_alert = (
                f"🚨 Contact Card Request Alert!\n"
                f"Customer: {customer.owner_name if customer else 'Unknown'}\n"
                f"Phone: {user_phone}\n"
                f"Truck: {
                    customer.truck_number if (
                        customer and customer.truck_number) else 'Not provided'}\n"
                f"User Msg: '{new_user_message}'\n"
                f"Action: Sent contact card of Mr. Karunakar Reddy to customer."
            )
            send_whatsapp_message(AGENT_NOTIFY_PHONE, agent_alert)
            return None  # ✅ Caller must NOT call send_whatsapp_message again

        # 🌟 HIGH-PRIORITY OVERRIDE 2: Tenglish notification shortcut
        if "notifications pampisthaya" in test_text_lower or "alerts pampisthundhi" in test_text_lower:
            tenglish_reply = (
                f"{display_name} garu, mana smart fuel monitoring setup updates automatic fuel drop "
                "notifications direct ga pampisthundhi. Sensor 99% accuracy tho live alerts ni "
                "operators ki register chesthundhi."
            )
            ChatMessage.objects.create(
                phone_number=user_phone,
                role='assistant',
                content=tenglish_reply)
            return tenglish_reply

        # 🚀 LANGUAGE DETECTOR
        has_telugu_script = any(
            '\u0c00' <= char <= '\u0c7f' for char in test_text)

        tenglish_keywords = [
            "chepu", "cheppandi", "enti", "anti", "ela", "kavali", "unayi", "una", "undhi", "lo", "ki",
            "pampisthaya", "pampandi", "entha", "antha", "vundhi", "vunnayi", "kuda", "naku", "mana", "features",
            "chestunda", "pampisthundhi", "vaddhu", "avunu", "ledu", "panichayayi", "ledhu",
            "ventane", "akada", "ekada"
        ]
        has_tenglish_roots = any(
            keyword in test_text_lower for keyword in tenglish_keywords)

        # 🚫 SHARED OFF-TOPIC GUARD (injected into every engine below)
        offtopic_rule_english = (
            "STRICT SCOPE — HIGHEST PRIORITY RULE:\n"
            "- You represent ONLY Fuel Tracks Technologies. You are a sales assistant, NOT a general chatbot.\n"
            "- If the user sends anything unrelated to fleet management, GPS tracking, fuel monitoring, "
            "pricing, or Fuel Tracks products — such as personal chit-chat, jokes, poems, food, weather, "
            "sports, or any other off-topic content — you MUST politely decline and redirect.\n"
            "- CRITICAL: Product pricing inquiries, catalog/PDF requests, contact requests, official documentation/paperwork requests (e.g., POA, board resolution, notary letter, letterhead, signed/stamped copies), greetings, and gratitude (e.g. thanks, thank you) are strictly ON-TOPIC. Never decline or redirect them.\n"
            f"- Off-topic redirect (English): '{display_name} garu, I can only assist with Fuel Tracks "
            "Technologies products and services. Feel free to ask about our GPS trackers, fuel monitoring, "
            "smart cameras, borewell solutions, or other accessories!'\n"
            "- EXCEPTIONS: General greetings, thank you, thanks, and goodbye are NOT off-topic. Respond to greetings politely, and respond to thank you / thanks / goodbye by closing the conversation politely.\n"
            "- NEVER write poems, jokes, stories, or creative content under any circumstances.\n\n"
        )
        offtopic_rule_tenglish = (
            "STRICT SCOPE — HIGHEST PRIORITY RULE:\n"
            "- Meeru ONLY Fuel Tracks Technologies products mariyu services gurinchi matladali. "
            "Meeru general chatbot kaadu — sales assistant maatram.\n"
            "- User personal topics (bhojnam, jokes, kavitalu, weather, sports, etc.) adigithe "
            "maryādagā decline cheyandi mariyu business ki redirect cheyandi.\n"
            "- CRITICAL: Pricing queries, catalog/PDF requests, contact requests, official documentation/paperwork requests (e.g., POA, board resolution, notary letter, letterhead, signed/stamped copies), greetings, and thanks/dhanyavadalu are strictly ON-TOPIC. Never decline or redirect them.\n"
            f"- Off-topic redirect: '{display_name} garu, nenu Fuel Tracks Technologies products "
            "mariyu services ki maatrame help cheyagalanu. Meeru fleet, GPS tracking, fuel monitoring, "
            "cameras, borewell solutions, leda other accessories gurinchi adugavacchu!'\n"
            "- EXCEPTIONS: General greetings, thank you, thanks, dhanyavadalu, or goodbye are allowed. Polite ga respond cheyandi (e.g. hello or thank you/goodbye replies).\n"
            "- Poems, jokes, stories, creative content NEVER raayakandi.\n\n"
        )
        offtopic_rule_telugu = (
            "STRICT SCOPE — HIGHEST PRIORITY RULE:\n"
            "- మీరు ONLY Fuel Tracks Technologies products మరియు services గురించి మాట్లాడాలి.\n"
            "- వ్యక్తిగత విషయాలు (భోజనం, జోక్స్, కవితలు, వాతావరణం మొదలైనవి) అడిగితే "
            "మర్యాదగా తిరస్కరించండి మరియు వెంటనే business కి redirect చేయండి.\n"
            "- CRITICAL: ధర (pricing) అడిగినప్పుడు, క్యాటలాగ్/PDF అడిగినప్పుడు, కాంటాక్ట్ నంబర్ అడిగినప్పుడు, అధికారిక పత్రాల/కాగితాల అభ్యర్థనలు (ఉదాహరణకు: POA, బోర్డ్ రిజల్యూషన్, నోటరీ లేఖ, లెటర్ హెడ్, సంతకం/స్టాంప్ చేసిన పత్రాలు), నమస్కారాలు, మరియు థాంక్యూ/ధన్యవాదాలు చెప్పినప్పుడు అవి ON-TOPIC. వీటిని ఎప్పుడూ తిరస్కరించకండి.\n"
            f"- Off-topic అయినప్పుడు చెప్పండి: '{display_name} గారు, నేను Fuel Tracks Technologies "
            "products మరియు services కోసం మాత్రమే సహాయం చేయగలను. GPS tracking, fuel monitoring, "
            "కెమెరాలు, బోరుబావి సొల్యూషన్స్, లేదా ఇతర పరికరాల గురించి అడగవచ్చు!'\n"
            "- మినహాయింపులు: సాధారణ నమస్కారాలు (హాయ్, హలో, నమస్తే), కృతజ్ఞతలు (ధన్యవాదాలు, థాంక్యూ), లేదా సెలవు/బై చెప్పడం off-topic కావు. వాటికి మర్యాదగా సమాధానం చెప్పండి.\n"
            "- Poems, jokes, stories, creative content ఎప్పుడూ రాయకండి.\n\n"
        )
        paperwork_rule_english = (
            "CRITICAL PAPERWORK & ADMINISTRATIVE REQUEST GUARDRAIL:\n"
            "- NEVER make decisions, commitments, or promises regarding administrative requests, official documentation, company letterheads, signed/stamped copies, board resolutions, power of attorney (POA), notary letters, trademark applications, or timelines (e.g., 'within 24 hours').\n"
            "- Do NOT promise that you or the team will prepare or send any such files or documents.\n"
            "- If the user requests official documents, paperwork, letterhead copies, notary letters, or trademark/POA/resolution copies, state politely that as an AI assistant you cannot process or commit to document requests, but you have notified our Technical Sales Expert, Mr. Karunakar Reddy, to assist them with this. Provide Mr. Karunakar Reddy's contact details (+91 90006 66914) for direct follow-up.\n\n"
        )
        paperwork_rule_tenglish = (
            "CRITICAL PAPERWORK & ADMINISTRATIVE REQUEST GUARDRAIL:\n"
            "- Official documents, company letterhead, signed/stamped copies, board resolutions, POA, notary letters, or trademark applications gurinchi advance commitments leda promises cheyakandi.\n"
            "- Veeti gurinchi '24 hours lo pampistham' kani 'team prepare chesthundi' kani promises cheyakandi.\n"
            "- User document requests adigithe, polite ga cheppandi: 'Nenu AI assistant ni, official documents process/promise cheyalenu. Kani ma Technical Sales Expert, Mr. Karunakar Reddy gariki inform chesanu, aayana mimmalni contact chestharu.' Provide Mr. Karunakar Reddy's contact: +91 90006 66914.\n\n"
        )
        paperwork_rule_telugu = (
            "CRITICAL PAPERWORK & ADMINISTRATIVE REQUEST GUARDRAIL:\n"
            "- కంపెనీ లెటర్హెడ్, సంతకం/స్టాంప్ చేసిన పత్రాలు, బోర్డ్ రిజల్యూషన్ (board resolution), పవర్ ఆఫ్ అటార్నీ (POA), నోటరీ లేఖలు, ట్రేడ్మార్క్ మొదలైన అధికారిక పత్రాల గురించి ఎటువంటి వాగ్దానాలు లేదా గడువులు (ఉదాహరణకు: 24 గంటల్లో పంపుతాము) చెప్పకండి.\n"
            "- పత్రాల తయారీ లేదా పంపడం గురించి మీ అంతటగా హామీలు ఇవ్వకండి.\n"
            "- వినియోగదారు అధికారిక పత్రాలు అడిగినప్పుడు, మర్యాదగా చెప్పండి: 'నేను AI అసిస్టెంట్ ని మాత్రమే, అధికారిక పత్రాలను ప్రాసెస్ చేయలేను. కానీ మా టెక్నికల్ సేల్స్ ఎక్స్‌పర్ట్, మిస్టర్ కరుణాకర్ రెడ్డి గారికి ఈ విషయాన్ని తెలియజేశాను. వారు మిమ్మల్ని సంప్రదిస్తారు.' వారి నంబర్ +91 90006 66914 కూడా ఇవ్వండి.\n\n"
        )

        core_behavior_rules = (
            "CORE BEHAVIOR RULES (apply in every response, all languages):\n"
            "1. CONTEXT AWARENESS\n"
            "   Before deciding a message is \"out of scope,\" check the last 1-3 messages for context. Short follow-ups like \"price\", \"how much\", \"cost\", \"details\", \"features\", \"warranty\", \"specs\" almost always refer to the product just discussed — NOT a new topic. Never fire the scope-refusal on a follow-up about a product you already introduced in this conversation.\n"
            "2. PRICING QUESTIONS ARE ALWAYS IN SCOPE\n"
            "   - Never respond to a pricing question with the generic \"I can only assist with Fuel Tracks products\" refusal.\n"
            "   - If the user asks for the price, cost, or amount for the 'TG Mining AIS 140 GPS device' or 'AIS 140 tracker', state that the price is 5500 and it is negotiable.\n"
            "   - For any OTHER products, DO NOT provide numerical price estimations, ranges, or exact quotes yourself. Instead, politely inform the user that our Technical Sales Expert, Mr. Karunakar Reddy, handles all pricing and detailed quotes. Provide his contact number (+91 90006 66914) and say he will assist them directly.\n"
            "3. SCOPE REFUSAL — NARROW USE ONLY\n"
            "   Use the redirect message (\"Sir/Madam garu, I can only assist with Fuel Tracks Technologies products and services...\") ONLY for messages with no reasonable connection to any product or service offered (general chit-chat, unrelated companies/personal topics). NEVER send this exact message twice in a row. If the user repeats or rephrases their question after a refusal, that means you misunderstood them — change your approach, don't repeat the line.\n"
            "4. NEVER PAIR A REFUSAL WITH SENT MATERIAL\n"
            "   Do not send a catalog/PDF/document in the same turn as a scope refusal. Either answer the question (and share material if relevant) or redirect — never both in one response.\n"
            "5. HANDLING FRUSTRATION & ANGER\n"
            "   If the customer sounds irritated, angry, frustrated, or uses short/curt language, DO NOT repeat scripted robotic responses. Be empathetic, apologize briefly if needed, and IMMEDIATELY offer to connect them directly with Mr. Karunakar Reddy. Your primary goal is to ensure they feel heard, respected, and never annoyed by repetitive AI loops. Never send the identical message twice in a row under any circumstance.\n"
            "6. NAME PERSONALIZATION\n"
            "   Once the user has given their name, use it naturally. Do not ask for their name again if it's already known from the conversation.\n"
            "7. ESCALATION\n"
            "   If you fail to understand or resolve the same question twice in a row, stop repeating yourself. Instead, offer to connect the user with a human sales representative.\n"
            "8. WHATSAPP FORMATTING\n"
            "   Use a single asterisk for *bold text* instead of double asterisks (**bold**). Double asterisks do not render correctly in WhatsApp.\n\n"
        )

        # ENGINE 1: NATIVE TELUGU SCRIPT
        if has_telugu_script:
            display_name_telugu = "సర్" if display_name == "Sir" else display_name
            system_prompt = (
                "You are an expert corporate AI Sales Representative representing Fuel Tracks Technologies.\n"
                "Role Definition: You talk ON BEHALF of Fuel Tracks Technologies. You are the seller. "
                "The user chatting with you is the buyer/customer.\n\n"

                "STRICT LANGUAGE RULE:\n"
                "- The user is talking to you in Telugu Script. You MUST reply back entirely in clear, "
                "professional corporate Telugu script characters (తెలుగు లిపి).\n"
                "- Do NOT use the English/Latin alphabet characters or Tenglish words here.\n"
                f"- Always address the user strictly as '{display_name_telugu} గారు'.\n"
                "- CRITICAL: Ignore any previous language used in the chat history. You MUST respond strictly in Telugu script characters (తెలుగు లిపి) now.\n\n"

                "FUEL TRACKS OFFICIAL PRODUCT FACTS (TELUGU SCRIPT):\n"
                "- GPS Trackers: ఇవి ప్రభుత్వ ఆమోదం పొందిన లొకేషన్ ట్రాకర్లు (AIS 140 Certified Device). తెలంగాణ ప్రభుత్వ మైనింగ్ డిపార్ట్‌మెంట్ (Mining Department) ద్వారా ఆమోదించబడిన ఈ AIS 140 పరికరం మైనింగ్ వాహనాలకు (Mining Vehicles/Operations) ఇప్పుడు తప్పనిసరి (mandatory). మా వద్ద లభించే AIS 140 ట్రాకర్లు అత్యంత నాణ్యమైనవి, నమ్మకమైనవి మరియు బెస్ట్ ప్రైస్ గ్యారెంటీతో లభిస్తాయి. ఇందులో రియల్-టైమ్ ట్రాకింగ్, స్పీడ్ మానిటరింగ్, మరియు పానిక్ బటన్స్ ఉంటాయి. ఇతర మోడల్స్: Teltonika FMB120, Teltonika FMB910, మరియు 3G WCDMA GPS tracker (రిమోట్ ఇంజన్ కట్ మరియు IP67 వాటర్ ప్రూఫ్ కలిగి ఉంటుంది).\n"
                "- ⚠️ ప్రభుత్వ నోటీసు (GOVERNMENT NOTICE — మైనింగ్ AIS 140 గడువు): "
                "(1) అన్ని లీజు హోల్డర్లు & MDL హోల్డర్లు తమ వాహనాలను డిపార్ట్‌మెంట్‌లో నమోదు చేసి, జూన్ 25, 2026 నాటికి అన్ని మినరల్ క్యారియింగ్ వాహనాలకు AIS-140 ఇన్‌స్టాల్ చేయాలి. "
                "(2) అన్ని మినరల్ ట్రాన్స్‌పోర్టింగ్ వాహనాలకు 31.07.2026 లోపు ఎంపనెల్డ్ ఏజెన్సీలతో సంప్రదించి AIS-140 పరికరాన్ని ఫిక్స్ చేయాలి. "
                "(3) 01.08.2026 నుండి AIS-140 లేకుండా ట్రాన్సిట్ ఫారమ్స్/పాసెస్ జనరేట్ కావు. "
                "*గడువు దాటకముందే సంప్రదించండి — మిస్టర్ కరుణాకర్ రెడ్డి: +91 90006 66914 | సపోర్ట్: +91 73374 33350 / 51 / 56.*\n"
                "- Smart Fuel Monitoring: మా సిస్టమ్ 99% ఖచ్చితత్వంతో డిజిటల్ ఫ్యూయల్ రాడ్ సెన్సార్లను (Italon Fuel Sensor) మరియు Teltonika FMB920 ట్రాకర్లను "
                "ఉపయోగిస్తుంది. ఇది ఇంధన దొంగతనాన్ని గుర్తించి వెంటనే లైవ్ అలర్ట్లను పంపుతుంది.\n"
                "- Smart Security Cameras & Dash Cams: Solar Cam (100% సోలార్, 4G LTE), Wi-Fi Security Camera (1080P, టూ-వే ఆడియో, నైట్ విజన్, SD/క్లౌడ్ స్టోరేజ్), మరియు Dashcam DC 01 S (ముందు/వెనుక 2K రికార్డింగ్, G-సెన్సార్ ప్రొటెక్షన్).\n"
                "- Borewell Solutions: Bore Well Rod Count (రోడ్ టైమింగ్ కౌంటింగ్ డిజిటల్ సిస్టమ్) మరియు Bore Well RPM Count (RPM మెజర్మెంట్).\n"
                "- Accessories: AC Temperature Sensor for Truck (ఏసి టెంపరేచర్ మానిటరింగ్), Car LCD Monitor (4.3\" డిస్ప్లే), మరియు Relay Cutoff Switch (12V 40A రిమోట్ ఇంజన్/ఫ్యూయల్ పవర్ కట్).\n\n"

                "FUEL TRACKS OFFICIAL CONTACT INFO (TELUGU SCRIPT):\n"
                "- ఫోన్ నంబర్: +91 90006 66914, +91 73374 33350, +91 73374 33351, +91 73374 33356\n"
                "- ఈమెయిల్: info@fueltracks.in\n"
                "- వెబ్‌సైట్: www.fueltracks.in\n"
                "- ప్రధాన కార్యాలయం: Champapet, Hyderabad (ప్రెస్ కాలనీ, చంపాపేట్, హైదరాబాద్)\n\n"

                + offtopic_rule_telugu + paperwork_rule_telugu + core_behavior_rules +
                "CLOSING RULES:\n"
                "- యూజర్ సేల్స్ టీమ్‌ని సంప్రదించాలని లేదా డీల్స్/కోట్ కావాలని అడిగితే, మర్యాదగా ఈ విధంగా సమాధానం చెప్పండి: "
                "'హలో! మా సేల్స్ టీమ్‌తో మాట్లాడాలని కోరినందుకు ధన్యవాదాలు. మీరు నేరుగా మా టెక్నికల్ సేల్స్ ఎక్స్‌పర్ట్ మిస్టర్ కరుణాకర్ రెడ్డి (+91 90006 66914) కి లేదా మా సపోర్ట్ నంబర్లు: 73374 33350, 73374 33351, 73374 33356 లకు కాల్ చేయవచ్చు.'\n"
                f"- ఒకవేళ యూజర్ 'సరే', 'ధన్యవాదాలు', లేదా సెలవు చెబితే: "
                f"'ఫ్యూయల్ ట్రాక్స్ టెక్నాలజీస్‌ను సంప్రదించినందుకు ధన్యవాదాలు, {display_name_telugu} గారు. "
                "మీకు శుభదినం!'"
            )

        # ENGINE 2: TENGLISH
        elif has_tenglish_roots:
            system_prompt = (
                "You are an expert corporate AI Sales Representative representing Fuel Tracks Technologies.\n"
                "Role Definition: You talk ON BEHALF of Fuel Tracks Technologies. You are the seller. "
                "The user chatting with you is the buyer/customer.\n\n"

                "STRICT LANGUAGE RULE:\n"
                "- The user is talking to you in Tenglish. You MUST respond entirely in clean, natural, "
                "easy-to-read Tenglish text using ONLY the English/Latin alphabet characters.\n"
                "- NEVER use actual Telugu script characters (తెలుగు లిపి) under any circumstances.\n"
                f"- Always address the user strictly as '{display_name} garu'.\n"
                "- CRITICAL: Ignore any previous language used in the chat history. Translate and respond strictly in Tenglish now.\n\n"

                "FUEL TRACKS FACTS IN TENGLISH:\n"
                f"- GPS Trackers: {display_name} garu, mana trackers government certified (AIS 140 Certified Device). Government of Telangana Mining Department dwara approved aina ee AIS 140 device mining vehicles/operations ki mandatory. Ee device high quality, more reliable, mariyu best price guaranteed tho vastundi. Indulo real-time location tracking, speed monitoring, mariyu panic buttons untayi. Other models: Teltonika FMB120, Teltonika FMB910, mariyu 3G WCDMA GPS tracker (remote engine cutoff mariyu IP67 waterproof features tho).\n"
                f"- ⚠️ Government Notice (Mining AIS 140 Deadline): "
                f"(1) Anni lease holders & MDL holders June 25, 2026 nati ki tama vehicles ni department lo register chesi, anni mineral carrying vehicles ki AIS-140 install cheyyali. "
                f"(2) Anni mineral transporting vehicles ki 31.07.2026 nati ki empanelled agencies tho consult chesi AIS-140 device fix cheyyali. "
                f"(3) 01.08.2026 nundi AIS-140 fixing lekunte Transit Forms/Passes generate avvaavu. "
                f"*Deadline mundu contact cheyyandi — Mr. Karunakar Reddy: +91 90006 66914 | Support: +91 73374 33350 / 51 / 56.*\n"
                f"- Smart Fuel Monitoring: {display_name} garu, mana smart fuel monitoring system 99% accuracy provides chesthundhi. "
                "Indulo Italon Fuel Level Sensor mariyu Teltonika FMB920 trackers untayi. Sudden fuel level drops and theft automatic ga detect chesi alerts pampisthundhi.\n"
                f"- Smart Cameras & Dash Cams: Solar Cam (100% solar, 4G LTE), Wi-Fi Camera (1080P, night vision, two-way audio), mariyu Dashcam DC 01 S (front/rear 2K recording, loop recording, G-sensor protection).\n"
                f"- Borewell Solutions: Bore Well Rod Count (drill rod timings display device) mariyu Bore Well RPM Count (RPM drill speed display).\n"
                f"- Accessories: AC Temperature Sensor for Truck, Car LCD Monitor (4.3 inch screen), mariyu Relay Cutoff Switch (12V 40A remote power disconnection switch for fuel/ignition prevention).\n\n"

                "OFFICIAL CONTACT INFO IN TENGLISH:\n"
                "- Phone Support: +91 90006 66914, +91 73374 33350, +91 73374 33351, +91 73374 33356\n"
                "- Email: info@fueltracks.in\n"
                "- Website: www.fueltracks.in\n"
                "- Head office address: Press Colony, Champapet, Hyderabad\n\n"

                + offtopic_rule_tenglish + paperwork_rule_tenglish + core_behavior_rules +
                "CLOSING RULES:\n"
                f"- Deal quotes or fleet integrations adigithe: 'Hello! Sales team ni contact cheyalani korinanduku dhanyavadalu. Meeru direct ga mana Technical Sales Expert Mr. Karunakar Reddy (+91 90006 66914) leda mana support numbers: 73374 33350, 73374 33351, 73374 33356 ki call cheyavacchu.' ani cheppandi.\n"
                f"- If the user says 'ok', 'thank you', or goodbye, close: "
                f"'Fuel Tracks Technologies ni contact chesinanduku dhanyavadalu, {display_name} garu. "
                "Have a great day ahead!'"
            )

        # ENGINE 3: ENGLISH
        else:
            system_prompt = (
                "You are an expert corporate AI Sales Representative representing Fuel Tracks Technologies.\n"
                "Role Definition: You talk ON BEHALF of Fuel Tracks Technologies. You are the seller. "
                "The user chatting with you is the buyer/customer.\n\n"

                "STRICT LANGUAGE RULE:\n"
                "- The user is talking to you in English. You MUST reply entirely in clear, professional "
                "corporate English. Do NOT mix in Tenglish, Telugu, or local script characters.\n"
                f"- Address the user strictly as '{display_name} garu'.\n"
                "- CRITICAL: Ignore any previous language used in the chat history. You MUST respond strictly in English now.\n\n"

                "FUEL TRACKS OFFICIAL PRODUCT FACTS:\n"
                "- GPS Trackers: Government-approved trackers for commercial vehicles (AIS 140 Certified Devices). Officially approved by the Government of Telangana Mining Department, the AIS 140 device is now mandatory for all mining vehicles/operations in Telangana. Built for mining vehicles, it offers high quality, reliability, and the best price guaranteed, featuring real-time location, speed monitoring, and panic buttons. Other models: Teltonika FMB120, Teltonika FMB910, and 3G WCDMA GPS tracker with remote engine cutoff and IP67 waterproof casing.\n"
                "- ⚠️ GOVERNMENT NOTICE (Mining AIS 140 Deadline): "
                "(1) All Lease Holders & MDL Holders must register their vehicles with the department and install AIS-140 to all mineral carrying vehicles by June 25th, 2026. "
                "(2) All Mineral Transporting Vehicles must be fixed with AIS-140 equipment by 31.07.2026, duly consulting empanelled agencies. "
                "(3) From 01.08.2026, Transit Forms/Passes will NOT be generated without AIS-140 fixing. "
                "*Contact us before the deadline — Mr. Karunakar Reddy: +91 90006 66914 | Support: +91 73374 33350 / 51 / 56.*\n"
                "- Smart Fuel Monitoring: Uses Italon digital fuel rod sensors (99% accuracy) and Teltonika FMB920 trackers to track refilling, detect sudden fuel drops, and send live theft alerts to operators.\n"
                "- Smart Security Cameras & Dash Cams: Solar Cam (100% solar powered, 4G LTE connectivity, mobile app viewing), Wi-Fi Security Camera (1080P, night vision, motion alerts, two-way audio), and Dashcam DC 01 S (front & rear 2K recording, loop recording, G-sensor protection).\n"
                "- Borewell Solutions: Bore Well Rod Count (digital display for drilling rod timings) and Bore Well RPM Count (accurate drilling RPM measurement).\n"
                "- Accessories: AC Temperature Sensor for Truck, Car LCD Monitor (4.3\" TFT kit with reversing priority), and Relay Cutoff Switch (12V 40A remote engine/fuel system cutoff).\n\n"

                "FUEL TRACKS OFFICIAL CONTACT INFO:\n"
                "- Phone Support: +91 90006 66914, +91 73374 33350, +91 73374 33351, +91 73374 33356\n"
                "- Email: info@fueltracks.in\n"
                "- Website: www.fueltracks.in\n"
                "- Address: Press Colony, Champapet, Hyderabad, Telangana 500079\n\n"

                + offtopic_rule_english + paperwork_rule_english + core_behavior_rules +
                "CLOSING GUARDRAIL:\n"
                "- If the user requests to contact the sales team, respond with: "
                "'Hello! Thank you for requesting to contact our sales team. You can call our Technical Sales Expert, Mr. Karunakar Reddy at +91 90006 66914 or our support team at 73374 33350, 73374 33351, 73374 33356 directly.'\n\n"
                "- If the user says goodbye, 'bye', 'thank you', or 'thanks', close: "
                f"'Thank you for contacting Fuel Tracks Technologies, {display_name} garu. "
                "Have a great day ahead!'\n\n"

                "CONCISENESS: Keep responses clean, focused, and under 3 sentences."
            )

        # Inject ad referral context if applicable
        if customer and customer.referred_by:
            campaign = customer.referred_by
            ad_context = (
                f"\n\nCRITICAL CONTEXT: The customer arrived via the ad campaign: '{
                    campaign.campaign_name}'. "
                f"You MUST focus your conversation strictly and exclusively on the product/topic of this ad: {
                    campaign.custom_system_prompt}. "
                f"Do NOT offer, pitch, or discuss other company products (such as other camera types, GPS trackers, "
                f"or fuel sensors) unless the customer explicitly asks about them."
            )
            system_prompt += ad_context

        # Check if the customer recently received a broadcast template
        recent_broadcast = ChatMessage.objects.filter(
            phone_number=user_phone,
            role='assistant',
            content__startswith="[System Sent Broadcast:"
        ).order_by('-id').first()

        if recent_broadcast:
            content = recent_broadcast.content
            template_name = None
            if " - " in content:
                # Format: [System Sent Broadcast: template_name - desc]
                parts = content.replace(
                    "[System Sent Broadcast:", "").replace(
                    "]", "").strip().split(" - ")
                if parts:
                    template_name = parts[0].strip()
            else:
                # Fallback for older formats: [System Sent Broadcast: desc]
                template_name = content.replace(
                    "[System Sent Broadcast:", "").replace(
                    "]", "").strip()

            if template_name:
                from bot.models import WhatsAppTemplate
                template_obj = WhatsAppTemplate.objects.filter(
                    template_name=template_name).first()
                template_prompt = ""
                if template_obj and template_obj.custom_system_prompt:
                    template_prompt = template_obj.custom_system_prompt
                else:
                    DEFAULT_TEMPLATE_PROMPTS = {
                        "hello_world": "Focus on welcoming the user and introducing our GPS tracking and fuel monitoring systems.",
                        "gps_tracking_device": "Focus strictly on promoting and answering queries about our AIS 140 certified GPS tracking devices.",
                        "ais_140_gps_mining_device": "Focus strictly on our AIS 140 certified GPS tracking devices approved by the Government of Telangana Mining Department, which are now mandatory for mining vehicles in Telangana. Highlight their high quality, reliability, best price guaranteed, and suitability for mining operations.",
                        "fuel_alert": "Focus on addressing the fuel drop/theft alert, explaining how our fuel sensors work to detect theft and provide 99% accuracy.",
                        "fleet_update": "Focus on discussing fleet tracking updates and overall fleet optimization."
                    }
                    template_prompt = DEFAULT_TEMPLATE_PROMPTS.get(
                        template_name, "")

                if template_prompt:
                    template_context = (
                        f"\n\nCRITICAL CONTEXT: The customer recently received the broadcast template: '{template_name}'. "
                        f"You MUST strictly focus your conversation and response style on the product/topic of this template: {template_prompt}. "
                        f"Do NOT offer, pitch, or discuss other company products unless the customer explicitly asks about them."
                    )
                    system_prompt += template_context

        # Fetch history. To ensure stable sorting, we order by '-id' (newest
        # first).
        messages_payload = [{"role": "system", "content": system_prompt}]

        history = ChatMessage.objects.filter(
            phone_number=user_phone).order_by('-id')[:6]
        history_list = list(reversed(history))

        # To prevent user message duplication, check if the latest message in
        # history is the same user query
        if history_list and history_list[-1].role == 'user' and history_list[-1].content == new_user_message:
            # It's already in history; append all history entries
            for msg in history_list:
                messages_payload.append(
                    {"role": msg.role, "content": msg.content})
        else:
            # Not in history (or history is empty/different); append history,
            # then append the new message
            for msg in history_list:
                messages_payload.append(
                    {"role": msg.role, "content": msg.content})
            messages_payload.append(
                {"role": "user", "content": new_user_message})

        # Define and inject language reminder to prevent drift in LLM
        # generation
        if has_telugu_script:
            language_reminder = "[REMINDER: Respond STRICTLY in Telugu script characters (తెలుగు లిపి). Do NOT use English/Latin alphabet characters. Ignore history language.]"
        elif has_tenglish_roots:
            language_reminder = "[REMINDER: Respond STRICTLY in Tenglish (Telugu using ONLY English/Latin alphabet characters). Do NOT use Telugu script characters (తెలుగు లిపి) under any circumstances. Ignore history language.]"
        else:
            language_reminder = "[REMINDER: Respond STRICTLY in English. Do NOT use Telugu script or Tenglish. Ignore history language.]"

        for msg in reversed(messages_payload):
            if msg["role"] == "user":
                msg["content"] = f"{msg['content']}\n\n{language_reminder}"
                break

        ai_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        completion = ai_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages_payload,
            temperature=0.1,
        )

        ai_reply = completion.choices[0].message.content

        # Count how many times the assistant has asked for the name
        name_request_count = ChatMessage.objects.filter(
            phone_number=user_phone,
            role='assistant'
        ).filter(
            Q(content__icontains="your name") | Q(
                content__icontains="మీ పేరు తెలుసుకోవచ్చా")
        ).count()

        is_new_contact = (
            not customer or
            not customer.owner_name or
            customer.owner_name.strip().lower() in [
                "new fleet contact", "new fleet contact."]
        )
        if is_new_contact and name_request_count < 2:
            if has_telugu_script:
                name_suffix = "\n\nదయచేసి మీ పేరు తెలుసుకోవచ్చా?"
            else:
                name_suffix = "\n\nMay I know your name, please?"
            ai_reply = f"{ai_reply}{name_suffix}"

        return ai_reply

    except Exception as e:
        print(f"[ERROR] Error inside AI loop execution: {e}")
        return "Thank you for reaching out to Fuel Tracks Technologies Private Limited. How can we help you?"


def send_whatsapp_message(to_phone, text_content, buttons=None, document_url=None,
                          document_filename=None, location_data=None, list_data=None,
                          contact_data=None, phone_number_id=None, media_id=None, media_type="document"):
    """Dispatches payload structures cleanly to Meta Graph Servers."""
    to_phone = str(to_phone).replace("+", "")
    active_phone_number_id = phone_number_id or _phone_number_id_ctx.get() or PHONE_NUMBER_ID
    url = f"https://graph.facebook.com/v19.0/{active_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    if contact_data and isinstance(contact_data, dict):
        # ✅ FIX 9: Strip all non-digit chars for wa_id to safely handle any phone format
        raw_phone = contact_data.get("phone_number", "")
        wa_id = ''.join(filter(str.isdigit, raw_phone))
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "contacts",
            "contacts": [
                {
                    "name": {
                        "first_name": contact_data.get("first_name", ""),
                        "last_name": contact_data.get("last_name", ""),
                        "formatted_name": contact_data.get("formatted_name", "")
                    },
                    "org": {"company": contact_data.get("company", "")},
                    "phones": [{"phone": raw_phone, "type": "WORK", "wa_id": wa_id}]
                }
            ]
        }
    elif list_data and isinstance(list_data, dict):
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": text_content},
                "action": {
                    "button": list_data.get("button_text", "View Menu"),
                    "sections": list_data.get("sections", [])
                }
            }
        }
    elif location_data and isinstance(location_data, dict):
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "location",
            "location": {
                "latitude": location_data.get("latitude"),
                "longitude": location_data.get("longitude"),
                "name": location_data.get("name", "Fuel Tracks Office"),
                "address": location_data.get("address", "Office Location")
            }
        }
    elif media_id:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": media_type,
            media_type: {
                "id": media_id
            }
        }
        if document_filename and media_type == "document":
            payload["document"]["filename"] = document_filename
        if text_content:
            payload[media_type]["caption"] = text_content
    elif document_url:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "document",
            "document": {
                "link": document_url,
                "filename": document_filename if document_filename else "Fuel_Tracks_Catalog.pdf",
                "caption": text_content
            }
        }
    elif buttons and isinstance(buttons, list):
        buttons = buttons[:3]
        button_actions = [
            {"type": "reply", "reply": {"id": f"btn_id_{i}", "title": btn}}
            for i, btn in enumerate(buttons)
        ]
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text_content},
                "action": {"buttons": button_actions}
            }
        }
    else:
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
        if res.status_code in [200, 201]:
            resp_data = res.json()
            messages = resp_data.get("messages", [])
            if messages:
                return messages[0].get("id")
    except Exception as e:
        print(f"Failed to post outgoing message via Meta API: {e}")
    return None


def notify_agent_of_incoming_message(
        customer, user_phone, user_text, suppress_alert=False, is_button_reply=False):
    """
    Sends a WhatsApp notification to the agent when a customer messages the bot or replies to a template,
    and logs the notification event in AgentNotificationLog.
    """
    from django.conf import settings
    if getattr(settings, 'DISABLE_INCOMING_NOTIFICATIONS', False):
        return

    clean_user = ''.join(c for c in user_phone if c.isdigit())
    clean_agent = ''.join(c for c in AGENT_NOTIFY_PHONE if c.isdigit())
    if clean_user == clean_agent:
        return

    # Check if a log entry was created for this user within the last 15 minutes
    from django.utils import timezone
    from datetime import timedelta
    time_threshold = timezone.now() - timedelta(minutes=15)
    recent_log = AgentNotificationLog.objects.filter(
        phone_number=user_phone,
        created_at__gte=time_threshold
    ).first()

    # If a recent log exists, append the message content and update details if
    # needed
    if recent_log:
        try:
            if recent_log.message_content:
                recent_log.message_content = f"{
                    recent_log.message_content}\n{user_text}"
            else:
                recent_log.message_content = user_text

            # Check if this new message can be matched to a recent broadcast
            # template
            recent_assistant_msg = ChatMessage.objects.filter(
                phone_number=user_phone,
                role='assistant'
            ).order_by('-id').first()

            template_name = None
            if recent_assistant_msg and recent_assistant_msg.content.startswith(
                    "[System Sent Broadcast:"):
                content = recent_assistant_msg.content
                if " - " in content:
                    parts = content.replace(
                        "[System Sent Broadcast:", "").replace(
                        "]", "").strip().split(" - ")
                    if parts:
                        template_name = parts[0].strip()
                else:
                    template_name = content.replace(
                        "[System Sent Broadcast:", "").replace(
                        "]", "").strip()

            if template_name or is_button_reply:
                recent_log.is_template_reply = True
                if template_name:
                    recent_log.template_name = template_name

            recent_log.save()
            print(
                f"[INFO] Appended message from {user_phone} to existing AgentNotificationLog {
                    recent_log.id}.")
        except Exception as e:
            print(
                f"[ERROR] Failed to update existing AgentNotificationLog entry: {e}")
        return

    # Check if the customer recently received a broadcast template
    recent_assistant_msg = ChatMessage.objects.filter(
        phone_number=user_phone,
        role='assistant'
    ).order_by('-id').first()

    template_name = None
    if recent_assistant_msg and recent_assistant_msg.content.startswith(
            "[System Sent Broadcast:"):
        content = recent_assistant_msg.content
        if " - " in content:
            parts = content.replace(
                "[System Sent Broadcast:", "").replace(
                "]", "").strip().split(" - ")
            if parts:
                template_name = parts[0].strip()
        else:
            template_name = content.replace(
                "[System Sent Broadcast:", "").replace(
                "]", "").strip()

    is_template_reply = is_button_reply or (template_name is not None)

    if is_template_reply:
        agent_alert = (
            f"📥 Template Reply Alert!\n"
            f"Customer: {customer.owner_name if customer else 'Unknown'}\n"
            f"Phone: {user_phone}\n"
            f"Truck: {
                customer.truck_number if (
                    customer and customer.truck_number) else 'Not provided'}\n"
            f"Template: {template_name}\n"
            f"User Reply: '{user_text}'"
        )
    else:
        agent_alert = (
            f"💬 Customer Message Alert!\n"
            f"Customer: {customer.owner_name if customer else 'Unknown'}\n"
            f"Phone: {user_phone}\n"
            f"Truck: {
                customer.truck_number if (
                    customer and customer.truck_number) else 'Not provided'}\n"
            f"User Msg: '{user_text}'"
        )

    notification_sent = False
    if not suppress_alert:
        try:
            send_whatsapp_message(AGENT_NOTIFY_PHONE, agent_alert)
            notification_sent = True
        except Exception as e:
            print(
                f"[ERROR] Failed to send WhatsApp notification to agent: {e}")

    try:
        AgentNotificationLog.objects.create(
            customer=customer,
            phone_number=user_phone,
            message_content=user_text,
            is_template_reply=is_template_reply,
            template_name=template_name,
            notification_sent=notification_sent
        )
    except Exception as e:
        print(f"[ERROR] Failed to create AgentNotificationLog entry: {e}")


def check_and_notify_agent(customer, user_phone, user_text, bot_reply):
    """
    Checks if the user text or the bot reply indicates that the agent (Karunakar Reddy)
    needs to be notified or contact is requested, and sends the notification if so.
    """
    # Exclude notifications when the message is sent to/by the agent phone
    # itself
    clean_user = ''.join(c for c in user_phone if c.isdigit())
    clean_agent = ''.join(c for c in AGENT_NOTIFY_PHONE if c.isdigit())
    if clean_user == clean_agent:
        return

    # Prevent duplicate notifications for the same message content using cache
    cache_key = f"notified_agent_{user_phone}_{hash(user_text)}"
    if cache.get(cache_key):
        return

    user_text_lower = user_text.lower()
    bot_reply_lower = bot_reply.lower() if bot_reply else ""

    # Keywords/phrases in bot reply that imply escalation or notification
    bot_escalation_keywords = [
        "notified", "escalated", "will call", "will contact", "call you", "contact you",
        "reach out", "connect you", "representative", "expert", "reddy garu", "కరుణాకర్ రెడ్డి",
        "సంప్రదిస్తారు", "కాల్ చేస్తారు"
    ]

    should_notify = False
    reason = "User query related to escalation, contact, or official documentation."

    # Check user text keywords
    if any(kw in user_text_lower for kw in USER_ESCALATION_KEYWORDS):
        should_notify = True
    # Check if bot reply indicates escalation
    elif any(kw in bot_reply_lower for kw in bot_escalation_keywords):
        should_notify = True
        reason = "AI response indicated escalation/contact will occur."

    if should_notify:
        agent_alert = (
            f"🚨 Lead & Document Escalation Alert!\n"
            f"Customer: {customer.owner_name if customer else 'Unknown'}\n"
            f"Phone: {user_phone}\n"
            f"Truck: {
                customer.truck_number if (
                    customer and customer.truck_number) else 'Not provided'}\n"
            f"User Msg: '{user_text}'\n"
            f"Bot Reply: '{bot_reply[:150]}...'\n"
            f"Reason: {reason}"
        )
        send_whatsapp_message(AGENT_NOTIFY_PHONE, agent_alert)
        # cache for 10 minutes to avoid duplicates
        cache.set(cache_key, True, timeout=600)


@csrf_exempt
def whatsapp_webhook(request):
    """Processes verification GET queries and messaging POST actions from Meta."""
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("Verification Token Mismatch", status=403)

    elif request.method == "POST":
        # Webhook security: verify X-Hub-Signature-256 header if secret is
        # configured
        app_secret = os.getenv("WHATSAPP_APP_SECRET")
        if app_secret:
            signature = request.headers.get("X-Hub-Signature-256")
            if not signature:
                print("[WARNING] Webhook security warning: Missing signature header.")
                return HttpResponse("Missing signature", status=401)
            expected_sig = hmac.new(
                app_secret.encode('utf-8'),
                request.body,
                hashlib.sha256
            ).hexdigest()
            actual_sig = signature.split("=")[-1]
            if not hmac.compare_digest(actual_sig, expected_sig):
                print("[WARNING] Webhook security warning: Signature mismatch.")
                return HttpResponse("Signature mismatch", status=401)

        try:
            data = json.loads(request.body.decode('utf-8'))
            if "object" in data and data["object"] == "whatsapp_business_account":
                entry = data.get("entry", [{}])[0]
                changes = entry.get("changes", [{}])[0]
                value = changes.get("value", {})

                # Dynamically determine the recipient's phone number ID to
                # reply from it
                metadata = value.get("metadata", {})
                recipient_phone_number_id = metadata.get("phone_number_id")
                if recipient_phone_number_id:
                    _phone_number_id_ctx.set(recipient_phone_number_id)

                if "statuses" in value:
                    status_obj = value["statuses"][0]
                    msg_id = status_obj.get("id")
                    status_text = status_obj.get("status")
                    if msg_id and status_text:
                        ChatMessage.objects.filter(
                            message_id=msg_id).update(
                            status=status_text)
                    return JsonResponse({"status": "success"})

                if "messages" in value:
                    message_obj = value["messages"][0]
                    user_phone = str(message_obj["from"])

                    # Sanitize user_phone to always be formatted as 91...
                    clean_phone = ''.join(filter(str.isdigit, user_phone))
                    if len(clean_phone) == 10:
                        user_phone = '91' + clean_phone
                    elif len(clean_phone) == 11 and clean_phone.startswith('0'):
                        user_phone = '91' + clean_phone[1:]
                    else:
                        user_phone = clean_phone
                    domain_url = request.scheme + "://" + request.get_host()

                    # Deduplicate Meta webhook replays using Database (persists
                    # across container restarts/processes)
                    message_id = message_obj.get("id", "")
                    if message_id:
                        from bot.models import ProcessedMessage
                        if ProcessedMessage.objects.filter(
                                message_id=message_id).exists():
                            print(
                                f"[WARNING] Duplicate message_id {message_id} found in DB — skipping.")
                            return JsonResponse({"status": "success"})
                        try:
                            ProcessedMessage.objects.create(
                                message_id=message_id)
                        except Exception:
                            print(
                                f"[WARNING] Duplicate message_id {message_id} save failed — skipping.")
                            return JsonResponse({"status": "success"})

                        # Set in cache as a fast-lookup fallback
                        cache_key = f"wa_msg_id_{message_id}"
                        cache.set(cache_key, True, timeout=86400)

                    if message_obj.get("type") in [
                            "text", "interactive", "button"]:
                        if message_obj.get("type") == "text":
                            user_text = message_obj["text"].get("body", "")
                        elif message_obj.get("type") == "button":
                            user_text = message_obj.get(
                                "button", {}).get("text", "")
                            if not user_text and message_obj.get(
                                    "button", {}).get("payload"):
                                user_text = message_obj.get(
                                    "button", {}).get("payload", "")
                        else:
                            interactive_type = message_obj["interactive"].get(
                                "type", "")
                            if interactive_type == "button_reply":
                                user_text = message_obj["interactive"]["button_reply"].get(
                                    "title", "")
                            elif interactive_type == "list_reply":
                                user_text = message_obj["interactive"]["list_reply"].get(
                                    "title", "")
                            else:
                                user_text = ""
                    elif message_obj.get("type") in ["audio", "image", "video", "document"]:
                        media_type = message_obj.get("type")
                        user_text = f"[{media_type.capitalize()} Message Received]"
                    else:
                        user_text = ""

                    if not user_text.strip():
                        return JsonResponse({"status": "success"})

                    print(
                        f"[INCOMING] Received text/action: '{user_text}' from {user_phone}")
                    clean_text = user_text.strip().lower()

                    # Fallback for button reply text containing welcome message
                    # prefix (e.g. from copy-paste/forwarding)
                    lines = [
                        line.strip() for line in user_text.strip().split("\n") if line.strip()]
                    if lines:
                        last_line_clean = lines[-1].lower()
                        if last_line_clean in [
                                "products", "office location", "talk to an agent", "start", "stop"]:
                            clean_text = last_line_clean

                    # Initialize or fetch customer identity
                    customer, created = FleetCustomer.objects.get_or_create(
                        phone_number=user_phone,
                        defaults={
                            "owner_name": "New Fleet Contact",
                            "is_active": True}
                    )

                    # Opt-out compliance: if customer is inactive, ignore all
                    # unless "start"
                    if not created and not customer.is_active and clean_text != "start":
                        print(
                            f"[INACTIVE] Inactive customer {user_phone} ignored (except START).")
                        return JsonResponse({"status": "success"})

                    # Auto-unpause logic after 24 hours
                    if customer.is_bot_paused and customer.bot_paused_at:
                        from django.utils import timezone
                        from datetime import timedelta
                        if timezone.now() > customer.bot_paused_at + timedelta(hours=24):
                            customer.is_bot_paused = False
                            customer.bot_paused_at = None
                            customer.save()
                            print(f"[UNPAUSED] Auto-unpaused bot for {user_phone} after 24 hours.")

                    # Determine if we should suppress the generic agent alert
                    # (because a more specific alert will be sent later in the flow)
                    is_talk_to_agent = clean_text == "talk to an agent"
                    is_contact_req = has_keyword_match(
                        clean_text, CONTACT_KEYWORDS)
                    is_escalation = any(
                        kw in clean_text for kw in USER_ESCALATION_KEYWORDS)
                    suppress_generic_alert = is_talk_to_agent or is_contact_req or is_escalation

                    is_button_reply = message_obj.get(
                        "type") in ["button", "interactive"]

                    # Save incoming user message to ChatMessage early so it is guaranteed
                    # to be recorded in chat history regardless of downstream branching
                    user_msg_obj, msg_created = ChatMessage.objects.get_or_create(
                        phone_number=user_phone,
                        role='user',
                        content=user_text,
                        message_id=message_id
                    )

                    # Notify agent of customer message or template reply
                    notify_agent_of_incoming_message(
                        customer,
                        user_phone,
                        user_text,
                        suppress_alert=suppress_generic_alert,
                        is_button_reply=is_button_reply
                    )

                    # Check for Meta Facebook Ad Referral payload
                    referral_data = message_obj.get("referral")
                    if referral_data:
                        ad_id = referral_data.get("source_id")
                        headline = referral_data.get("headline", "")
                        body = referral_data.get("body", "")
                        print(
                            f"[REFERRAL] Ad Referral detected: Ad ID={ad_id}, Headline='{headline}', Body='{body}'")

                        matched_campaign = None

                        # 1. Match by Ad ID
                        if ad_id:
                            matched_campaign = AdCampaign.objects.filter(
                                ad_id=ad_id, is_active=True).first()

                        # 2. Match by Headline Keywords
                        if not matched_campaign and (headline or body):
                            headline_lower = headline.lower() if headline else ""
                            body_lower = body.lower() if body else ""
                            for campaign in AdCampaign.objects.filter(
                                    is_active=True):
                                if campaign.headline_keywords:
                                    keywords = [
                                        kw.strip().lower() for kw in campaign.headline_keywords.split(",") if kw.strip()]
                                    if any(
                                            kw in headline_lower or kw in body_lower for kw in keywords):
                                        matched_campaign = campaign
                                        break

                        if matched_campaign:
                            print(
                                f"[REFERRAL] Matched customer {user_phone} to campaign '{
                                    matched_campaign.campaign_name}'")
                            customer.referred_by = matched_campaign
                            customer.save()

                            # Send custom welcome message or catalog file if
                            # configured
                            if matched_campaign.welcome_message or matched_campaign.catalog_file:
                                # Send and save custom welcome message
                                if matched_campaign.welcome_message:
                                    welcome_reply = matched_campaign.welcome_message
                                    msg_id = send_whatsapp_message(
                                        user_phone, welcome_reply)

                                    ChatMessage.objects.create(
                                        phone_number=user_phone,
                                        role='assistant',
                                        content=welcome_reply,
                                        message_id=msg_id)

                                # If a catalog file is associated, send it
                                # automatically
                                if matched_campaign.catalog_file:
                                    catalog_name = matched_campaign.catalog_file
                                    catalog_msg = CATALOG_METADATA.get(catalog_name, {}).get(
                                        "en", "Here is our product catalog:")
                                    msg_id = send_whatsapp_message(
                                        to_phone=user_phone,
                                        text_content=catalog_msg,
                                        document_url=f"{domain_url}/api/catalog/{catalog_name}",
                                        document_filename=catalog_name
                                    )
                                    ChatMessage.objects.create(
                                        phone_number=user_phone,
                                        role='assistant',
                                        content=f"{catalog_msg} (Sent {catalog_name})",
                                        message_id=msg_id
                                    )
                                return JsonResponse({"status": "success"})

                    # If human agent paused the bot, just log message and return
                    if customer.is_bot_paused:
                        print(
                            f"[PAUSED] Bot is paused for {user_phone}. Ignored automatic processing.")
                        return JsonResponse({"status": "success"})

                    # 🌟 INTERCEPTION: Native Map Pin Routing
                    location_triggers = [
                        "office location", "లొకేషన్", "మ్యాప్", "map", "address",
                        "చిరునామా", "location pamp"
                    ]
                    device_triggers = ["tracker", "ట్రాకర్",
                                       "gps", "జిపిఎస్", "device", "పరికరం"]
                    is_device_query = has_keyword_match(
                        clean_text, device_triggers)

                    # Determine if this message is a simple greeting
                    is_greeting = is_simple_greeting(clean_text)

                    # Determine if we should handle the name collection flow
                    asked_for_name = False
                    is_new_unreferred_contact = (
                        customer.owner_name == "New Fleet Contact" and
                        not customer.referred_by
                    )

                    has_history = ChatMessage.objects.filter(
                        phone_number=user_phone).exists()

                    if is_new_unreferred_contact:
                        history = ChatMessage.objects.filter(
                            phone_number=user_phone, role='assistant').order_by('-id')
                        if history.exists():
                            for msg in history[:2]:
                                if "May I know your name" in msg.content or "tell me your name" in msg.content:
                                    asked_for_name = True
                                    break

                    # Count how many times the assistant has asked for the name
                    name_request_count = ChatMessage.objects.filter(
                        phone_number=user_phone,
                        role='assistant'
                    ).filter(
                        Q(content__icontains="your name") | Q(
                            content__icontains="మీ పేరు తెలుసుకోవచ్చా")
                    ).count()

                    is_contact_request = (
                        has_keyword_match(clean_text, CONTACT_KEYWORDS) or
                        any(w in clean_text for w in ["సేల్స్", "sales", "సంప్రదించండి", "కరుణాకర్", "సపోర్ట్"])
                    )
                    handle_name_flow = (
                        is_new_unreferred_contact and
                        (asked_for_name or is_greeting) and
                        not is_contact_request and
                        name_request_count < 2
                    )

                    if clean_text == "stop":
                        customer.is_active = False
                        customer.save()
                        opt_out_reply = (
                            "You have successfully unsubscribed from Fuel Tracks automated alerts. "
                            "Reply 'START' to resubscribe."
                        )
                        msg_id = send_whatsapp_message(
                            user_phone, opt_out_reply)

                        ChatMessage.objects.create(
                            phone_number=user_phone,
                            role='assistant',
                            content=opt_out_reply,
                            message_id=msg_id)
                        return JsonResponse({"status": "success"})

                    elif clean_text == "start":
                        customer.is_active = True
                        customer.save()
                        opt_in_reply = (
                            "Welcome back! Automated tracking alerts have been reactivated for your number."
                        )
                        msg_id = send_whatsapp_message(
                            user_phone, opt_in_reply)

                        ChatMessage.objects.create(
                            phone_number=user_phone,
                            role='assistant',
                            content=opt_in_reply,
                            message_id=msg_id)
                        return JsonResponse({"status": "success"})

                    elif has_keyword_match(clean_text, location_triggers) and not is_device_query:
                        location_intro = "Locating the Fuel Tracks Technologies head office branch... 📍"
                        office_coordinates = {
                            "latitude": 17.3486,
                            "longitude": 78.5214,
                            "name": "Fuel Tracks Technologies Pvt Ltd",
                            "address": "Press Colony, Champapet, Hyderabad, Telangana 500079"
                        }
                        send_whatsapp_message(user_phone, location_intro)
                        ChatMessage.objects.create(
                            phone_number=user_phone,
                            role='assistant',
                            content=location_intro)
                        send_whatsapp_message(
                            to_phone=user_phone, text_content="",
                            location_data=office_coordinates
                        )
                        ChatMessage.objects.create(
                            phone_number=user_phone, role='assistant',
                            content=f"Dispatched map pin: {office_coordinates['address']}"
                        )
                        return JsonResponse({"status": "success"})

                    elif clean_text == "products":
                        catalog_text = "Here is our official Fuel Tracks Product Catalog Guide! 📄"
                        ChatMessage.objects.create(
                            phone_number=user_phone, role='assistant', content=catalog_text)
                        send_whatsapp_message(
                            user_phone, catalog_text,
                            document_url=f"{domain_url}/api/catalog/Fuel_Tracks_Catalog.pdf",
                            document_filename="Fuel_Tracks_Catalog.pdf"
                        )
                        return JsonResponse({"status": "success"})

                    elif clean_text == "talk to an agent":
                        agent_text = (
                            "Our Expert, Mr. Karunakar Reddy, has been notified of your request! 📞 "
                            "He will call or message you shortly.\n\n"
                            "Direct Contact Numbers:\n"
                            "👤 *Mr. Karunakar Reddy (Technical Sales):* +91 90006 66914\n"
                            "📞 *Support Team:* +91 73374 33350 | +91 73374 33351 | +91 73374 33356"
                        )
                        msg_id = send_whatsapp_message(user_phone, agent_text)

                        ChatMessage.objects.create(
                            phone_number=user_phone,
                            role='assistant',
                            content=agent_text,
                            message_id=msg_id)

                        # Notify the agent
                        agent_alert = (
                            f"🚨 New Lead Alert!\n"
                            f"Customer: {customer.owner_name}\n"
                            f"Phone: {user_phone}\n"
                            f"Truck: {
                                customer.truck_number or 'Not provided'}\n"
                            f"Requested: Talk to an Agent"
                        )
                        send_whatsapp_message(AGENT_NOTIFY_PHONE, agent_alert)
                        return JsonResponse({"status": "success"})

                    elif is_contact_request:
                        # Customer clicked "Contact Sales" button or typed a
                        # sales/contact keyword — respond with direct contact info
                        # and language-aware message, then alert the agent.
                        has_telugu_script_contact = any(
                            '\u0c00' <= char <= '\u0c7f' for char in user_text)
                        has_tenglish_contact = any(
                            word in user_text.lower() for word in [
                                "garu", "meeru", "maa", "cheyandi", "cheyyandi",
                                "ayindi", "vastundi", "cheppandi", "matladali"])

                        cust_name = customer.owner_name if customer and customer.owner_name else ""
                        is_unknown = not cust_name or cust_name.strip().lower() in [
                            "new fleet contact", "new fleet contact."]
                        name_part_te = f"{cust_name} గారు, " if not is_unknown else ""
                        name_part_en = f"{cust_name} garu, " if not is_unknown else ""

                        if has_telugu_script_contact:
                            contact_reply = (
                                f"{name_part_te}మీరు మా సేల్స్ టీమ్‌ని సంప్రదించాలనుకున్నందుకు ధన్యవాదాలు! 🙏\n\n"
                                f"మా టెక్నికల్ సేల్స్ ఎక్స్‌పర్ట్ *మిస్టర్ కరుణాకర్ రెడ్డి* గారికి మీ అభ్యర్థన తెలియజేశాం. "
                                f"వారు త్వరలోనే మీకు కాల్ చేస్తారు. 📞\n\n"
                                f"మీరు నేరుగా సంప్రదించగల నంబర్లు:\n"
                                f"👤 *మిస్టర్ కరుణాకర్ రెడ్డి (టెక్నికల్ సేల్స్):* +91 90006 66914\n"
                                f"📞 *సపోర్ట్ టీమ్ నంబర్లు:* +91 73374 33350 | +91 73374 33351 | +91 73374 33356"
                            )
                        elif has_tenglish_contact:
                            contact_reply = (
                                f"{name_part_en}maa sales team ni contact cheyalani korinanduku dhanyavadalu! 🙏\n\n"
                                f"Maa Technical Sales Expert *Mr. Karunakar Reddy* garu ki meeru request chesaru. "
                                f"Varu twaralone meeru ki call chestaru. 📞\n\n"
                                f"Meeru direct ga contact cheyavacchu:\n"
                                f"👤 *Mr. Karunakar Reddy (Technical Sales):* +91 90006 66914\n"
                                f"📞 *Support Team Numbers:* +91 73374 33350 | +91 73374 33351 | +91 73374 33356"
                            )
                        else:
                            contact_reply = (
                                f"{name_part_en}Thank you for reaching out to our Sales Team! 🙏\n\n"
                                f"We have notified our Technical Sales Expert, *Mr. Karunakar Reddy*, "
                                f"of your request. He will call or message you shortly. 📞\n\n"
                                f"You can also contact us directly:\n"
                                f"👤 *Mr. Karunakar Reddy (Technical Sales):* +91 90006 66914\n"
                                f"📞 *Support Team Numbers:* +91 73374 33350 | +91 73374 33351 | +91 73374 33356"
                            )

                        msg_id = send_whatsapp_message(user_phone, contact_reply)
                        ChatMessage.objects.create(
                            phone_number=user_phone,
                            role='assistant',
                            content=contact_reply,
                            message_id=msg_id)

                        # Notify the agent immediately
                        agent_alert = (
                            f"🚨 Sales Contact Request!\n"
                            f"Customer: {customer.owner_name if customer else 'Unknown'}\n"
                            f"Phone: {user_phone}\n"
                            f"Truck: {customer.truck_number if customer and customer.truck_number else 'Not provided'}\n"
                            f"Button/Text: '{user_text}'"
                        )
                        send_whatsapp_message(AGENT_NOTIFY_PHONE, agent_alert)
                        return JsonResponse({"status": "success"})

                        if not asked_for_name:
                            professional_welcome = (
                                "Welcome to Fuel Tracks Technologies Private Limited!\n\n"
                                "We are India's trusted provider of high-end GPS Tracking Systems, "
                                "AIS 140 Certified Devices, and Smart Fuel Monitoring Solutions "
                                "designed to eliminate fuel theft and optimize fleet operations.\n\n"
                                "🌐 Website: www.fueltracks.in\n"
                                "📞 Support: +91 90006 66914, +91 73374 33350, +91 73374 33351, +91 73374 33356\n\n"
                                "How can we help your business today? Select an option below:"
                            )
                            ChatMessage.objects.create(
                                phone_number=user_phone, role='assistant', content=professional_welcome)
                            send_whatsapp_message(
                                user_phone, professional_welcome,
                                buttons=[
                                    "Office Location", "Products", "Talk to an Agent"]
                            )

                            name_request = "May I know your name, please?"
                            msg_id = send_whatsapp_message(
                                user_phone, name_request)

                            ChatMessage.objects.create(
                                phone_number=user_phone,
                                role='assistant',
                                content=name_request,
                                message_id=msg_id)
                            return JsonResponse({"status": "success"})
                        else:
                            name_reply = user_text.strip()
                            extracted_details = extract_customer_details_with_ai(
                                name_reply)
                            extracted_name = extracted_details.get("name")

                            if not extracted_name:
                                words = name_reply.split()
                                if len(words) <= 2 and all(w.isalpha()
                                                           for w in words):
                                    extracted_name = name_reply.title()

                            blocked_names = {
                                "karunakar reddy", "mr. karunakar reddy", "karunakar",
                                "fuel tracks", "fuel tracks technologies",
                                "new fleet contact", "sir/madam"
                            }

                            if extracted_name and extracted_name.lower() not in blocked_names:
                                customer.owner_name = extracted_name
                                customer.save()

                                # Send friendly confirmation
                                welcome_text = f"Thank you, {extracted_name} garu! How can I assist you with GPS tracking or fuel monitoring today?"
                                msg_id = send_whatsapp_message(
                                    user_phone, welcome_text)

                                ChatMessage.objects.create(
                                    phone_number=user_phone,
                                    role='assistant',
                                    content=welcome_text,
                                    message_id=msg_id)
                                return JsonResponse({"status": "success"})
                            else:
                                retry_request = "Could you please tell me your name so I know how to address you?"
                                msg_id = send_whatsapp_message(
                                    user_phone, retry_request)

                                ChatMessage.objects.create(
                                    phone_number=user_phone,
                                    role='assistant',
                                    content=retry_request,
                                    message_id=msg_id)
                                return JsonResponse({"status": "success"})

                    else:
                        # Defer Details Extraction: Only runs for queries going
                        # to the AI engine
                        needs_name = (
                            not customer.owner_name or
                            customer.owner_name.strip().lower() == "new fleet contact"
                        )
                        needs_truck = not customer.truck_number

                        if needs_name or needs_truck:
                            extracted_details = extract_customer_details_with_ai(
                                user_text)
                            blocked_names = {
                                "karunakar reddy", "mr. karunakar reddy", "karunakar",
                                "fuel tracks", "fuel tracks technologies",
                                "new fleet contact", "sir/madam"
                            }
                            updated = False
                            extracted_name = extracted_details.get("name")
                            if (needs_name and extracted_name and
                                    extracted_name.strip().lower() not in blocked_names):
                                customer.owner_name = extracted_name
                                updated = True
                            if needs_truck and extracted_details.get(
                                    "truck_number"):
                                customer.truck_number = extracted_details["truck_number"].upper(
                                )
                                updated = True
                            if updated:
                                customer.save()

                        # Process message through AI engine
                        bot_reply = get_ai_response(
                            user_phone, user_text, customer)
                        if bot_reply is not None:
                            msg_id = send_whatsapp_message(
                                user_phone, bot_reply)
                            ChatMessage.objects.create(
                                phone_number=user_phone,
                                role='assistant',
                                content=bot_reply,
                                message_id=msg_id)
                            check_and_notify_agent(
                                customer, user_phone, user_text, bot_reply)

                            # Specific device catalog sending logic
                            has_telugu_script = any(
                                '\u0c00' <= char <= '\u0c7f' for char in clean_text)

                            # Fetch recent messages in chat history (newest
                            # first) to enable history-based catalog lookup
                            recent_chat_history = ChatMessage.objects.filter(
                                phone_number=user_phone).order_by('-id')[:10]
                            history_texts = [
                                msg.content for msg in recent_chat_history]

                            matched_pdf, _ = find_device_catalog_match(
                                clean_text, history_texts)

                            if matched_pdf and matched_pdf in CATALOG_METADATA:
                                catalog_msg = CATALOG_METADATA[matched_pdf][
                                    "te"] if has_telugu_script else CATALOG_METADATA[matched_pdf]["en"]

                                msg_id = send_whatsapp_message(
                                    to_phone=user_phone,
                                    text_content=catalog_msg,
                                    document_url=f"{domain_url}/api/catalog/{matched_pdf}",
                                    document_filename=matched_pdf
                                )
                                ChatMessage.objects.create(
                                    phone_number=user_phone,
                                    role='assistant',
                                    content=f"{catalog_msg} (Sent {matched_pdf})",
                                    message_id=msg_id
                                )
        except Exception as e:
            print(f"Error inside primary webhook context loop: {e}")

    return JsonResponse({"status": "success"})


def export_customers_excel(request):
    """
    Exports all active/registered FleetCustomer records as an Excel-compatible CSV file.
    Includes UTF-8 BOM so Excel opens it with proper encoding for Indian names/characters.
    """
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="customers.csv"'

    # Write UTF-8 BOM first for Excel compatibility
    response.write('\ufeff')

    writer = csv.writer(response)
    # Header row
    writer.writerow(['Phone Number', 'Customer Name',
                    'Truck Number', 'Is Active', 'Date Created'])

    customers = FleetCustomer.objects.all().order_by('-created_at')
    for customer in customers:
        writer.writerow([
            f'="{customer.phone_number}"',
            customer.owner_name or '',
            customer.truck_number or '',
            'Yes' if customer.is_active else 'No',
            customer.created_at.strftime(
                '%Y-%m-%d %H:%M') if customer.created_at else ''
        ])

    return response


def serve_catalog(request, filename):
    """
    Serves the requested PDF catalog file from the media directory.
    """
    if not re.match(r'^[a-zA-Z0-9_\-\.]+\.pdf$', filename):
        raise Http404("Invalid catalog filename")

    from django.conf import settings
    catalog_path = os.path.join(settings.BASE_DIR, 'media', filename)
    if os.path.exists(catalog_path):
        return FileResponse(open(catalog_path, 'rb'),
                            content_type='application/pdf')
    else:
        raise Http404("Catalog not found")
