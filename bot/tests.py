from django.test import TestCase, Client
from unittest.mock import patch, MagicMock
from django.urls import reverse
from bot.models import FleetCustomer, ChatMessage
import json
import os

class WebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Clean database state before test
        FleetCustomer.objects.all().delete()
        ChatMessage.objects.all().delete()
        
        # Create standard customer
        self.customer = FleetCustomer.objects.create(
            phone_number="1234567890",
            owner_name="Test Customer",
            is_active=True
        )

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_ais_140_query(self, mock_getenv, mock_groq, mock_post):
        # Prevent signature check and set API keys/vars
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        # Mock Groq client completion responses
        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Here is some info about AIS 140 tracker."))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion

        # Mock response from Meta
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Payload representing an AIS 140 query
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "1234567890",
                                        "id": "msg_ais_140",
                                        "type": "text",
                                        "text": {"body": "Can you tell me about the AIS 140 GPS tracker?"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 200)

        # We expect 2 calls: one for the AI text explanation, and one for the catalog document.
        self.assertEqual(mock_post.call_count, 2)
        
        # Verify AI explanation sent
        _, kwargs_explanation = mock_post.call_args_list[0]
        self.assertEqual(kwargs_explanation["json"]["type"], "text")
        self.assertEqual(kwargs_explanation["json"]["text"]["body"], "Here is some info about AIS 140 tracker.")

        # Verify AIS 140 Catalog sent
        _, kwargs_catalog = mock_post.call_args_list[1]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "AIS_140_GPS_Tracker_Catalog.pdf")
        self.assertEqual(kwargs_catalog["json"]["document"]["caption"], "Here is the AIS 140 GPS Tracker Catalog: 📄")

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_fuel_monitoring_query(self, mock_getenv, mock_groq, mock_post):
        # Prevent signature check
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        # Mock Groq client completion responses
        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Here is some info about our Smart Fuel monitoring sensor."))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion

        # Mock response from Meta
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Payload representing a fuel sensor query
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "1234567890",
                                        "id": "msg_fuel_sensor",
                                        "type": "text",
                                        "text": {"body": "How does the fuel monitoring sensor work?"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 200)

        # We expect 2 calls: one for the AI text explanation, and one for the catalog document.
        self.assertEqual(mock_post.call_count, 2)

        # Verify AI explanation sent
        _, kwargs_explanation = mock_post.call_args_list[0]
        self.assertEqual(kwargs_explanation["json"]["type"], "text")
        self.assertEqual(kwargs_explanation["json"]["text"]["body"], "Here is some info about our Smart Fuel monitoring sensor.")

        # Verify Fuel Monitoring Catalog sent
        _, kwargs_catalog = mock_post.call_args_list[1]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "Smart_Fuel_Monitoring_Catalog.pdf")
        self.assertEqual(kwargs_catalog["json"]["document"]["caption"], "Here is the Smart Fuel Monitoring Catalog: 📄")

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_general_query(self, mock_getenv, mock_groq, mock_post):
        # Prevent signature check
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        # Mock Groq client completion responses
        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Hello! How can I help you today?"))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion

        # Mock response from Meta
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Payload representing a general query (no specific device keywords)
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "1234567890",
                                        "id": "msg_general",
                                        "type": "text",
                                        "text": {"body": "Hello"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 200)

        # We expect only 1 call for the general message reply, and NO catalogs.
        self.assertEqual(mock_post.call_count, 1)
        _, kwargs_explanation = mock_post.call_args_list[0]
        self.assertEqual(kwargs_explanation["json"]["type"], "text")
        self.assertEqual(kwargs_explanation["json"]["text"]["body"], "Hello! How can I help you today?")

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_location_tracker_telugu_query_bypass(self, mock_getenv, mock_groq, mock_post):
        # Prevent signature check
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        # Mock Groq client completion responses
        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="అవును, మేము ప్రభుత్వ ఆమోదం పొందిన లొకేషన్ ట్రాకర్లను అందిస్తాము."))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion

        # Mock response from Meta
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Payload representing "గవర్నమెంట్ ఆమోదించిన లొకేషన్ ట్రాకర్లు లభిస్తాయా?" (Do you get government-approved location trackers?)
        # It contains "లొకేషన్" (which triggers location) but also "ట్రాకర్లు" (device trigger), so it should bypass office location pin!
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "1234567890",
                                        "id": "msg_bypass",
                                        "type": "text",
                                        "text": {"body": "గవర్నమెంట్ ఆమోదించిన లొకేషన్ ట్రాకర్లు లభిస్తాయా?"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 200)

        # We expect 2 calls: one for AI explanation and one for the AIS 140 catalog PDF.
        # It should NOT send the office location coordinate map pin!
        self.assertEqual(mock_post.call_count, 2)
        
        # Verify AI explanation sent (Telugu)
        _, kwargs_explanation = mock_post.call_args_list[0]
        self.assertEqual(kwargs_explanation["json"]["type"], "text")
        self.assertEqual(kwargs_explanation["json"]["text"]["body"], "అవును, మేము ప్రభుత్వ ఆమోదం పొందిన లొకేషన్ ట్రాకర్లను అందిస్తాము.")

        # Verify AIS 140 Catalog sent (Telugu caption because of Telugu script in user query)
        _, kwargs_catalog = mock_post.call_args_list[1]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "AIS_140_GPS_Tracker_Catalog.pdf")
        self.assertEqual(kwargs_catalog["json"]["document"]["caption"], "ఇదిగోండి AIS 140 GPS ట్రాకర్ కేటలాగ్: 📄")

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_gratitude_query(self, mock_getenv, mock_groq, mock_post):
        # Prevent signature check
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        # Mock Groq client completion responses
        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Thank you for contacting Fuel Tracks Technologies, Test Customer garu. Have a great day ahead!"))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion

        # Mock response from Meta
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Payload representing "Thank you"
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "1234567890",
                                        "id": "msg_gratitude",
                                        "type": "text",
                                        "text": {"body": "Thank you"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload),
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 200)

        # We expect only 1 call for the polite closing message reply, and NO off-topic redirect or catalogs.
        self.assertEqual(mock_post.call_count, 1)
        _, kwargs_explanation = mock_post.call_args_list[0]
        self.assertEqual(kwargs_explanation["json"]["type"], "text")
        self.assertEqual(kwargs_explanation["json"]["text"]["body"], "Thank you for contacting Fuel Tracks Technologies, Test Customer garu. Have a great day ahead!")
