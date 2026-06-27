import os
import sys

def main():
    source_pdf = r"C:\Users\madhu\.gemini\antigravity-ide\brain\abd12405-89a0-4fc6-a784-dba24acd88ce\media__1782546031137.pdf"
    output_dir = r"e:\whatsapp_ai_bot\media"

    if not os.path.exists(source_pdf):
        print(f"Error: Source PDF not found at {source_pdf}")
        sys.exit(1)

    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        print("Error: pypdf is not installed. Please install it using pip install pypdf")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    reader = PdfReader(source_pdf)
    total_pages = len(reader.pages)
    print(f"Total pages in source: {total_pages}")

    def extract_pages(pages_list, output_filename):
        writer = PdfWriter()
        for p_num in pages_list:
            # p_num is 1-indexed, convert to 0-indexed
            idx = p_num - 1
            if 0 <= idx < total_pages:
                writer.add_page(reader.pages[idx])
            else:
                print(f"Warning: Page {p_num} is out of range.")
        out_path = os.path.join(output_dir, output_filename)
        with open(out_path, "wb") as f:
            writer.write(f)
        print(f"Successfully created: {out_path} with {len(pages_list)} pages.")

    # 1. Fuel_Tracks_Catalog.pdf (Full 21 pages)
    extract_pages(list(range(1, 22)), "Fuel_Tracks_Catalog.pdf")

    # 2. AIS_140_GPS_Tracker_Catalog.pdf (Pages: 1, 2, 3, 4, 8)
    extract_pages([1, 2, 3, 4, 8], "AIS_140_GPS_Tracker_Catalog.pdf")

    # 3. Smart_Fuel_Monitoring_Catalog.pdf (Pages: 1, 5, 6, 7, 11)
    extract_pages([1, 5, 6, 7, 11], "Smart_Fuel_Monitoring_Catalog.pdf")

    # 4. Wifi_Camera_Catalog.pdf (Pages: 1, 14, 17)
    extract_pages([1, 14, 17], "Wifi_Camera_Catalog.pdf")

    # 5. Solar_Cam_Catalog.pdf (Pages: 1, 12)
    extract_pages([1, 12], "Solar_Cam_Catalog.pdf")

    # 6. Dash_Cam_Catalog.pdf (Pages: 1, 13, 15)
    extract_pages([1, 13, 15], "Dash_Cam_Catalog.pdf")

    # 7. PTZ_Camera_Catalog.pdf (Pages: 1, 16)
    extract_pages([1, 16], "PTZ_Camera_Catalog.pdf")

    # 8. Borewell_Rod_Count_Catalog.pdf (Pages: 1, 9)
    extract_pages([1, 9], "Borewell_Rod_Count_Catalog.pdf")

    # 9. Borewell_RPM_Count_Catalog.pdf (Pages: 1, 10)
    extract_pages([1, 10], "Borewell_RPM_Count_Catalog.pdf")

    # 10. AC_Temperature_Sensor_Catalog.pdf (Pages: 1, 18)
    extract_pages([1, 18], "AC_Temperature_Sensor_Catalog.pdf")

    # 11. Car_LCD_Monitor_Catalog.pdf (Pages: 1, 19, 20)
    extract_pages([1, 19, 20], "Car_LCD_Monitor_Catalog.pdf")

    # 12. Relay_Cutoff_Switch_Catalog.pdf (Pages: 1, 21)
    extract_pages([1, 21], "Relay_Cutoff_Switch_Catalog.pdf")

if __name__ == "__main__":
    main()
