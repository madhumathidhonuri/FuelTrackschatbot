import os
import re
import json
import hmac
import csv
import hashlib
import requests
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from dotenv import load_dotenv
from groq import Groq
from .models import ChatMessage, FleetCustomer, AdCampaign

load_dotenv()

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

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# 🌟 CONFIGURATION PARAMETER
AGENT_NOTIFY_PHONE = "+919000666914"  # Include your full country code (e.g., +91...)


def has_keyword_match(text, keywords):
    """
    Checks if any of the keywords match in the text, ensuring word boundaries.
    """
    for kw in keywords:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def find_device_catalog_match(text, history_messages=None):
    """
    Scans the text (and optionally history) to find which device catalog to send.
    Returns a tuple: (catalog_filename, catalog_name) or (None, None)
    """
    clean_text = text.strip().lower()
    
    wifi_camera_keywords = ["wifi camera", "wifi cam", "wi-fi camera", "వైఫై కెమెరా", "wifi security camera"]
    solar_cam_keywords = ["solar cam", "solar camera", "సోలార్ కెమెరా", "solar security camera", "solar 4g cam"]
    dash_cam_keywords = ["dashcam", "dash cam", "dash camera", "డ్యాష్‌కామ్", "dashcam dc 01 s", "dc 01 s", "dc01s"]
    ptz_camera_keywords = ["ptz camera", "ptz security", "ptz కెమెరా", "ptz cam"]
    borewell_rod_keywords = ["rod count", "rod counter", "borewell rod", "రోడ్ కౌంట్"]
    borewell_rpm_keywords = ["rpm count", "rpm counter", "borewell rpm", "rpm కౌంట్"]
    ac_sensor_keywords = ["ac sensor", "ac temperature sensor", "temperature sensor", "టెంపరేచర్ సెన్సార్", "ac temperature"]
    lcd_monitor_keywords = ["lcd monitor", "car lcd", "monitor screen", "మోనిటర్"]
    relay_switch_keywords = ["relay", "cutoff switch", "relay cutoff", "cutoff", "రిలే"]
    
    ais_keywords = [
        "ais 140", "ais140", "gps", "tracker", "trackers", "ట్రాకర్", "ట్రాకర్లు", "జిపిఎస్",
        "fmb120", "fmb 120", "fmb910", "fmb 910", "teltonika fmb120", "teltonika fmb910", "teltonika"
    ]
    fuel_keywords = [
        "fuel", "sensor", "sensors", "rod", "theft", "monitoring", "ఫ్యూయల్", "ఇంధన", "సెన్సార్",
        "fmb920", "fmb 920", "italon", "teltonika fmb920"
    ]
    product_keywords = ["product", "products", "catalog", "catalogs", "కేటలాగ్", "ఉత్పత్తులు", "catalogue", "catalogues"]

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
    if has_keyword_match(clean_text, generic_catalog_request_keywords) and history_messages:
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

        content = completion.choices[0].message.content.strip()
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

        # 👤 DYNAMIC NAME RESOLUTION LOGIC
        invalid_names = {
            "new fleet contact", "naku", "nak", "naku oka", "nak oka", "sir/madam",
            "karunakar reddy", "mr. karunakar reddy", "karunakar", "reddy",
            "fuel tracks", "fuel tracks technologies"
        }
        if (customer and customer.owner_name and
                customer.owner_name.strip().lower() not in invalid_names):
            display_name = customer.owner_name.strip()
        else:
            display_name = "Sir"

        # 🌟 HIGH-PRIORITY OVERRIDE 1: Contact Card Hijack
        contact_keywords = [
            "give his number", "his phone number", "contact number", "give number",
            "number of the human", "number send", "number bodybuilding", "number ivvu",
            "number pampandi", "ph no", "phone no", "mobile number", "contact details",
            "phone number", "mobile", "whatsapp number", "karunakar number", "karunakar phone",
            "his number", "his contact", "agent number", "agent phone", "agent contact",
            "reddy number", "reddy phone", "provide phone number", "send phone number",
            "give phone number", "how can i contact", "how to contact", "how can we contact",
            "contact you", "contact us", "how to reach", "how can i reach"
        ]
        if has_keyword_match(test_text_lower, contact_keywords):
            handoff_intro = (
                "Here are the official business contact details for our Technical Sales Expert, "
                "Mr. Karunakar Reddy! 📞\n\n"
                "You can save his corporate contact card directly to your phone below to call "
                "or message him at your convenience:"
            )
            # ✅ FIX 11: Save only once; send only once — no duplicate save/send in this branch
            ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=handoff_intro)
            send_whatsapp_message(user_phone, handoff_intro)

            corporate_vcard = {
                "first_name": "Karunakar Reddy",
                "last_name": "(Fuel Tracks)",
                "formatted_name": "Mr. Karunakar Reddy",
                "company": "Fuel Tracks Technologies Pvt Ltd",
                "phone_number": "+919000666914"  # ✅ FIX 9: No spaces so wa_id replace is clean
            }
            send_whatsapp_message(to_phone=user_phone, text_content="", contact_data=corporate_vcard)
            return None  # ✅ Caller must NOT call send_whatsapp_message again

        # 🌟 HIGH-PRIORITY OVERRIDE 2: Tenglish notification shortcut
        if "notifications pampisthaya" in test_text_lower or "alerts pampisthundhi" in test_text_lower:
            tenglish_reply = (
                f"{display_name} garu, mana smart fuel monitoring setup updates automatic fuel drop "
                "notifications direct ga pampisthundhi. Sensor 99% accuracy tho live alerts ni "
                "operators ki register chesthundhi."
            )
            ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=tenglish_reply)
            return tenglish_reply

        # 🚀 LANGUAGE DETECTOR
        has_telugu_script = any('\u0c00' <= char <= '\u0c7f' for char in test_text)

        tenglish_keywords = [
            "chepu", "cheppandi", "enti", "anti", "ela", "kavali", "unayi", "una", "undhi", "lo", "ki",
            "pampisthaya", "pampandi", "entha", "vundhi", "vunnayi", "kuda", "naku", "mana", "features",
            "chestunda", "pampisthundhi", "vaddhu", "avunu", "ledu", "panichayayi", "ledhu",
            "ventane", "akada", "ekada"
        ]
        has_tenglish_roots = any(keyword in test_text_lower for keyword in tenglish_keywords)

        # 🚫 SHARED OFF-TOPIC GUARD (injected into every engine below)
        offtopic_rule_english = (
            "STRICT SCOPE — HIGHEST PRIORITY RULE:\n"
            "- You represent ONLY Fuel Tracks Technologies. You are a sales assistant, NOT a general chatbot.\n"
            "- If the user sends anything unrelated to fleet management, GPS tracking, fuel monitoring, "
            "pricing, or Fuel Tracks products — such as personal chit-chat, jokes, poems, food, weather, "
            "sports, or any other off-topic content — you MUST politely decline and redirect.\n"
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
            f"- Off-topic అయినప్పుడు చెప్పండి: '{display_name} గారు, నేను Fuel Tracks Technologies "
            "products మరియు services కోసం మాత్రమే సహాయం చేయగలను. GPS tracking, fuel monitoring, "
            "కెమెరాలు, బోరుబావి సొల్యూషన్స్, లేదా ఇతర పరికరాల గురించి అడగవచ్చు!'\n"
            "- మినహాయింపులు: సాధారణ నమస్కారాలు (హాయ్, హలో, నమస్తే), కృతజ్ఞతలు (ధన్యవాదాలు, థాంక్యూ), లేదా సెలవు/బై చెప్పడం off-topic కావు. వాటికి మర్యాదగా సమాధానం చెప్పండి.\n"
            "- Poems, jokes, stories, creative content ఎప్పుడూ రాయకండి.\n\n"
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
                "- GPS Trackers: ఇవి ప్రభుత్వ ఆమోదం పొందిన లొకేషన్ ట్రాకర్లు (AIS 140 Certified Device). "
                "ఇందులో రియల్-టైమ్ లొకేషన్ ట్రాకింగ్, స్పీడ్ మానిటరింగ్, మరియు అత్యవసర పానిక్ బటన్స్ ఉంటాయి. "
                "ఇతర మోడల్స్: Teltonika FMB120, Teltonika FMB910, మరియు 3G WCDMA GPS tracker (రిమోట్ ఇంజన్ కట్ మరియు IP67 వాటర్ ప్రూఫ్ కలిగి ఉంటుంది).\n"
                "- Smart Fuel Monitoring: మా సిస్టమ్ 99% ఖచ్చితత్వంతో డిజిటల్ ఫ్యూయల్ రాడ్ సెన్సార్లను (Italon Fuel Sensor) మరియు Teltonika FMB920 ట్రాకర్లను "
                "ఉపయోగిస్తుంది. ఇది ఇంధన దొంగతనాన్ని గుర్తించి వెంటనే లైవ్ అలర్ట్లను పంపుతుంది.\n"
                "- Smart Security Cameras & Dash Cams: Solar Cam (100% సోలార్, 4G LTE), Wi-Fi Security Camera (1080P, టూ-వే ఆడియో, నైట్ విజన్, SD/క్లౌడ్ స్టోరేజ్), మరియు Dashcam DC 01 S (ముందు/వెనుక 2K రికార్డింగ్, G-సెన్సార్ ప్రొటెక్షన్).\n"
                "- Borewell Solutions: Bore Well Rod Count (రోడ్ టైమింగ్ కౌంటింగ్ డిజిటల్ సిస్టమ్) మరియు Bore Well RPM Count (RPM మెజర్మెంట్).\n"
                "- Accessories: AC Temperature Sensor for Truck (ఏసి టెంపరేచర్ మానిటరింగ్), Car LCD Monitor (4.3\" డిస్ప్లే), మరియు Relay Cutoff Switch (12V 40A రిమోట్ ఇంజన్/ఫ్యూయల్ పవర్ కట్).\n\n"

                "FUEL TRACKS OFFICIAL CONTACT INFO (TELUGU SCRIPT):\n"
                "- ఫోన్ నంబర్: +91 90006 66914\n"
                "- ఈమెయిల్: info@fueltracks.in\n"
                "- వెబ్‌సైట్: www.fueltracks.in\n"
                "- ప్రధాన కార్యాలయం: Champapet, Hyderabad (ప్రెస్ కాలనీ, చంపాపేట్, హైదరాబాద్)\n\n"

                + offtopic_rule_telugu +
                "CRITICAL PRICING & CLOSING RULES:\n"
                "- ధర వివరాలను మీ అంతటగా ఊహించి చెప్పకండి.\n"
                "- యూజర్ డీల్స్ లేదా కోట్ కావాలని అడిగితే మా టెక్నికల్ సేల్స్ ఎక్స్‌పర్ట్, "
                "మిస్టర్ కరుణాకర్ రెడ్డి గారు 10-15 నిమిషాల్లో మీకు కాల్ చేసి పూర్తి వివరాలు "
                "అందిస్తారని చెప్పండి.\n"
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
                f"- GPS Trackers: {display_name} garu, mana trackers government certified (AIS 140 Certified Device). "
                "Indulo real-time location tracking, speed monitoring, mariyu panic buttons untayi. "
                "Other models: Teltonika FMB120, Teltonika FMB910, mariyu 3G WCDMA GPS tracker (remote engine cutoff mariyu IP67 waterproof features tho).\n"
                f"- Smart Fuel Monitoring: {display_name} garu, mana smart fuel monitoring system 99% accuracy provides chesthundhi. "
                "Indulo Italon Fuel Level Sensor mariyu Teltonika FMB920 trackers untayi. Sudden fuel level drops and theft automatic ga detect chesi alerts pampisthundhi.\n"
                f"- Smart Cameras & Dash Cams: Solar Cam (100% solar, 4G LTE), Wi-Fi Camera (1080P, night vision, two-way audio), mariyu Dashcam DC 01 S (front/rear 2K recording, loop recording, G-sensor protection).\n"
                f"- Borewell Solutions: Bore Well Rod Count (drill rod timings display device) mariyu Bore Well RPM Count (RPM drill speed display).\n"
                f"- Accessories: AC Temperature Sensor for Truck, Car LCD Monitor (4.3 inch screen), mariyu Relay Cutoff Switch (12V 40A remote power disconnection switch for fuel/ignition prevention).\n\n"

                "OFFICIAL CONTACT INFO IN TENGLISH:\n"
                "- Phone Support: +91 90006 66914\n"
                "- Email: info@fueltracks.in\n"
                "- Website: www.fueltracks.in\n"
                "- Head office address: Press Colony, Champapet, Hyderabad\n\n"

                + offtopic_rule_tenglish +
                "CRITICAL PRICING & CLOSING RULES:\n"
                "- Specific pricing package values or numerical cost rates guess cheyakandi.\n"
                f"- Deal quotes or fleet integrations adigithe: 'Mr. Karunakar Reddy garu 10-15 minutes "
                f"lo meeku call chesi full commercial proposal isthaaru' ani cheppandi.\n"
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
                "- GPS Trackers: Government-approved trackers for commercial vehicles (AIS 140 Certified Devices) featuring real-time location, speed monitoring, and panic buttons. Other models: Teltonika FMB120, Teltonika FMB910, and 3G WCDMA GPS tracker with remote engine cutoff and IP67 waterproof casing.\n"
                "- Smart Fuel Monitoring: Uses Italon digital fuel rod sensors (99% accuracy) and Teltonika FMB920 trackers to track refilling, detect sudden fuel drops, and send live theft alerts to operators.\n"
                "- Smart Security Cameras & Dash Cams: Solar Cam (100% solar powered, 4G LTE connectivity, mobile app viewing), Wi-Fi Security Camera (1080P, night vision, motion alerts, two-way audio), and Dashcam DC 01 S (front & rear 2K recording, loop recording, G-sensor protection).\n"
                "- Borewell Solutions: Bore Well Rod Count (digital display for drilling rod timings) and Bore Well RPM Count (accurate drilling RPM measurement).\n"
                "- Accessories: AC Temperature Sensor for Truck, Car LCD Monitor (4.3\" TFT kit with reversing priority), and Relay Cutoff Switch (12V 40A remote engine/fuel system cutoff).\n\n"

                "FUEL TRACKS OFFICIAL CONTACT INFO:\n"
                "- Phone Support: +91 90006 66914\n"
                "- Email: info@fueltracks.in\n"
                "- Website: www.fueltracks.in\n"
                "- Address: Press Colony, Champapet, Hyderabad, Telangana 500079\n\n"

                + offtopic_rule_english +
                "CRITICAL PRICING & QUOTE GUARDRAIL:\n"
                "- NEVER invent, guess, or state specific pricing figures or numerical rates.\n"
                "- State that our Technical Sales Expert, Mr. Karunakar Reddy, will provide a "
                "customized commercial proposal during his call.\n\n"

                "CRITICAL CLOSING GUARDRAIL:\n"
                f"- If the user says goodbye, 'bye', 'thank you', or 'thanks', close: "
                f"'Thank you for contacting Fuel Tracks Technologies, {display_name} garu. "
                "Have a great day ahead!'\n\n"

                "CONCISENESS: Keep responses clean, focused, and under 3 sentences."
            )

        # Inject ad referral context if applicable
        if customer and customer.referred_by:
            campaign = customer.referred_by
            ad_context = (
                f"\n\nCRITICAL CONTEXT: The customer arrived via the ad campaign: '{campaign.campaign_name}'. "
                f"You MUST focus your conversation strictly and exclusively on the product/topic of this ad: {campaign.custom_system_prompt}. "
                f"Do NOT offer, pitch, or discuss other company products (such as other camera types, GPS trackers, "
                f"or fuel sensors) unless the customer explicitly asks about them."
            )
            system_prompt += ad_context

        # Fetch history. To ensure stable sorting, we order by '-id' (newest first).
        messages_payload = [{"role": "system", "content": system_prompt}]

        history = ChatMessage.objects.filter(phone_number=user_phone).order_by('-id')[:6]
        history_list = list(reversed(history))

        # To prevent user message duplication, check if the latest message in history is the same user query
        if history_list and history_list[-1].role == 'user' and history_list[-1].content == new_user_message:
            # It's already in history; append all history entries
            for msg in history_list:
                messages_payload.append({"role": msg.role, "content": msg.content})
        else:
            # Not in history (or history is empty/different); append history, then append the new message
            for msg in history_list:
                messages_payload.append({"role": msg.role, "content": msg.content})
            messages_payload.append({"role": "user", "content": new_user_message})

        # Define and inject language reminder to prevent drift in LLM generation
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
        ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=ai_reply)
        return ai_reply

    except Exception as e:
        print(f"[ERROR] Error inside AI loop execution: {e}")
        return "Thank you for reaching out to Fuel Tracks Technologies Private Limited. How can we help you?"


