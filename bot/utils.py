import os


def parse_excel_or_csv(file_path_or_buffer, filename=None):
    """
    Parses a CSV or Excel file and returns a list of dictionaries with customer details.
    Standardized keys: phone_number, owner_name, truck_number, is_active
    """
    import pandas as pd

    if filename is None:
        if isinstance(file_path_or_buffer, str):
            filename = file_path_or_buffer
        else:
            filename = getattr(file_path_or_buffer, 'name', '')

    lower_filename = filename.lower()
    if lower_filename.endswith('.csv'):
        # Force column types to be strings to prevent dropping leading zeroes
        df = pd.read_csv(file_path_or_buffer, dtype=str)
    elif lower_filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_path_or_buffer, dtype=str)
    else:
        raise ValueError(
            "Unsupported file format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file.")

    # Standardize column names (lowercase, strip spaces, replace spaces with
    # underscores)
    df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

    # Map possible columns to target fields
    phone_cols = [
        'phone_number',
        'phone',
        'mobile',
        'mobile_number',
        'phone_no',
        'ph_no',
        'ph']
    name_cols = ['owner_name', 'customer_name', 'name', 'owner', 'customer']
    truck_cols = [
        'truck_number',
        'vehicle_number',
        'truck',
        'vehicle',
        'truck_no',
        'vehicle_no',
        'registration_number',
        'registration_no',
        'reg_number',
        'reg_no',
        'registration']
    active_cols = ['is_active', 'active', 'status']

    # Helper to find matching column
    def find_col(possible_cols):
        for c in df.columns:
            clean_c = c.replace(
                '_',
                ' ').replace(
                '-',
                ' ').strip().lower().replace(
                ' ',
                '_')
            if clean_c in possible_cols or c in possible_cols:
                return c
        return None

    phone_col = find_col(phone_cols)
    name_col = find_col(name_cols)
    truck_col = find_col(truck_cols)
    active_col = find_col(active_cols)

    if not phone_col:
        raise ValueError(
            "Could not find a phone number column in the file. Please ensure there is a column named 'Phone Number' or 'Mobile'.")

    customers_data = []
    # Use to_dict('records') — ~60x faster than iterrows() for 50k rows
    for row in df.to_dict('records'):
        val_phone = row.get(phone_col)
        if val_phone is None:
            continue
        import pandas as pd
        if pd.isna(val_phone):
            continue
        phone = str(val_phone).strip()
        # Clean phone number (remove float .0, spaces, etc.)
        if phone.endswith('.0'):
            phone = phone[:-2]
        phone = ''.join(filter(str.isdigit, phone))

        if not phone:
            continue

        # Standardize Indian numbers to include '91' country code
        if len(phone) == 10:
            phone = '91' + phone
        elif len(phone) == 11 and phone.startswith('0'):
            phone = '91' + phone[1:]

        name = None
        if name_col:
            raw_name = row.get(name_col)
            if raw_name is not None and not pd.isna(raw_name):
                name = str(raw_name).strip()
                if name in ('nan', 'None', ''):
                    name = None

        truck = None
        if truck_col:
            raw_truck = row.get(truck_col)
            if raw_truck is not None and not pd.isna(raw_truck):
                truck = str(raw_truck).strip()
                if truck in ('nan', 'None', ''):
                    truck = None

        is_active = True
        if active_col:
            raw_active = row.get(active_col)
            if raw_active is not None and not pd.isna(raw_active):
                val_active = str(raw_active).strip().lower()
                if val_active in ('false', '0', 'no', 'n', 'inactive', 'off'):
                    is_active = False

        customers_data.append({
            'phone_number': phone,
            'owner_name': name,
            'truck_number': truck,
            'is_active': is_active
        })
    return customers_data


def normalize_phone_number(phone):
    """
    Cleans and normalizes phone numbers to standard format (with 91 country code for Indian 10-digit numbers).
    """
    if not phone:
        return ""
    phone = str(phone).strip()
    if phone.endswith('.0'):
        phone = phone[:-2]
    phone = ''.join(filter(str.isdigit, phone))
    if not phone:
        return ""
    if len(phone) == 10:
        phone = '91' + phone
    elif len(phone) == 11 and phone.startswith('0'):
        phone = '91' + phone[1:]
    return phone



def upload_media_to_meta(file_path_or_field):
    """
    Uploads a file to Meta Cloud API and returns the media_id.
    Accepts a local file path (str) or a Django FieldFile/File object.
    """
    import os
    import requests
    import mimetypes

    phone_number_id = os.getenv("PHONE_NUMBER_ID")
    whatsapp_token = os.getenv("WHATSAPP_TOKEN")
    if not phone_number_id or not whatsapp_token:
        raise ValueError(
            "PHONE_NUMBER_ID and WHATSAPP_TOKEN must be configured in environment.")

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/media"
    headers = {
        "Authorization": f"Bearer {whatsapp_token}"
    }

    file_name = None
    file_obj = None
    mime_type = "image/jpeg"  # Default fallback

    # Check if it's a Django FieldFile or File object (it will have open
    # method and name)
    if hasattr(file_path_or_field, "name") and hasattr(
            file_path_or_field, "open"):
        file_name = os.path.basename(file_path_or_field.name)
        guess = mimetypes.guess_type(file_name)[0]
        if guess:
            mime_type = guess
        file_obj = file_path_or_field
        try:
            file_obj.seek(0)
        except Exception:
            pass
    elif isinstance(file_path_or_field, str):
        if not os.path.exists(file_path_or_field):
            raise FileNotFoundError(
                f"File not found on local disk: {file_path_or_field}")
        file_name = os.path.basename(file_path_or_field)
        guess = mimetypes.guess_type(file_name)[0]
        if guess:
            mime_type = guess
        file_obj = open(file_path_or_field, "rb")
    else:
        raise TypeError(
            "file_path_or_field must be a string file path or a Django File/FieldFile object.")

    try:
        files = {
            "messaging_product": (None, "whatsapp"),
            "file": (file_name, file_obj, mime_type),
            "type": (None, mime_type)
        }
        response = requests.post(url, headers=headers, files=files, timeout=12)

        if response.status_code == 200:
            media_id = response.json().get("id")
            if not media_id:
                raise Exception("Response did not contain media ID.")
            return media_id
        else:
            raise Exception(
                f"Meta API returned status code {
                    response.status_code}: {
                    response.text}")
    finally:
        if isinstance(file_path_or_field, str):
            try:
                if file_obj:
                    file_obj.close()
            except Exception:
                pass
        else:
            try:
                if file_obj:
                    file_obj.seek(0)
            except Exception:
                pass


