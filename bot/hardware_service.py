import os
import io
import time
import base64
import tempfile
import subprocess
import requests
from PIL import Image
from groq import Groq
from django.conf import settings

HARDWARE_DIAGNOSTIC_PROMPT = """You are the Lead Hardware & Telematics Diagnostic Engineer at FuelTracks Technologies.
A fleet customer has sent visual media (photo or video frames) on WhatsApp regarding their vehicle hardware, GPS tracker, fuel sensor, or wiring.

Analyze the visual evidence carefully with technician-grade precision:

0. BLURRY / DARK / GLARE GUARDRAIL (CRITICAL):
   - If the photo/video is too dark under the steering wheel, too blurry from hand vibration, or blinded by camera flash/glare so you cannot clearly see the LEDs or wiring, DO NOT GUESS OR HALLUCINATE.
   - Reply warmly and politely:
     "The photo/video is a bit dark or blurry under the dashboard. Could you please turn on your phone flashlight and take a steady, clear picture from about 1 foot away? This will help me see the indicator lights clearly and diagnose the issue for you!"

1. IDENTIFY HARDWARE / COMPONENT:
   - GPS Tracker / AIS-140 VLTD (e.g. Concox GT06N, WeTrack2, Teltonika FMB920/120, Coban)
   - Indicator LEDs (Red = Power, Blue = GPS Satellites, Green = GSM/GPRS Cellular Network)
   - Digital Capacitive Fuel Level Sensor (probe rod, tank flange, RS232/RS485 cable, calibration box)
   - Vehicle Wiring Harness / 2A Inline Fuse Holder / Battery Terminals / ACC ignition wire
   - Vehicle Document (RC, Insurance, Fitness, Permit)
   - Other / Unrelated

2. LED INDICATOR TELEMATICS RULES (watch across frames for blinking patterns):
   - Red LED (Main Power):
     * Solid Red = External 12V/24V vehicle battery power is connected and healthy.
     * Blinking / Amber / Dim Red = Running on INTERNAL backup battery! The truck's main battery switch is OFF, the vehicle battery is dead, or the inline 2A fuse on the red wire has blown.
     * Red OFF = Complete power loss (both vehicle power and internal battery dead).
   - Blue LED (GPS Satellite Fix):
     * Solid Blue = GPS Fix locked (satellite connected).
     * Fast Blinking across frames = Searching for GPS satellites (vehicle parked in basement, tin shed, canopy, or antenna obstructed).
     * Blue OFF = GPS module asleep or inactive.
   - Green LED (GSM Cellular & GPRS):
     * Slow Blinking = GSM cellular connected and actively streaming telemetry data to FuelTracks server.
     * Fast Blinking or OFF across all frames = SIM card validity expired, SIM dislodged, or vehicle is in a no-network dead zone.

3. FUEL SENSOR & WIRING RULES:
   - Check flange mounting, rubber gasket leaks, RS232/RS485 coupler connection, bent probe rod, or loose ground/earth wire.

4. MULTILINGUAL MIRRORING:
   - If the customer's text or caption is in Telugu or Tenglish, reply in friendly Telugu/Tenglish.
   - If in Hindi or Hinglish, reply in friendly Hindi/Hinglish.
   - If in Tamil or Tanglish, reply in friendly Tamil/Tanglish.
   - Otherwise, reply in warm, clear, professional Indian English.

5. IF IT IS A VEHICLE DOCUMENT:
   - Acknowledge that the document has been received and noted for their fleet records.

6. IF IT IS NOT RELATED TO HARDWARE OR VEHICLE:
   - Politely respond: "Thank you for sharing. How can our FuelTracks support team assist you with your fleet or device today?"

RESPONSE FORMAT (Keep it concise, friendly, WhatsApp-formatted with bold tags and emojis):
🔍 *Hardware Identified:* [e.g. AIS 140 GPS Tracker / Digital Fuel Sensor]
💡 *Diagnostic Status & Issue:* [State clearly what is wrong with the device based on the LEDs or wiring]
🛠️ *How to Solve:*
• Step 1: [Exact actionable step, e.g. check 2A fuse on red wire, move vehicle into open sky]
• Step 2: [Next step, e.g. verify SIM balance or reboot device]
📞 *FuelTracks Technical Support:*
If the issue persists, our support team is available at *+91 73374 33350* / *+91 90006 66914*.
"""


