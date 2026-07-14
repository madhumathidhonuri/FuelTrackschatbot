import os
import pandas as pd

def parse_excel_or_csv(file_path_or_buffer, filename=None):
    """
    Parses a CSV or Excel file and returns a list of dictionaries with customer details.
    Standardized keys: phone_number, owner_name, truck_number, is_active
    """
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
        raise ValueError("Unsupported file format. Please upload an Excel (.xlsx, .xls) or CSV (.csv) file.")

    # Standardize column names (lowercase, strip spaces, replace spaces with underscores)
    df.columns = [str(c).strip().lower().replace(' ', '_') for c in df.columns]

    # Map possible columns to target fields
    phone_cols = ['phone_number', 'phone', 'mobile', 'mobile_number', 'phone_no', 'ph_no', 'ph']
    name_cols = ['owner_name', 'customer_name', 'name', 'owner', 'customer']
    truck_cols = ['truck_number', 'vehicle_number', 'truck', 'vehicle', 'truck_no', 'vehicle_no', 'registration_number', 'registration_no', 'reg_number', 'reg_no', 'registration']
    active_cols = ['is_active', 'active', 'status']

    # Helper to find matching column
    def find_col(possible_cols):
        for c in df.columns:
            clean_c = c.replace('_', ' ').replace('-', ' ').strip().lower().replace(' ', '_')
            if clean_c in possible_cols or c in possible_cols:
                return c
        return None

    phone_col = find_col(phone_cols)
    name_col = find_col(name_cols)
    truck_col = find_col(truck_cols)
    active_col = find_col(active_cols)

    if not phone_col:
        raise ValueError("Could not find a phone number column in the file. Please ensure there is a column named 'Phone Number' or 'Mobile'.")

    customers_data = []
    for _, row in df.iterrows():
        val_phone = row[phone_col]
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

        name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else None
        # Clean string formats for name/truck
        if name == 'nan' or name == 'None':
            name = None
        
        truck = str(row[truck_col]).strip() if truck_col and pd.notna(row[truck_col]) else None
        if truck == 'nan' or truck == 'None':
            truck = None

        is_active = True
        if active_col and pd.notna(row[active_col]):
            val_active = str(row[active_col]).strip().lower()
            if val_active in ('false', '0', 'no', 'n', 'inactive', 'off'):
                is_active = False

        customers_data.append({
            'phone_number': phone,
            'owner_name': name,
            'truck_number': truck,
            'is_active': is_active
        })
    return customers_data


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
        raise ValueError("PHONE_NUMBER_ID and WHATSAPP_TOKEN must be configured in environment.")

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/media"
    headers = {
        "Authorization": f"Bearer {whatsapp_token}"
    }

    file_name = None
    file_obj = None
    mime_type = "image/jpeg"  # Default fallback

    # Check if it's a Django FieldFile or File object (it will have open method and name)
    if hasattr(file_path_or_field, "name") and hasattr(file_path_or_field, "open"):
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
            raise FileNotFoundError(f"File not found on local disk: {file_path_or_field}")
        file_name = os.path.basename(file_path_or_field)
        guess = mimetypes.guess_type(file_name)[0]
        if guess:
            mime_type = guess
        file_obj = open(file_path_or_field, "rb")
    else:
        raise TypeError("file_path_or_field must be a string file path or a Django File/FieldFile object.")

    try:
        files = {
            "messaging_product": (None, "whatsapp"),
            "file": (file_name, file_obj, mime_type),
            "type": (None, mime_type)
        }
        response = requests.post(url, headers=headers, files=files, timeout=30)
        
        if response.status_code == 200:
            media_id = response.json().get("id")
            if not media_id:
                raise Exception("Response did not contain media ID.")
            return media_id
        else:
            raise Exception(f"Meta API returned status code {response.status_code}: {response.text}")
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