def download_media_from_meta(message_obj, message_id=None):
    """
    Downloads media (audio, image, video, document) sent by customer via Meta WhatsApp Cloud API.
    Saves file to MEDIA_ROOT / 'incoming_media' / and returns the relative URL (e.g. /media/incoming_media/wamid_123.mp3).
    If it's audio, converts .ogg to .mp3 using imageio_ffmpeg if available for universal browser playback.
    """
    import os
    import requests
    import tempfile
    import subprocess
    from django.conf import settings

    if not isinstance(message_obj, dict):
        return None

    media_type = message_obj.get("type")
    if not media_type or media_type not in message_obj:
        return None

    media_info = message_obj.get(media_type, {})
    media_id = media_info.get("id")
    if not media_id:
        return None

    whatsapp_token = os.getenv("WHATSAPP_TOKEN")
    if not whatsapp_token:
        print("[MEDIA DOWNLOAD] WHATSAPP_TOKEN missing in environment.")
        return None

    try:
        # Step 1: Query Meta Graph API for media URL
        url_endpoint = f"https://graph.facebook.com/v19.0/{media_id}"
        headers = {"Authorization": f"Bearer {whatsapp_token}"}
        resp = requests.get(url_endpoint, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"[MEDIA DOWNLOAD] Meta media query failed: {resp.status_code} {resp.text}")
            return None

        meta_json = resp.json()
        download_url = meta_json.get("url")
        mime_type = meta_json.get("mime_type", "")
        if not download_url:
            print("[MEDIA DOWNLOAD] Meta returned no download URL.")
            return None

        # Step 2: Download the binary file
        dl_resp = requests.get(download_url, headers=headers, timeout=20)
        if dl_resp.status_code != 200:
            print(f"[MEDIA DOWNLOAD] File download failed with status {dl_resp.status_code}")
            return None

        file_bytes = dl_resp.content

        # Step 3: Determine target filename and directory
        safe_msg_id = "".join(c for c in (message_id or media_id) if c.isalnum() or c in ("-", "_"))
        if not safe_msg_id:
            safe_msg_id = str(media_id)

        target_dir = os.path.join(settings.MEDIA_ROOT, "incoming_media")
        os.makedirs(target_dir, exist_ok=True)

        if media_type == "audio":
            # WhatsApp voice notes arrive as audio/ogg; codecs=opus
            # Convert to mp3 using ffmpeg for universal browser support
            converted = False
            target_path = os.path.join(target_dir, f"{safe_msg_id}.mp3")
            try:
                import imageio_ffmpeg
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_ogg:
                    temp_ogg.write(file_bytes)
                    temp_ogg_path = temp_ogg.name

                conv_res = subprocess.run([
                    ffmpeg_exe, "-y", "-i", temp_ogg_path,
                    "-acodec", "libmp3lame", "-q:a", "2",
                    target_path
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                if os.path.exists(temp_ogg_path):
                    try:
                        os.remove(temp_ogg_path)
                    except Exception:
                        pass

                if conv_res.returncode == 0 and os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                    converted = True
                    print(f"[MEDIA DOWNLOAD] Successfully converted voice note to MP3: {target_path}")
            except Exception as conv_err:
                print(f"[MEDIA DOWNLOAD WARNING] Audio conversion failed, writing raw bytes: {conv_err}")

            if not converted:
                # Fallback: save raw bytes as .ogg or .mp4
                ext = "mp4" if "mp4" in mime_type else "ogg"
                target_path = os.path.join(target_dir, f"{safe_msg_id}.{ext}")
                with open(target_path, "wb") as f:
                    f.write(file_bytes)
                rel_url = f"/media/incoming_media/{safe_msg_id}.{ext}"
            else:
                rel_url = f"/media/incoming_media/{safe_msg_id}.mp3"
        else:
            # For image, video, document
            ext = "bin"
            if "jpeg" in mime_type or "jpg" in mime_type: ext = "jpg"
            elif "png" in mime_type: ext = "png"
            elif "mp4" in mime_type: ext = "mp4"
            elif "pdf" in mime_type: ext = "pdf"
            else:
                import mimetypes
                guessed = mimetypes.guess_extension(mime_type)
                if guessed:
                    ext = guessed.lstrip(".")

            target_path = os.path.join(target_dir, f"{safe_msg_id}.{ext}")
            with open(target_path, "wb") as f:
                f.write(file_bytes)
            rel_url = f"/media/incoming_media/{safe_msg_id}.{ext}"

        print(f"[MEDIA DOWNLOAD SUCCESS] Saved {media_type} to {rel_url}")
        return rel_url
    except Exception as err:
        print(f"[MEDIA DOWNLOAD ERROR] Failed downloading {media_type}: {err}")
        return None

