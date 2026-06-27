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
    truck_cols = ['truck_number', 'vehicle_number', 'truck', 'vehicle', 'truck_no', 'vehicle_no']
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