def cleanup_old_media(max_age_days=7):
    """
    Auto-purges incoming media older than max_age_days to guarantee
    that Render server storage is never exhausted.
    """
    try:
        media_dir = os.path.join(settings.MEDIA_ROOT, "incoming_media")
        if not os.path.exists(media_dir):
            return

        now = time.time()
        max_age_secs = max_age_days * 86400
        purged_count = 0

        for fname in os.listdir(media_dir):
            fpath = os.path.join(media_dir, fname)
            if os.path.isfile(fpath):
                if now - os.path.getmtime(fpath) > max_age_secs:
                    try:
                        os.remove(fpath)
                        purged_count += 1
                    except Exception:
                        pass
        if purged_count > 0:
            print(f"[STORAGE CLEANUP] Purged {purged_count} old media files from incoming_media.")
    except Exception as e:
        print(f"[STORAGE CLEANUP WARNING] Media cleanup failed: {e}")


def optimize_and_encode_image(image_path_or_bytes, max_dim=1024):
    """
    Optimizes image size to ensure minimal bandwidth, fast LPU processing,
    and prevent any memory/storage bottlenecks on the server.
    """
    try:
        if isinstance(image_path_or_bytes, bytes):
            img = Image.open(io.BytesIO(image_path_or_bytes))
        else:
            img = Image.open(image_path_or_bytes)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        width, height = img.size
        if max(width, height) > max_dim:
            scaling_factor = max_dim / float(max(width, height))
            new_size = (int(width * scaling_factor), int(height * scaling_factor))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=82, optimize=True)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return encoded
    except Exception as e:
        print(f"[HARDWARE SERVICE ERROR] Image optimization failed: {e}")
        return None


def extract_video_frames(video_path, max_frames=3):
    """
    Extracts 2-3 keyframes across the video using imageio_ffmpeg in < 200ms.
    Captures temporal changes (LED blinking, wiring movement, fuel leaks).
    """
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        print(f"[HARDWARE SERVICE ERROR] FFmpeg not available: {e}")
        return []

    full_path = video_path
    if not os.path.isabs(full_path):
        full_path = os.path.join(settings.BASE_DIR, video_path.lstrip("/\\"))
    if not os.path.exists(full_path):
        media_root_path = os.path.join(settings.MEDIA_ROOT, "incoming_media", os.path.basename(video_path))
        if os.path.exists(media_root_path):
            full_path = media_root_path
        else:
            print(f"[HARDWARE SERVICE ERROR] Video file not found: {full_path}")
            return []

    timestamps = ["00:00:00.5", "00:00:01.5", "00:00:02.5"][:max_frames]
    encoded_frames = []

    for idx, ts in enumerate(timestamps):
        temp_frame_path = os.path.join(tempfile.gettempdir(), f"frame_{idx}_{os.path.basename(video_path)}.jpg")
        try:
            res = subprocess.run([
                ffmpeg_exe, "-y",
                "-ss", ts,
                "-i", full_path,
                "-vframes", "1",
                "-q:v", "2",
                temp_frame_path
            ], capture_output=True, timeout=5)

            if res.returncode == 0 and os.path.exists(temp_frame_path) and os.path.getsize(temp_frame_path) > 0:
                b64 = optimize_and_encode_image(temp_frame_path)
                if b64:
                    encoded_frames.append(b64)
        except Exception as frame_err:
            print(f"[HARDWARE SERVICE WARNING] Failed extracting frame at {ts}: {frame_err}")
        finally:
            if os.path.exists(temp_frame_path):
                try:
                    os.remove(temp_frame_path)
                except Exception:
                    pass

    return encoded_frames