def send_whatsapp_message(to_phone, text_content, buttons=None, document_url=None,
                          document_filename=None, location_data=None, list_data=None,
                          contact_data=None):
    """Dispatches payload structures cleanly to Meta Graph Servers."""
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
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
    except Exception as e:
        print(f"Failed to post outgoing message via Meta API: {e}")


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
        # Webhook security: verify X-Hub-Signature-256 header if secret is configured
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

                if "statuses" in value:
                    return JsonResponse({"status": "success"})

                if "messages" in value:
                    message_obj = value["messages"][0]
                    user_phone = message_obj["from"]
                    domain_url = request.scheme + "://" + request.get_host()

                    # Deduplicate Meta webhook replays using Database (persists across container restarts/processes)
                    message_id = message_obj.get("id", "")
                    if message_id:
                        from bot.models import ProcessedMessage
                        if ProcessedMessage.objects.filter(message_id=message_id).exists():
                            print(f"[WARNING] Duplicate message_id {message_id} found in DB — skipping.")
                            return JsonResponse({"status": "success"})
                        try:
                            ProcessedMessage.objects.create(message_id=message_id)
                        except Exception:
                            print(f"[WARNING] Duplicate message_id {message_id} save failed — skipping.")
                            return JsonResponse({"status": "success"})
                        
                        # Set in cache as a fast-lookup fallback
                        cache_key = f"wa_msg_id_{message_id}"
                        cache.set(cache_key, True, timeout=86400)

                    if message_obj.get("type") in ["text", "interactive"]:
                        if message_obj.get("type") == "text":
                            user_text = message_obj["text"].get("body", "")
                        else:
                            interactive_type = message_obj["interactive"].get("type", "")
                            if interactive_type == "button_reply":
                                user_text = message_obj["interactive"]["button_reply"].get("title", "")
                            elif interactive_type == "list_reply":
                                user_text = message_obj["interactive"]["list_reply"].get("title", "")
                            else:
                                user_text = ""

                        if not user_text.strip():
                            return JsonResponse({"status": "success"})

                        print(f"[INCOMING] Received text/action: '{user_text}' from {user_phone}")
                        clean_text = user_text.strip().lower()

                        # Fallback for button reply text containing welcome message prefix (e.g. from copy-paste/forwarding)
                        lines = [line.strip() for line in user_text.strip().split("\n") if line.strip()]
                        if lines:
                            last_line_clean = lines[-1].lower()
                            if last_line_clean in ["products", "office location", "talk to an agent", "start", "stop"]:
                                clean_text = last_line_clean

                        # Opt-out compliance: if customer is registered and inactive, ignore all unless "start"
                        customer_exists = FleetCustomer.objects.filter(phone_number=user_phone).exists()
                        if customer_exists:
                            customer = FleetCustomer.objects.get(phone_number=user_phone)
                            if not customer.is_active and clean_text != "start":
                                print(f"[INACTIVE] Inactive customer {user_phone} ignored (except START).")
                                return JsonResponse({"status": "success"})

                        # Initialize or fetch customer identity
                        customer, created = FleetCustomer.objects.get_or_create(
                            phone_number=user_phone,
                            defaults={"owner_name": "New Fleet Contact", "is_active": True}
                        )

                        # Check for Meta Facebook Ad Referral payload
                        referral_data = message_obj.get("referral")
                        if referral_data:
                            ad_id = referral_data.get("source_id")
                            headline = referral_data.get("headline", "")
                            body = referral_data.get("body", "")
                            print(f"[REFERRAL] Ad Referral detected: Ad ID={ad_id}, Headline='{headline}', Body='{body}'")
                            
                            matched_campaign = None
                            
                            # 1. Match by Ad ID
                            if ad_id:
                                matched_campaign = AdCampaign.objects.filter(ad_id=ad_id, is_active=True).first()
                            
                            # 2. Match by Headline Keywords
                            if not matched_campaign and (headline or body):
                                headline_lower = headline.lower() if headline else ""
                                body_lower = body.lower() if body else ""
                                for campaign in AdCampaign.objects.filter(is_active=True):
                                    if campaign.headline_keywords:
                                        keywords = [kw.strip().lower() for kw in campaign.headline_keywords.split(",") if kw.strip()]
                                        if any(kw in headline_lower or kw in body_lower for kw in keywords):
                                            matched_campaign = campaign
                                            break
                            
                            if matched_campaign:
                                print(f"[REFERRAL] Matched customer {user_phone} to campaign '{matched_campaign.campaign_name}'")
                                customer.referred_by = matched_campaign
                                customer.save()
                                
                                # Send custom welcome message if configured
                                if matched_campaign.welcome_message:
                                    # Save user's initial message
                                    ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)
                                    
                                    # Send and save custom welcome message
                                    welcome_reply = matched_campaign.welcome_message
                                    ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=welcome_reply)
                                    send_whatsapp_message(user_phone, welcome_reply)
                                    
                                    # If a catalog file is associated, send it automatically
                                    if matched_campaign.catalog_file:
                                        catalog_name = matched_campaign.catalog_file
                                        catalog_msg = CATALOG_METADATA.get(catalog_name, {}).get("en", "Here is our product catalog:")
                                        send_whatsapp_message(
                                            to_phone=user_phone,
                                            text_content=catalog_msg,
                                            document_url=f"{domain_url}/api/catalog/{catalog_name}",
                                            document_filename=catalog_name
                                        )
                                        ChatMessage.objects.create(
                                            phone_number=user_phone,
                                            role='assistant',
                                            content=f"{catalog_msg} (Sent {catalog_name})"
                                        )
                                    return JsonResponse({"status": "success"})

                        # 🌟 INTERCEPTION: Native Map Pin Routing
                        location_triggers = [
                            "office location", "లొకేషన్", "మ్యాప్", "map", "address",
                            "చిరునామా", "location pamp"
                        ]
                        device_triggers = ["tracker", "ట్రాకర్", "gps", "జిపిఎస్", "device", "పరికరం"]
                        is_device_query = has_keyword_match(clean_text, device_triggers)

                        if clean_text == "stop":
                            customer.is_active = False
                            customer.save()
                            ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)
                            opt_out_reply = (
                                "You have successfully unsubscribed from Fuel Tracks automated alerts. "
                                "Reply 'START' to resubscribe."
                            )
                            ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=opt_out_reply)
                            send_whatsapp_message(user_phone, opt_out_reply)
                            return JsonResponse({"status": "success"})

                        elif clean_text == "start":
                            customer.is_active = True
                            customer.save()
                            ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)
                            opt_in_reply = (
                                "Welcome back! Automated tracking alerts have been reactivated for your number."
                            )
                            ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=opt_in_reply)
                            send_whatsapp_message(user_phone, opt_in_reply)
                            return JsonResponse({"status": "success"})

                        elif has_keyword_match(clean_text, location_triggers) and not is_device_query:
                            location_intro = "Locating the Fuel Tracks Technologies head office branch... 📍"
                            send_whatsapp_message(user_phone, location_intro)

                            office_coordinates = {
                                "latitude": 17.3486,
                                "longitude": 78.5214,
                                "name": "Fuel Tracks Technologies Pvt Ltd",
                                "address": "Press Colony, Champapet, Hyderabad, Telangana 500079"
                            }
                            ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)
                            ChatMessage.objects.create(
                                phone_number=user_phone, role='assistant',
                                content=f"Dispatched map pin: {office_coordinates['address']}"
                            )
                            send_whatsapp_message(
                                to_phone=user_phone, text_content="",
                                location_data=office_coordinates
                            )
                            return JsonResponse({"status": "success"})

                        elif clean_text == "products":
                            ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)
                            catalog_text = "Here is our official Fuel Tracks Product Catalog Guide! 📄"
                            ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=catalog_text)
                            send_whatsapp_message(
                                user_phone, catalog_text,
                                document_url=f"{domain_url}/api/catalog/Fuel_Tracks_Catalog.pdf",
                                document_filename="Fuel_Tracks_Catalog.pdf"
                            )
                            return JsonResponse({"status": "success"})

                        elif clean_text == "talk to an agent":
                            ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)
                            agent_text = (
                                "Our Expert, Mr. Karunakar Reddy, has been notified of your request! 📞 "
                                "He will call or message you natively in 10-15 minutes."
                            )
                            ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=agent_text)
                            send_whatsapp_message(user_phone, agent_text)

                            # Notify the agent
                            agent_alert = (
                                f"🚨 New Lead Alert!\n"
                                f"Customer: {customer.owner_name}\n"
                                f"Phone: {user_phone}\n"
                                f"Truck: {customer.truck_number or 'Not provided'}\n"
                                f"Requested: Talk to an Agent"
                            )
                            send_whatsapp_message(AGENT_NOTIFY_PHONE, agent_alert)
                            return JsonResponse({"status": "success"})

                        elif customer.owner_name == "New Fleet Contact" and not customer.referred_by:
                            # Check history to see if we already asked for the name
                            history = ChatMessage.objects.filter(phone_number=user_phone, role='assistant').order_by('-id')
                            asked_for_name = False
                            if history.exists():
                                last_assistant_msg = history[0].content
                                if "May I know your name" in last_assistant_msg or "tell me your name" in last_assistant_msg:
                                    asked_for_name = True

                            if not asked_for_name:
                                ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)
                                professional_welcome = (
                                    "Welcome to Fuel Tracks Technologies Private Limited! 🚀\n\n"
                                    "We are India's trusted provider of high-end GPS Tracking Systems, "
                                    "AIS 140 Certified Devices, and Smart Fuel Monitoring Solutions "
                                    "designed to eliminate fuel theft and optimize fleet operations.\n\n"
                                    "🌐 Website: www.fueltracks.in\n"
                                    "📞 Support: +91 90006 66914\n\n"
                                    "How can we help your business today? Select an option below:"
                                )
                                ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=professional_welcome)
                                send_whatsapp_message(
                                    user_phone, professional_welcome,
                                    buttons=["Office Location", "Products", "Talk to an Agent"]
                                )

                                name_request = "May I know your name, please?"
                                ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=name_request)
                                send_whatsapp_message(user_phone, name_request)
                                return JsonResponse({"status": "success"})
                            else:
                                ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)
                                name_reply = user_text.strip()
                                extracted_details = extract_customer_details_with_ai(name_reply)
                                extracted_name = extracted_details.get("name")
                                
                                if not extracted_name:
                                    words = name_reply.split()
                                    if len(words) <= 2 and all(w.isalpha() for w in words):
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
                                    ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=welcome_text)
                                    send_whatsapp_message(user_phone, welcome_text)
                                    return JsonResponse({"status": "success"})
                                else:
                                    retry_request = "Could you please tell me your name so I know how to address you?"
                                    ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=retry_request)
                                    send_whatsapp_message(user_phone, retry_request)
                                    return JsonResponse({"status": "success"})

                        else:
                            ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)

                            # Defer Details Extraction: Only runs for queries going to the AI engine
                            needs_name = (
                                not customer.owner_name or
                                customer.owner_name.strip().lower() == "new fleet contact"
                            )
                            needs_truck = not customer.truck_number

                            if needs_name or needs_truck:
                                extracted_details = extract_customer_details_with_ai(user_text)
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
                                if needs_truck and extracted_details.get("truck_number"):
                                    customer.truck_number = extracted_details["truck_number"].upper()
                                    updated = True
                                if updated:
                                    customer.save()

                            # Process message through AI engine
                            bot_reply = get_ai_response(user_phone, user_text, customer)
                            if bot_reply is not None:
                                send_whatsapp_message(user_phone, bot_reply)

                                # Specific device catalog sending logic
                                has_telugu_script = any('\u0c00' <= char <= '\u0c7f' for char in clean_text)
                                
                                # Fetch recent messages in chat history (newest first) to enable history-based catalog lookup
                                recent_chat_history = ChatMessage.objects.filter(phone_number=user_phone).order_by('-id')[:10]
                                history_texts = [msg.content for msg in recent_chat_history]
                                
                                matched_pdf, _ = find_device_catalog_match(clean_text, history_texts)
                                
                                if matched_pdf and matched_pdf in CATALOG_METADATA:
                                    catalog_msg = CATALOG_METADATA[matched_pdf]["te"] if has_telugu_script else CATALOG_METADATA[matched_pdf]["en"]
                                    
                                    send_whatsapp_message(
                                        to_phone=user_phone,
                                        text_content=catalog_msg,
                                        document_url=f"{domain_url}/api/catalog/{matched_pdf}",
                                        document_filename=matched_pdf
                                    )
                                    
                                    ChatMessage.objects.create(
                                        phone_number=user_phone,
                                        role='assistant',
                                        content=f"{catalog_msg} (Sent {matched_pdf})"
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
    writer.writerow(['Phone Number', 'Customer Name', 'Truck Number', 'Is Active', 'Date Created'])
    
    customers = FleetCustomer.objects.all().order_by('-created_at')
    for customer in customers:
        writer.writerow([
            f'="{customer.phone_number}"',
            customer.owner_name or '',
            customer.truck_number or '',
            'Yes' if customer.is_active else 'No',
            customer.created_at.strftime('%Y-%m-%d %H:%M') if customer.created_at else ''
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
        return FileResponse(open(catalog_path, 'rb'), content_type='application/pdf')
    else:
        raise Http404("Catalog not found")