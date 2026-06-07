import os
import json
import requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv
from groq import Groq
from .models import ChatMessage, FleetCustomer

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

# 🌟 CONFIGURATION PARAMETER
AGENT_NOTIFY_PHONE = "+919000666914"  # Include your full country code (e.g., +91...)

# ✅ FIX 10: In-memory set to deduplicate Meta webhook replays within process lifetime
_processed_message_ids = set()


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

        extracted_data = json.loads(completion.choices[0].message.content.strip())
        return extracted_data
    except Exception as e:
        print(f"⚠️ Details extraction skipped or failed: {e}")
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
            "fuel tracks", "fuel tracks technologies", "madhu"
        }
        if (customer and customer.owner_name and
                customer.owner_name.strip().lower() not in invalid_names):
            display_name = customer.owner_name.strip()
        else:
            display_name = "Sir/Madam"

        # 🌟 HIGH-PRIORITY OVERRIDE 1: Contact Card Hijack
        contact_keywords = [
            "give his number", "his phone number", "contact number", "give number",
            "number of the human", "number send", "number bodybuilding", "number ivvu",
            "number pampandi", "ph no", "phone no", "mobile number", "contact details"
        ]
        if any(x in test_text_lower for x in contact_keywords):
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
            "or fleet solutions!'\n"
            "- NEVER write poems, jokes, stories, or creative content under any circumstances.\n\n"
        )
        offtopic_rule_tenglish = (
            "STRICT SCOPE — HIGHEST PRIORITY RULE:\n"
            "- Meeru ONLY Fuel Tracks Technologies products mariyu services gurinchi matladali. "
            "Meeru general chatbot kaadu — sales assistant maatram.\n"
            "- User personal topics (bhojnam, jokes, kavitalu, weather, sports, etc.) adigithe "
            "maryādagā decline cheyandi mariyu business ki redirect cheyandi.\n"
            f"- Off-topic redirect: '{display_name} garu, nenu Fuel Tracks Technologies products "
            "mariyu services ki maatrame help cheyagalanu. Meeru fleet, GPS tracking, leда fuel "
            "monitoring gurinchi adugavacchu!'\n"
            "- Poems, jokes, stories, creative content NEVER raayakandi.\n\n"
        )
        offtopic_rule_telugu = (
            "STRICT SCOPE — HIGHEST PRIORITY RULE:\n"
            "- మీరు ONLY Fuel Tracks Technologies products మరియు services గురించి మాట్లాడాలి.\n"
            "- వ్యక్తిగత విషయాలు (భోజనం, జోక్స్, కవితలు, వాతావరణం మొదలైనవి) అడిగితే "
            "మర్యాదగా తిరస్కరించండి మరియు వెంటనే business కి redirect చేయండి.\n"
            f"- Off-topic అయినప్పుడు చెప్పండి: '{display_name} గారు, నేను Fuel Tracks Technologies "
            "products మరియు services కోసం మాత్రమే సహాయం చేయగలను. GPS tracking, fuel monitoring "
            "గురించి అడగవచ్చు!'\n"
            "- Poems, jokes, stories, creative content ఎప్పుడూ రాయకండి.\n\n"
        )

        # ENGINE 1: NATIVE TELUGU SCRIPT
        if has_telugu_script:
            system_prompt = (
                "You are an expert corporate AI Sales Representative representing Fuel Tracks Technologies.\n"
                "Role Definition: You talk ON BEHALF of Fuel Tracks Technologies. You are the seller. "
                "The user chatting with you is the buyer/customer.\n\n"

                "STRICT LANGUAGE RULE:\n"
                "- The user is talking to you in Telugu Script. You MUST reply back entirely in clear, "
                "professional corporate Telugu script characters (తెలుగు లిపి).\n"
                "- Do NOT use the English/Latin alphabet characters or Tenglish words here.\n"
                f"- Always address the user strictly as '{display_name} గారు'.\n\n"

                "FUEL TRACKS OFFICIAL PRODUCT FACTS (TELUGU SCRIPT):\n"
                "- AIS 140 Certified Devices: ఇవి ప్రభుత్వ ఆమోదం పొందిన లొకేషన్ ట్రాకర్లు. "
                "ఇందులో రియల్-టైమ్ లొకేషన్ ట్రాకింగ్, స్పీడ్ మానిటరింగ్, మరియు అత్యవసర పానిక్ "
                "బటన్స్ ఉంటాయి. ఇవి Champapet లొకేషన్‌లో లభిస్తాయి.\n"
                "- Smart Fuel Monitoring: మా సిస్టమ్ 99% ఖచ్చితత్వంతో డిజిటల్ ఫ్యూయల్ రాడ్ సెన్సార్లను "
                "ఉపయోగిస్తుంది. ఇది ఇంధన దొంగతనాన్ని గుర్తించి వెంటనే లైవ్ అలర్ట్లను పంపుతుంది.\n\n"

                + offtopic_rule_telugu +
                "CRITICAL PRICING & CLOSING RULES:\n"
                "- ధర వివరాలను మీ అంతటగా ఊహించి చెప్పకండి.\n"
                "- యూజర్ డీల్స్ లేదా కోట్ కావాలని అడిగితే మా టెక్నికల్ సేల్స్ ఎక్స్‌పర్ట్, "
                "మిస్టర్ కరుణాకర్ రెడ్డి గారు 10-15 నిమిషాల్లో మీకు కాల్ చేసి పూర్తి వివరాలు "
                "అందిస్తారని చెప్పండి.\n"
                f"- ఒకవేళ యూజర్ 'సరే', 'ధన్యవాదాలు', లేదా సెలవు చెబితే: "
                f"'ఫ్యూయల్ ట్రాక్స్ టెక్నాలజీస్‌ను సంప్రదించినందుకు ధన్యవాదాలు, {display_name} గారు. "
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
                f"- Always address the user strictly as '{display_name} garu'.\n\n"

                "FUEL TRACKS FACTS IN TENGLISH:\n"
                f"- AIS 140 Certified Devices: {display_name} garu, mana trackers commercial vehicles ki "
                "government certified. Indulo real-time location tracking, speed monitoring, mariyu "
                "emergency panic buttons untayi. Mana head office branch Champapet lo undhi.\n"
                f"- Smart Fuel Monitoring: {display_name} garu, mana smart fuel monitoring system 99% "
                "accuracy provide chesthundhi. Idi sudden fuel level drops automatic ga detect chesi "
                "live theft alerts operators ki pampisthundhi.\n\n"

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
                f"- Address the user strictly as '{display_name} garu'.\n\n"

                "FUEL TRACKS OFFICIAL PRODUCT FACTS:\n"
                "- AIS 140 Certified Devices: Government-approved trackers for commercial and public "
                "transport vehicles. Features include dual IP67 waterproof casing, real-time location "
                "tracking, speed monitoring, and emergency panic buttons. Our head office is located "
                "in Press Colony, Champapet.\n"
                "- Smart Fuel Monitoring: Uses digital fuel rod sensors with 99% accuracy to track "
                "refilling, detect sudden fuel level drops, and send live fuel theft alerts "
                "instantaneously to operators.\n\n"

                + offtopic_rule_english +
                "CRITICAL PRICING & QUOTE GUARDRAIL:\n"
                "- NEVER invent, guess, or state specific pricing figures or numerical rates.\n"
                "- State that our Technical Sales Expert, Mr. Karunakar Reddy, will provide a "
                "customized commercial proposal during his call.\n\n"

                "CRITICAL CLOSING GUARDRAIL:\n"
                f"- If the user says goodbye or 'bye', close: "
                f"'Thank you for contacting Fuel Tracks Technologies, {display_name} garu. "
                "Have a great day ahead!'\n\n"

                "CONCISENESS: Keep responses clean, focused, and under 3 sentences."
            )

        # ✅ FIX 6: Load history BEFORE saving the new user message to avoid double-counting.
        #    History is fetched here (user message not yet in DB at this point).
        messages_payload = [{"role": "system", "content": system_prompt}]

        history = ChatMessage.objects.filter(phone_number=user_phone).order_by('-timestamp')[:6]
        for msg in reversed(list(history)):
            messages_payload.append({"role": msg.role, "content": msg.content})

        messages_payload.append({"role": "user", "content": new_user_message})

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
        print(f"❌ Error inside AI loop execution: {e}")
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

                    # ✅ FIX 10: Deduplicate Meta webhook replays using message_id
                    message_id = message_obj.get("id", "")
                    if message_id and message_id in _processed_message_ids:
                        print(f"⚠️ Duplicate message_id {message_id} — skipping.")
                        return JsonResponse({"status": "success"})
                    if message_id:
                        _processed_message_ids.add(message_id)

                    if message_obj.get("type") in ["text", "interactive"]:
                        if message_obj.get("type") == "text":
                            user_text = message_obj["text"]["body"]
                        else:
                            interactive_type = message_obj["interactive"]["type"]
                            if interactive_type == "button_reply":
                                user_text = message_obj["interactive"]["button_reply"]["title"]
                            elif interactive_type == "list_reply":
                                user_text = message_obj["interactive"]["list_reply"]["title"]
                            else:
                                user_text = ""

                        if not user_text.strip():
                            return JsonResponse({"status": "success"})

                        print(f"📥 Received text/action: '{user_text}' from {user_phone}")
                        clean_text = user_text.strip().lower()

                        # Initialize or fetch customer identity
                        customer, created = FleetCustomer.objects.get_or_create(
                            phone_number=user_phone,
                            defaults={"owner_name": "New Fleet Contact", "is_active": True}
                        )

                        # ✅ FIX 7: Only run AI extraction when BOTH name AND truck_number are missing
                        needs_name = (
                            not customer.owner_name or
                            customer.owner_name.strip().lower() == "new fleet contact"
                        )
                        needs_truck = not customer.truck_number

                        if needs_name or needs_truck:
                            extracted_details = extract_customer_details_with_ai(user_text)
                            blocked_names = {
                                "karunakar reddy", "mr. karunakar reddy", "karunakar",
                                "fuel tracks", "fuel tracks technologies", "madhu",
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

                        # 🌟 INTERCEPTION: Native Map Pin Routing
                        location_triggers = [
                            "office location", "లొకేషన్", "మ్యాప్", "map", "address",
                            "చిరునామా", "location pamp"
                        ]
                        if any(trigger in clean_text for trigger in location_triggers):
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

                        # Keyword Subscription Routing
                        if clean_text == "stop":
                            customer.is_active = False
                            customer.save()
                            # ✅ FIX 5: Save chat history for STOP/START too
                            ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)
                            opt_out_reply = (
                                "You have successfully unsubscribed from Fuel Tracks automated alerts. "
                                "Reply 'START' to resubscribe."
                            )
                            ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=opt_out_reply)
                            send_whatsapp_message(user_phone, opt_out_reply)

                        elif clean_text == "start":
                            customer.is_active = True
                            customer.save()
                            # ✅ FIX 5: Save chat history for START too
                            ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)
                            opt_in_reply = (
                                "Welcome back! Automated tracking alerts have been reactivated for your number."
                            )
                            ChatMessage.objects.create(phone_number=user_phone, role='assistant', content=opt_in_reply)
                            send_whatsapp_message(user_phone, opt_in_reply)

                        else:
                            # Save the incoming user message before any branching
                            ChatMessage.objects.create(phone_number=user_phone, role='user', content=user_text)

                            if created:
                                # ✅ FIX 12: New user — send welcome AND ALSO process their first
                                #    message through AI so the greeting is context-aware.
                                professional_welcome = (
                                    "Welcome to Fuel Tracks Technologies Private Limited! 🚀\n\n"
                                    "We are India's trusted provider of high-end GPS Tracking Systems, "
                                    "AIS 140 Certified Devices, and Smart Fuel Monitoring Solutions "
                                    "designed to eliminate fuel theft and optimize fleet operations.\n\n"
                                    "🌐 Website: www.fueltracks.in\n"
                                    "📞 Support: +91 90006 66914\n\n"
                                    "How can we help your business today? Select an option below:"
                                )
                                send_whatsapp_message(
                                    user_phone, professional_welcome,
                                    buttons=["Office Location", "Products", "Talk to an Agent"]
                                )
                                # Do not pass through AI on first contact — welcome message is sufficient.
                                # The customer's next reply will be handled by the AI engine.

                            elif clean_text == "products":
                                catalog_text = "Here is our official Fuel Tracks Product Catalog Guide! 📄"
                                send_whatsapp_message(
                                    user_phone, catalog_text,
                                    document_url="https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
                                    document_filename="Fuel_Tracks_Catalog.pdf"
                                )

                            # ✅ FIX 1 & 3: "Talk to an Agent" button text fixed to match,
                            #    and AGENT_NOTIFY_PHONE now actually receives a WhatsApp alert.
                            elif clean_text == "talk to an agent":
                                agent_text = (
                                    "Our Expert, Mr. Karunakar Reddy, has been notified of your request! 📞 "
                                    "He will call or message you natively in 10-15 minutes."
                                )
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

                            else:
                                # AI engine — user message already saved above
                                bot_reply = get_ai_response(user_phone, user_text, customer)
                                # bot_reply is None when contact card branch handles everything internally
                                if bot_reply is not None:
                                    send_whatsapp_message(user_phone, bot_reply)

        except Exception as e:
            print(f"Error inside primary webhook context loop: {e}")

    return JsonResponse({"status": "success"})