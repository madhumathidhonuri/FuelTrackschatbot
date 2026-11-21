from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from bot.models import FleetCustomer, ChatMessage
import json


class HardwareDiagnosticsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.webhook_url = reverse("whatsapp_webhook")

    @patch("threading.Thread")
    @patch("os.getenv")
    @patch("bot.utils.download_media_from_meta")
    def test_image_diagnostics_flow_triggers_thread(self, mock_download, mock_getenv, mock_thread):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "1218529308003610",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_download.return_value = "/media/incoming_media/test_device.jpg"

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1058407473197676",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15550234567",
                                    "phone_number_id": "1218529308003610"
                                },
                                "contacts": [{"profile": {"name": "Test Customer"}, "wa_id": "919876543210"}],
                                "messages": [
                                    {
                                        "from": "919876543210",
                                        "id": "wamid_img_123",
                                        "timestamp": "1732000000",
                                        "type": "image",
                                        "image": {
                                            "id": "media_id_999",
                                            "mime_type": "image/jpeg",
                                            "caption": "Why is my device not tracking?"
                                        }
                                    }
                                ]
                            },
                            "field": "messages"
                        }
                    ]
                }
            ]
        }

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(payload),
            content_type="application/json"
        )

        # Meta receives instant 200 OK without timeout
        self.assertEqual(response.status_code, 200)
        # Background worker thread was spawned
        mock_thread.assert_called_once()
        self.assertTrue(mock_thread.return_value.start.called)

    @patch("bot.views.notify_agents")
    @patch("bot.views.send_whatsapp_message")
    @patch("bot.hardware_service.diagnose_hardware_image")
    def test_process_visual_media_background_image(self, mock_diagnose, mock_send, mock_notify):
        from bot.views import process_visual_media_background
        mock_diagnose.return_value = (
            "🔍 *Hardware Identified:* GPS Tracker\n"
            "💡 *Diagnostic Status & Issue:* Red LED is Solid (Power OK), Blue is Blinking (Searching GPS).\n"
            "🛠️ *How to Solve:*\n• Step 1: Move vehicle into open sky."
        )
        mock_send.return_value = "wamid_diag_test"

        process_visual_media_background(
            user_phone="919876543210",
            media_type="image",
            media_url="/media/incoming_media/test_device.jpg",
            caption="Check my tracker",
            domain_url="https://whatsapp-ai-bot-dqot.onrender.com",
            customer_name="Test Customer"
        )

        mock_diagnose.assert_called_once()
        mock_send.assert_called_once()
        self.assertIn("Hardware Identified", mock_send.call_args[0][1])
        mock_notify.assert_called_once()
        self.assertIn("Hardware Visual Diagnostic Alert", mock_notify.call_args[0][0])
        assistant_msgs = ChatMessage.objects.filter(phone_number="919876543210", role="assistant")
        self.assertTrue(assistant_msgs.exists())

    @patch("bot.views.notify_agents")
    @patch("bot.views.send_whatsapp_message")
    @patch("bot.hardware_service.diagnose_hardware_video")
    def test_process_visual_media_background_video(self, mock_diagnose_vid, mock_send, mock_notify):
        from bot.views import process_visual_media_background
        mock_diagnose_vid.return_value = (
            "🔍 *Hardware Identified:* GPS Tracker\n"
            "💡 *Diagnostic Status & Issue:* Green GSM LED is fast blinking across video frames.\n"
            "🛠️ *How to Solve:*\n• Step 1: Check SIM balance."
        )
        mock_send.return_value = "wamid_vid_test"

        process_visual_media_background(
            user_phone="919999888877",
            media_type="video",
            media_url="/media/incoming_media/test_device.mp4",
            caption="See video lights",
            domain_url="https://whatsapp-ai-bot-dqot.onrender.com",
            customer_name="Video Customer"
        )

        mock_diagnose_vid.assert_called_once()
        mock_send.assert_called_once()
        self.assertIn("Green GSM LED", mock_send.call_args[0][1])
        mock_notify.assert_called_once()
        self.assertIn("VIDEO", mock_notify.call_args[0][0])
        assistant_msgs = ChatMessage.objects.filter(phone_number="919999888877", role="assistant")
        self.assertTrue(assistant_msgs.exists())

    @patch("os.getenv")
    @patch("bot.views.send_whatsapp_message")
    @patch("bot.utils.download_media_from_meta")
    @patch("bot.hardware_service.transcribe_voice_note")
    def test_voice_note_transcription_flow(self, mock_transcribe, mock_download, mock_send, mock_getenv):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "1218529308003610",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_download.return_value = "/media/incoming_media/test_voice.mp3"
        mock_transcribe.return_value = "Where is my truck AP 09 BX 1234"
        mock_send.return_value = "wamid_voice_test"

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1058407473197676",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15550234567",
                                    "phone_number_id": "1218529308003610"
                                },
                                "contacts": [{"profile": {"name": "Driver Voice"}, "wa_id": "918888777766"}],
                                "messages": [
                                    {
                                        "from": "918888777766",
                                        "id": "wamid_audio_123",
                                        "timestamp": "1732000000",
                                        "type": "audio",
                                        "audio": {
                                            "id": "media_audio_999",
                                            "mime_type": "audio/ogg"
                                        }
                                    }
                                ]
                            },
                            "field": "messages"
                        }
                    ]
                }
            ]
        }

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        mock_transcribe.assert_called_once()
        user_msg = ChatMessage.objects.filter(phone_number="918888777766", role="user").first()
        self.assertIsNotNone(user_msg)
        self.assertEqual(user_msg.content, "Where is my truck AP 09 BX 1234")

    @patch("os.getenv")
    @patch("bot.views.send_whatsapp_message")
    @patch("bot.hardware_service.get_vehicle_live_status")
    def test_vehicle_location_lookup_flow(self, mock_get_status, mock_send, mock_getenv):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "1218529308003610",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_get_status.return_value = (
            "🚛 *Vehicle: AP 09 BX 1234*\n"
            "• *Current Status:* 🟢 *Moving* (54 km/h)\n"
            "📍 *Live Google Maps:* https://maps.google.com/?q=17.385,78.486"
        )
        mock_send.return_value = "wamid_loc_test"

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1058407473197676",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "15550234567",
                                    "phone_number_id": "1218529308003610"
                                },
                                "contacts": [{"profile": {"name": "Fleet Owner"}, "wa_id": "917777666655"}],
                                "messages": [
                                    {
                                        "from": "917777666655",
                                        "id": "wamid_txt_123",
                                        "timestamp": "1732000000",
                                        "type": "text",
                                        "text": {
                                            "body": "Track AP 09 BX 1234"
                                        }
                                    }
                                ]
                            },
                            "field": "messages"
                        }
                    ]
                }
            ]
        }

        response = self.client.post(
            self.webhook_url,
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        mock_get_status.assert_called_once()
        mock_send.assert_called_once()
        self.assertIn("Moving", mock_send.call_args[0][1])
        assistant_msg = ChatMessage.objects.filter(phone_number="917777666655", role="assistant").first()
        self.assertIsNotNone(assistant_msg)
        self.assertIn("AP 09 BX 1234", assistant_msg.content)