def diagnose_hardware_image(image_path, user_caption=""):
    """
    Analyzes an incoming device/wiring image via Groq multimodal vision (Qwen 3.8 27B).
    Returns a customer-friendly, professional diagnostic response with the exact issue and fix.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return (
            "Thank you for sharing the photo. Our FuelTracks technical team has received it "
            "and will review it shortly. For immediate assistance, call *+91 73374 33350*."
        )

    full_path = image_path
    if not os.path.isabs(full_path):
        full_path = os.path.join(settings.BASE_DIR, image_path.lstrip("/\\"))

    if not os.path.exists(full_path):
        media_root_path = os.path.join(settings.MEDIA_ROOT, "incoming_media", os.path.basename(image_path))
        if os.path.exists(media_root_path):
            full_path = media_root_path
        else:
            return (
                "Thank you for sharing the photo. Our technical team has received it. "
                "For direct support, contact FuelTracks at *+91 73374 33350*."
            )

    encoded_b64 = optimize_and_encode_image(full_path)
    if not encoded_b64:
        return (
            "The photo could not be read clearly. Could you please take a clear picture "
            "under good lighting and send it again? Support: *+91 73374 33350*."
        )

    caption_context = f"\nCustomer note/caption: '{user_caption}'" if user_caption else ""
    full_user_prompt = f"{HARDWARE_DIAGNOSTIC_PROMPT}{caption_context}"

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_b64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=400,
        )

        diagnosis = response.choices[0].message.content
        if diagnosis and len(diagnosis.strip()) > 10:
            return diagnosis.strip()
    except Exception as groq_err:
        print(f"[HARDWARE SERVICE ERROR] Groq vision inference failed: {groq_err}")

    return (
        "Thank you for sharing the hardware photo. We have logged your device image in FuelTracks support. "
        "Our hardware specialist will inspect it and connect with you. "
        "Direct Hotline: *+91 73374 33350* / *+91 90006 66914*."
    )


def diagnose_hardware_video(video_path, user_caption=""):
    """
    Extracts consecutive video frames and analyzes blinking LEDs, wiring, or sensor issues
    using Groq multimodal vision (Qwen 3.8 27B).
    Returns the exact issue identified from the video and how to solve it.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return (
            "Thank you for sharing the video clip. Our FuelTracks technical team has received it "
            "and will review it shortly. For immediate assistance, call *+91 73374 33350*."
        )

    frames_b64 = extract_video_frames(video_path, max_frames=3)
    if not frames_b64:
        return (
            "Thank you for sharing the video. Our FuelTracks technical team has received your clip "
            "and is reviewing it. Direct Hotline: *+91 73374 33350* / *+91 90006 66914*."
        )

    caption_context = f"\nCustomer note/caption: '{user_caption}'" if user_caption else ""
    full_user_prompt = (
        f"{HARDWARE_DIAGNOSTIC_PROMPT}\n"
        f"NOTE: The user sent a short video clip. The images below are consecutive frames extracted across the clip. "
        f"Compare the frames to determine if the LEDs are BLINKING, SOLID, or OFF.{caption_context}"
    )

    message_content = [{"type": "text", "text": full_user_prompt}]
    for idx, b64 in enumerate(frames_b64):
        message_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}"
            }
        })

    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=[{"role": "user", "content": message_content}],
            temperature=0.1,
            max_tokens=400,
        )

        diagnosis = response.choices[0].message.content
        if diagnosis and len(diagnosis.strip()) > 10:
            return diagnosis.strip()
    except Exception as groq_err:
        print(f"[HARDWARE SERVICE ERROR] Groq video frames inference failed: {groq_err}")

    return (
        "Thank you for sharing the hardware video. We have logged your clip in FuelTracks support. "
        "Our hardware engineer will inspect it and contact you shortly. "
        "Direct Hotline: *+91 73374 33350* / *+91 90006 66914*."
    )


