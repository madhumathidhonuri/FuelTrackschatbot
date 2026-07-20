
import re

# Fix bot/views.py
with open("bot/views.py", "r", encoding="utf-8") as f:
    content = f.read()

target = """                        if message_obj.get("type") in ["text", "interactive", "button"]:
                            if message_obj.get("type") == "text":
                                user_text = message_obj["text"].get("body", "")
                            elif message_obj.get("type") == "button":
                                user_text = message_obj.get("button", {}).get("text", "")
                                if not user_text and message_obj.get("button", {}).get("payload"):
                                    user_text = message_obj.get("button", {}).get("payload", "")
                            else:
                                interactive_type = message_obj["interactive"].get("type", "")
                                if interactive_type == "button_reply":
                                    user_text = message_obj["interactive"]["button_reply"].get("title", "")
                                elif interactive_type == "list_reply":
                                    user_text = message_obj["interactive"]["list_reply"].get("title", "")
                            else:
                                user_text = ""

                        if not user_text.strip():"""

replacement = """                        if message_obj.get("type") in ["text", "interactive", "button"]:
                            if message_obj.get("type") == "text":
                                user_text = message_obj["text"].get("body", "")
                            elif message_obj.get("type") == "button":
                                user_text = message_obj.get("button", {}).get("text", "")
                                if not user_text and message_obj.get("button", {}).get("payload"):
                                    user_text = message_obj.get("button", {}).get("payload", "")
                            else:
                                interactive_type = message_obj["interactive"].get("type", "")
                                if interactive_type == "button_reply":
                                    user_text = message_obj["interactive"]["button_reply"].get("title", "")
                                elif interactive_type == "list_reply":
                                    user_text = message_obj["interactive"]["list_reply"].get("title", "")
                                else:
                                    user_text = ""
                        elif message_obj.get("type") in ["audio", "image", "video", "document"]:
                            media_type = message_obj.get("type")
                            user_text = f"[{media_type.capitalize()} Message Received]"
                        else:
                            user_text = ""

                        if not user_text.strip():"""

content = content.replace(target, replacement)
with open("bot/views.py", "w", encoding="utf-8") as f:
    f.write(content)

# Fix bot/admin.py audio conversion
with open("bot/admin.py", "r", encoding="utf-8") as f:
    content_admin = f.read()

target_admin = """            # Step 1: Upload media to Meta
            url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/media"
            headers = {
                "Authorization": f"Bearer {WHATSAPP_TOKEN}"
            }
            # We must pass messaging_product as a regular field, and the file as the file field
            files = {
                'file': (file_name, upload_file.read(), content_type)
            }
            data = {
                'messaging_product': 'whatsapp'
            }
            
            try:
                upload_res = requests.post(url, headers=headers, files=files, data=data)"""

replacement_admin = """            import tempfile
            import imageio_ffmpeg
            import subprocess

            converted_file_path = None
            if media_type == 'audio':
                try:
                    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_webm:
                        temp_webm.write(upload_file.read())
                        temp_webm_path = temp_webm.name
                    
                    converted_file_path = temp_webm_path.replace(".webm", ".mp4")
                    subprocess.run([
                        ffmpeg_exe, "-y", "-i", temp_webm_path, "-c:a", "aac", "-b:a", "128k", converted_file_path
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    file_name = file_name.replace(".webm", ".mp4").replace(".mp4", "") + ".mp4"
                    content_type = "audio/mp4"
                    with open(converted_file_path, "rb") as f:
                        file_data = f.read()
                        
                    os.remove(temp_webm_path)
                except Exception as e:
                    print(f"Audio conversion failed: {e}")
                    upload_file.seek(0)
                    file_data = upload_file.read()
            else:
                file_data = upload_file.read()

            # Step 1: Upload media to Meta
            url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/media"
            headers = {
                "Authorization": f"Bearer {WHATSAPP_TOKEN}"
            }
            # We must pass messaging_product as a regular field, and the file as the file field
            files = {
                'file': (file_name, file_data, content_type)
            }
            data = {
                'messaging_product': 'whatsapp'
            }
            
            try:
                upload_res = requests.post(url, headers=headers, files=files, data=data)"""

content_admin = content_admin.replace(target_admin, replacement_admin)

target_admin_cleanup = """            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})

            # Step 3: Log in chat history"""

replacement_admin_cleanup = """            except Exception as e:
                return JsonResponse({"success": False, "error": str(e)})
            finally:
                if converted_file_path and os.path.exists(converted_file_path):
                    os.remove(converted_file_path)

            # Step 3: Log in chat history"""

content_admin = content_admin.replace(target_admin_cleanup, replacement_admin_cleanup)

with open("bot/admin.py", "w", encoding="utf-8") as f:
    f.write(content_admin)