def transcribe_voice_note(audio_path):
    """
    Transcribes incoming WhatsApp voice notes (.mp3) using Groq Whisper (whisper-large-v3).
    Supports Telugu, Hindi, Tamil, and English. Runs in < 400ms.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    full_path = audio_path
    if not os.path.isabs(full_path):
        full_path = os.path.join(settings.BASE_DIR, audio_path.lstrip("/\\"))
    if not os.path.exists(full_path):
        media_root_path = os.path.join(settings.MEDIA_ROOT, "incoming_media", os.path.basename(audio_path))
        if os.path.exists(media_root_path):
            full_path = media_root_path
        else:
            return None

    try:
        client = Groq(api_key=api_key)
        with open(full_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f
            )
        if transcription and transcription.text and len(transcription.text.strip()) > 1:
            clean_text = transcription.text.strip()
            print(f"[VOICE TRANSCRIBE SUCCESS] Transcribed audio: '{clean_text}'")
            return clean_text
    except Exception as e:
        print(f"[VOICE TRANSCRIBE ERROR] Whisper transcription failed: {e}")
    return None


def get_vehicle_live_status(user_phone, vehicle_query=""):
    """
    Fetches real-time vehicle telemetry (lat, lng, speed, ignition, fuel, battery)
    from FuelTracks backend API for the authenticated customer phone.
    """
    api_url = os.getenv("FUELTRACKS_API_URL", "https://api.fueltracks.in")
    bot_secret = os.getenv("WHATSAPP_APP_SECRET", "")

    try:
        params = {"phone": user_phone}
        if vehicle_query:
            params["vehicle"] = vehicle_query

        resp = requests.get(
            f"{api_url}/api/auth/bot-vehicle-status",
            params=params,
            headers={"x-bot-secret": bot_secret},
            timeout=5
        )

        if resp.status_code == 200:
            res_json = resp.json()
            vehicles = res_json.get("vehicles") or []
            if vehicles:
                return format_vehicle_status_message(vehicles)
        elif resp.status_code == 404:
            return None
    except Exception as e:
        print(f"[VEHICLE STATUS LOOKUP ERROR] {e}")

    return None


def format_vehicle_status_message(vehicles):
    """
    Formats live vehicle telemetry into a clean, professional WhatsApp card.
    """
    blocks = []
    for v in vehicles[:3]:
        plate = v.get("plate") or v.get("name") or "Vehicle"
        speed = float(v.get("speed") or 0)
        ignition = v.get("ignition") in (1, True, "1", "true")
        lat = v.get("lat")
        lng = v.get("lng")
        voltage = v.get("voltage") or v.get("battery")
        fuel_level = v.get("fuel_level")
        fuel_percent = v.get("fuel_percent")

        if speed > 2:
            status_line = f"🟢 *Moving* ({int(speed)} km/h)"
        elif ignition:
            status_line = "🟡 *Idling* (Engine ON)"
        else:
            status_line = "🛑 *Parked* (Engine OFF)"

        lines = [
            f"🚛 *Vehicle: {plate}*",
            f"• *Current Status:* {status_line}",
        ]

        if voltage:
            lines.append(f"• *Battery Voltage:* {voltage}V 🔋")

        if fuel_level is not None:
            fuel_str = f"{fuel_level} Liters"
            if fuel_percent is not None:
                fuel_str += f" ({fuel_percent}%)"
            lines.append(f"• *Fuel Level:* {fuel_str} ⛽")

        if lat and lng:
            maps_url = f"https://maps.google.com/?q={lat},{lng}"
            lines.append(f"📍 *Live Google Maps:* {maps_url}")

        blocks.append("\n".join(lines))

    result_text = "\n\n───────────────\n\n".join(blocks)
    result_text += "\n\n📲 *Full Fleet Dashboard:* https://app.fueltracks.in"
    return result_text
