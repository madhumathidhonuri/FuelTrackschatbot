from django.test import TestCase, Client
from unittest.mock import patch, MagicMock
from django.urls import reverse
from bot.models import FleetCustomer, ChatMessage, AdCampaign, WhatsAppTemplate
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

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_contact_hijack_how_can_i_contact(self, mock_getenv, mock_groq, mock_post):
        # Prevent signature check
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        # Mock response from Meta
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Payload representing "How can I contact"
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
                                        "id": "msg_contact_hijack",
                                        "type": "text",
                                        "text": {"body": "How can I contact"}
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

        # We expect 2 calls: one for handoff_intro, one for the contact card.
        self.assertEqual(mock_post.call_count, 2)
        
        _, kwargs_intro = mock_post.call_args_list[0]
        self.assertEqual(kwargs_intro["json"]["type"], "text")
        self.assertIn("Technical Sales Expert", kwargs_intro["json"]["text"]["body"])

        _, kwargs_card = mock_post.call_args_list[1]
        self.assertEqual(kwargs_card["json"]["type"], "contacts")

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_ask_name_flow(self, mock_getenv, mock_groq, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        # Mock response from Meta
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Use a new phone number that doesn't exist in database
        new_phone = "9876543210"
        
        # 1. First message should trigger name request
        payload_1 = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"messages": [{"from": new_phone, "id": "msg_1", "type": "text", "text": {"body": "Hello"}}]}}]}]
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload_1),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_count, 2)
        
        # First call is the interactive welcome menu
        _, kwargs_welcome = mock_post.call_args_list[0]
        self.assertEqual(kwargs_welcome["json"]["type"], "interactive")
        self.assertEqual(kwargs_welcome["json"]["interactive"]["type"], "button")
        
        # Second call is the text prompt asking for the name
        _, kwargs_name_req = mock_post.call_args_list[1]
        self.assertEqual(kwargs_name_req["json"]["type"], "text")
        self.assertIn("May I know your name, please?", kwargs_name_req["json"]["text"]["body"])

        # Reset mocks
        mock_post.reset_mock()
        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        # Mock details extraction to return Madhu
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content='{"name": "Madhu", "truck_number": null}'))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion

        # 2. Second message giving name should set it and show welcome menu with buttons
        payload_2 = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"messages": [{"from": new_phone, "id": "msg_2", "type": "text", "text": {"body": "Madhu"}}]}}]}]
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload_2),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify customer's name is saved
        customer = FleetCustomer.objects.get(phone_number=new_phone)
        self.assertEqual(customer.owner_name, "Madhu")

        # Verify friendly text reply was sent
        self.assertEqual(mock_post.call_count, 1)
        _, kwargs_reply = mock_post.call_args_list[0]
        self.assertEqual(kwargs_reply["json"]["type"], "text")
        self.assertIn("Thank you, Madhu garu!", kwargs_reply["json"]["text"]["body"])

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_general_products_catalog(self, mock_getenv, mock_groq, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Here are our products: AIS 140 GPS tracker and Smart Fuel Monitoring."))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Payload asking "What are your products"
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
                                        "id": "msg_general_products",
                                        "type": "text",
                                        "text": {"body": "What are your products"}
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

        # We expect 2 calls: AI response (text) and the general catalog (document)
        self.assertEqual(mock_post.call_count, 2)

        _, kwargs_explanation = mock_post.call_args_list[0]
        self.assertEqual(kwargs_explanation["json"]["type"], "text")
        self.assertEqual(kwargs_explanation["json"]["text"]["body"], "Here are our products: AIS 140 GPS tracker and Smart Fuel Monitoring.")

        _, kwargs_catalog = mock_post.call_args_list[1]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "Fuel_Tracks_Catalog.pdf")

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_multiline_button_reply(self, mock_getenv, mock_groq, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Payload representing a copy-pasted/forwarded welcome menu button click (with "Products")
        multiline_body = (
            "Welcome to Fuel Tracks Technologies Private Limited! \n\n"
            "We are India's trusted provider of high-end GPS Tracking Systems, "
            "AIS 140 Certified Devices, and Smart Fuel Monitoring Solutions.\n\n"
            "How can we help your business today? Select an option below:\n"
            "Products"
        )
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
                                        "id": "msg_multiline_button",
                                        "type": "text",
                                        "text": {"body": multiline_body}
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

        # We expect 1 call: sending the main Fuel Tracks Catalog PDF
        self.assertEqual(mock_post.call_count, 1)

        _, kwargs_catalog = mock_post.call_args_list[0]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "Fuel_Tracks_Catalog.pdf")
        self.assertEqual(kwargs_catalog["json"]["document"]["caption"], "Here is our official Fuel Tracks Product Catalog Guide! 📄")

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_device_catalog_match_direct(self, mock_getenv, mock_groq, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_chat = mock_groq.return_value.chat.completions.create
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="We have the Teltonika FMB120 which is an AIS 140 certified GPS tracker."))
        ]
        mock_chat.return_value = mock_response

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post.return_value = mock_post_resp

        # Set customer name first so it doesn't prompt for name
        self.customer.owner_name = "Test User"
        self.customer.save()

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
                                        "id": "msg_direct_device",
                                        "type": "text",
                                        "text": {"body": "Teltonika FMB120"}
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

        # We expect 2 calls: AI response (text) and catalog (document)
        self.assertEqual(mock_post.call_count, 2)
        _, kwargs_catalog = mock_post.call_args_list[1]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "AIS_140_GPS_Tracker_Catalog.pdf")

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_device_catalog_match_history(self, mock_getenv, mock_groq, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_chat = mock_groq.return_value.chat.completions.create
        
        mock_response_1 = MagicMock()
        mock_response_1.choices = [
            MagicMock(message=MagicMock(content="We have the solar security camera with high resolution."))
        ]
        
        mock_response_2 = MagicMock()
        mock_response_2.choices = [
            MagicMock(message=MagicMock(content="Here is the PDF for the solar camera."))
        ]
        
        mock_chat.side_effect = [mock_response_1, mock_response_2]

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post.return_value = mock_post_resp

        # Set customer name first
        self.customer.owner_name = "Test User"
        self.customer.save()

        # 1. Send first message discussing solar camera
        payload_1 = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "1234567890",
                                        "id": "msg_history_1",
                                        "type": "text",
                                        "text": {"body": "Tell me about the solar camera"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        self.client.post(reverse("whatsapp_webhook"), data=json.dumps(payload_1), content_type="application/json")

        # 2. Send generic "Send pdf" message
        mock_post.reset_mock()
        payload_2 = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "1234567890",
                                        "id": "msg_history_2",
                                        "type": "text",
                                        "text": {"body": "Send pdf"}
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        response = self.client.post(reverse("whatsapp_webhook"), data=json.dumps(payload_2), content_type="application/json")
        self.assertEqual(response.status_code, 200)

        # The generic query should result in sending Solar_Cam_Catalog.pdf based on history
        _, kwargs_catalog = mock_post.call_args_list[1]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "Solar_Cam_Catalog.pdf")

    def test_export_customers_excel(self):
        # Create some test customers
        FleetCustomer.objects.all().delete()
        FleetCustomer.objects.create(phone_number="919000666914", owner_name="Ravi Teja", truck_number="TS09EX1234", is_active=True)
        FleetCustomer.objects.create(phone_number="919999999999", owner_name="Suresh Kumar", truck_number=None, is_active=False)

        response = self.client.get(reverse("export_customers_excel"))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment; filename="customers.csv"', response['Content-Disposition'])
        
        # Decode the CSV content
        content = response.content.decode('utf-8')
        
        # Check that it starts with the BOM and contains the correct headers and content
        self.assertTrue(content.startswith('\ufeff'))
        
        # Strip BOM for easier checking
        clean_content = content.lstrip('\ufeff')
        
        # Split rows
        import csv
        import io
        reader = csv.reader(io.StringIO(clean_content))
        rows = list(reader)
        
        self.assertEqual(len(rows), 3) # Header + 2 data rows
        self.assertEqual(rows[0], ['Phone Number', 'Customer Name', 'Truck Number', 'Is Active', 'Date Created'])
        
        # Find which row is Suresh and which is Ravi
        suresh_row = next(r for r in rows if r[0] == '="919999999999"')
        ravi_row = next(r for r in rows if r[0] == '="919000666914"')
        
        self.assertEqual(suresh_row[1], "Suresh Kumar")
        self.assertEqual(suresh_row[2], "")
        self.assertEqual(suresh_row[3], "No")
        
        self.assertEqual(ravi_row[1], "Ravi Teja")
        self.assertEqual(ravi_row[2], "TS09EX1234")
        self.assertEqual(ravi_row[3], "Yes")

    def test_serve_catalog_success(self):
        for filename in ["Fuel_Tracks_Catalog.pdf", "AIS_140_GPS_Tracker_Catalog.pdf", 
                         "Smart_Fuel_Monitoring_Catalog.pdf", "Wifi_Camera_Catalog.pdf",
                         "Solar_Cam_Catalog.pdf", "Dash_Cam_Catalog.pdf", "PTZ_Camera_Catalog.pdf",
                         "Borewell_Rod_Count_Catalog.pdf", "Borewell_RPM_Count_Catalog.pdf",
                         "AC_Temperature_Sensor_Catalog.pdf", "Car_LCD_Monitor_Catalog.pdf",
                         "Relay_Cutoff_Switch_Catalog.pdf"]:
            response = self.client.get(reverse("serve_catalog", kwargs={"filename": filename}))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_serve_catalog_not_found(self):
        response = self.client.get(reverse("serve_catalog", kwargs={"filename": "non_existent_catalog.pdf"}))
        self.assertEqual(response.status_code, 404)

    def test_serve_catalog_invalid_name(self):
        response = self.client.get(reverse("serve_catalog", kwargs={"filename": "invalid_file_name.txt"}))
        self.assertEqual(response.status_code, 404)

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_camera_query(self, mock_getenv, mock_groq, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Here is some info about the Wifi Camera."))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

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
                                        "id": "msg_camera",
                                        "type": "text",
                                        "text": {"body": "Tell me about the wifi camera"}
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
        self.assertEqual(mock_post.call_count, 2)

        _, kwargs_catalog = mock_post.call_args_list[1]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "Wifi_Camera_Catalog.pdf")

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_borewell_query(self, mock_getenv, mock_groq, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Here is some info about the Borewell Rod count."))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

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
                                        "id": "msg_borewell",
                                        "type": "text",
                                        "text": {"body": "borewell rod count solution"}
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
        self.assertEqual(mock_post.call_count, 2)

        _, kwargs_catalog = mock_post.call_args_list[1]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "Borewell_Rod_Count_Catalog.pdf")

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_webhook_accessory_query(self, mock_getenv, mock_groq, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Here is some info about AC Temperature sensor."))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

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
                                        "id": "msg_accessory",
                                        "type": "text",
                                        "text": {"body": "what about ac temperature sensor"}
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
        self.assertEqual(mock_post.call_count, 2)

        _, kwargs_catalog = mock_post.call_args_list[1]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "AC_Temperature_Sensor_Catalog.pdf")


class ExcelUploadAndBroadcastTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123'
        )
        self.client.login(username='admin', password='password123')
        FleetCustomer.objects.all().delete()
        
    def test_parse_csv(self):
        import io
        from bot.utils import parse_excel_or_csv
        csv_data = "Phone Number,Customer Name,Truck Number,Is Active\n918888888888,John Doe,TRUCK123,yes\n917777777777,Jane Smith,TRUCK456,no\n"
        csv_file = io.StringIO(csv_data)
        parsed = parse_excel_or_csv(csv_file, filename="test.csv")
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]['phone_number'], '918888888888')
        self.assertEqual(parsed[0]['owner_name'], 'John Doe')
        self.assertEqual(parsed[0]['truck_number'], 'TRUCK123')
        self.assertTrue(parsed[0]['is_active'])
        
        self.assertEqual(parsed[1]['phone_number'], '917777777777')
        self.assertEqual(parsed[1]['owner_name'], 'Jane Smith')
        self.assertEqual(parsed[1]['truck_number'], 'TRUCK456')
        self.assertFalse(parsed[1]['is_active'])

    def test_parse_excel(self):
        import io
        import pandas as pd
        from bot.utils import parse_excel_or_csv
        df = pd.DataFrame({
            'Phone Number': ['916666666666', '915555555555'],
            'Customer Name': ['Bob Ross', 'Alice Cooper'],
            'Truck Number': ['TRUCK789', None],
            'Is Active': ['yes', 'no']
        })
        excel_io = io.BytesIO()
        df.to_excel(excel_io, index=False)
        excel_io.seek(0)
        parsed = parse_excel_or_csv(excel_io, filename="test.xlsx")
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]['phone_number'], '916666666666')
        self.assertEqual(parsed[0]['owner_name'], 'Bob Ross')
        self.assertEqual(parsed[0]['truck_number'], 'TRUCK789')
        self.assertTrue(parsed[0]['is_active'])
        
        self.assertEqual(parsed[1]['phone_number'], '915555555555')
        self.assertEqual(parsed[1]['owner_name'], 'Alice Cooper')
        self.assertIsNone(parsed[1]['truck_number'])
        self.assertFalse(parsed[1]['is_active'])

    def test_admin_upload_csv(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        csv_data = "Phone Number,Customer Name,Truck Number,Is Active\n918888888888,John Doe,TRUCK123,yes\n"
        uploaded_file = SimpleUploadedFile("test_list.csv", csv_data.encode('utf-8'), content_type="text/csv")
        
        response = self.client.post(
            reverse("admin:bot_fleetcustomer_upload_excel"),
            {"excel_file": uploaded_file}
        )
        self.assertEqual(response.status_code, 302) # Redirects back to changelist
        
        # Verify customer was imported to database
        self.assertTrue(FleetCustomer.objects.filter(phone_number="918888888888").exists())
        customer = FleetCustomer.objects.get(phone_number="918888888888")
        self.assertEqual(customer.owner_name, "John Doe")
        self.assertEqual(customer.truck_number, "TRUCK123")
        self.assertTrue(customer.is_active)

    @patch("bot.broadcast.requests.post")
    def test_run_massive_broadcast_with_file(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        from bot.broadcast import run_massive_broadcast
        
        # Create a CSV file
        csv_data = "Phone Number,Customer Name,Truck Number,Is Active\n914444444444,Target User,TRUCK999,yes\n"
        csv_file_path = "media/test_broadcast_list.csv"
        # Ensure media directory exists
        os.makedirs("media", exist_ok=True)
        with open(csv_file_path, "w") as f:
            f.write(csv_data)
            
        try:
            # Let's run the broadcast targeting this CSV file
            run_massive_broadcast("hello_world", "en", csv_file_path)
            
            # Verify the mock post was called once for the customer in the file
            self.assertEqual(mock_post.call_count, 1)
            _, kwargs = mock_post.call_args
            self.assertEqual(kwargs["json"]["to"], "914444444444")
            self.assertEqual(kwargs["json"]["template"]["name"], "hello_world")
        finally:
            if os.path.exists(csv_file_path):
                os.remove(csv_file_path)

    @patch("bot.broadcast.requests.post")
    def test_send_whatsapp_template_en_fallback(self, mock_post):
        from bot.broadcast import send_whatsapp_template
        import copy
        
        # Define mock responses
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 404
        mock_response_fail.json.return_value = {
            "error": {
                "message": "(#132001) Template name does not exist in the translation",
                "code": 132001,
                "type": "OAuthException"
            }
        }
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.text = '{"success": true}'
        
        # Capture deep copies of call payloads to avoid mutation-in-place issues in mock call history
        call_payloads = []
        def side_effect(*args, **kwargs):
            call_payloads.append(copy.deepcopy(kwargs.get("json")))
            if len(call_payloads) == 1:
                return mock_response_fail
            return mock_response_success
            
        mock_post.side_effect = side_effect
        
        # Call send_whatsapp_template with language_code='en'
        success, error = send_whatsapp_template(
            to_phone="919999999999",
            template_name="gps_tracking_device",
            language_code="en"
        )
        
        # Verify success and calls
        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(mock_post.call_count, 2)
        
        # First call has 'en'
        self.assertEqual(call_payloads[0]["template"]["language"]["code"], "en")
        
        # Second call has 'en_US'
        self.assertEqual(call_payloads[1]["template"]["language"]["code"], "en_US")


class FacebookAdsIntegrationTests(TestCase):
    def setUp(self):
        self.client = Client()
        AdCampaign.objects.all().delete()
        FleetCustomer.objects.all().delete()
        ChatMessage.objects.all().delete()

        # Create campaigns
        self.campaign_wifi = AdCampaign.objects.create(
            campaign_name="Wifi Camera Promo",
            ad_id="wifi_ad_123",
            headline_keywords="wifi camera, wifi security",
            welcome_message="Hello, welcome to our Wifi Camera ad campaign!",
            custom_system_prompt="Focus on Wifi camera setup and night vision.",
            catalog_file="Wifi_Camera_Catalog.pdf",
            is_active=True
        )

        self.campaign_gps = AdCampaign.objects.create(
            campaign_name="GPS Tracker Promo",
            ad_id="gps_ad_456",
            headline_keywords="gps tracker, location tracker",
            welcome_message="Welcome! Learn about our GPS Trackers.",
            custom_system_prompt="Focus strictly on GPS trackers and government AIS 140 certification.",
            catalog_file="AIS_140_GPS_Tracker_Catalog.pdf",
            is_active=True
        )

    @patch("bot.views.requests.post")
    @patch("bot.views.os.getenv")
    def test_webhook_matches_ad_by_id(self, mock_getenv, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_post.return_value = MagicMock(status_code=200)

        # Incoming webhook payload with referral block containing wifi ad ID
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "919999999999",
                            "id": "wamid.referral_id_1",
                            "type": "text",
                            "text": {"body": "Interested in camera"},
                            "referral": {
                                "source_id": "wifi_ad_123",
                                "source_type": "ad",
                                "headline": "High-Quality Wifi Camera",
                                "body": "Protect your assets."
                            }
                        }]
                    }
                }]
            }]
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        
        # Verify customer was created and referred_by was set
        customer = FleetCustomer.objects.get(phone_number="919999999999")
        self.assertEqual(customer.referred_by, self.campaign_wifi)

        # We expect 2 calls: 1 for welcome message, 1 for catalog document
        self.assertEqual(mock_post.call_count, 2)
        
        # Verify welcome message
        _, kwargs_welcome = mock_post.call_args_list[0]
        self.assertEqual(kwargs_welcome["json"]["text"]["body"], "Hello, welcome to our Wifi Camera ad campaign!")

        # Verify catalog message
        _, kwargs_catalog = mock_post.call_args_list[1]
        self.assertEqual(kwargs_catalog["json"]["type"], "document")
        self.assertEqual(kwargs_catalog["json"]["document"]["filename"], "Wifi_Camera_Catalog.pdf")

    @patch("bot.views.requests.post")
    @patch("bot.views.os.getenv")
    def test_webhook_matches_ad_by_headline_keywords(self, mock_getenv, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        mock_post.return_value = MagicMock(status_code=200)

        # Incoming webhook payload with referral block matching keywords (location tracker -> gps)
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "918888888888",
                            "id": "wamid.referral_id_2",
                            "type": "text",
                            "text": {"body": "Interested"},
                            "referral": {
                                "source_id": "unknown_ad_id",
                                "source_type": "ad",
                                "headline": "Best Location Tracker",
                                "body": "Realtime updates."
                            }
                        }]
                    }
                }]
            }]
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        
        # Verify customer was created and referred_by was set to GPS campaign
        customer = FleetCustomer.objects.get(phone_number="918888888888")
        self.assertEqual(customer.referred_by, self.campaign_gps)

    @patch("bot.views.requests.post")
    @patch("bot.views.Groq")
    @patch("bot.views.os.getenv")
    def test_ai_response_injects_ad_context(self, mock_getenv, mock_groq, mock_post):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_APP_SECRET": None,
            "GROQ_API_KEY": "fake_key",
            "PHONE_NUMBER_ID": "fake_id",
            "WHATSAPP_TOKEN": "fake_token",
        }.get(key, default)

        # Mock Groq client
        mock_ai_instance = MagicMock()
        mock_groq.return_value = mock_ai_instance
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Mocked camera reply."))
        ]
        mock_ai_instance.chat.completions.create.return_value = mock_completion
        mock_post.return_value = MagicMock(status_code=200)

        # Create a customer already associated with the WiFi camera campaign
        customer = FleetCustomer.objects.create(
            phone_number="917777777777",
            owner_name="Ad Customer",
            referred_by=self.campaign_wifi
        )

        # Customer sends a follow-up message (no referral block in webhook this time)
        payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "917777777777",
                            "id": "wamid.follow_up_msg",
                            "type": "text",
                            "text": {"body": "Tell me more about it."}
                        }]
                    }
                }]
            }]
        }

        response = self.client.post(
            reverse("whatsapp_webhook"),
            data=json.dumps(payload),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

        # Verify Groq was called
        self.assertTrue(mock_ai_instance.chat.completions.create.called)
        
        # Verify the custom ad instructions were present in the system prompt
        call_args = mock_ai_instance.chat.completions.create.call_args
        messages_payload = call_args[1]["messages"]
        system_message = next(msg for msg in messages_payload if msg["role"] == "system")
        
        self.assertIn("Focus on Wifi camera setup and night vision.", system_message["content"])
        self.assertIn("CRITICAL CONTEXT: The customer arrived via the ad campaign: 'Wifi Camera Promo'", system_message["content"])


class WhatsAppTemplateSyncTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='password123'
        )
        self.client.login(username='admin', password='password123')
        WhatsAppTemplate.objects.all().delete()

    @patch("bot.admin.requests.get")
    @patch("bot.admin.os.getenv")
    def test_sync_whatsapp_templates_from_meta(self, mock_getenv, mock_get):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_TOKEN": "fake_token",
            "WHATSAPP_BUSINESS_ACCOUNT_ID": "fake_waba_id"
        }.get(key, default)

        # Mock Meta API template response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "name": "hello_world",
                    "status": "APPROVED",
                    "category": "UTILITY",
                    "language": "en_US",
                    "components": [{"type": "BODY", "text": "Hello World"}]
                },
                {
                    "name": "gps_tracking_device",
                    "status": "APPROVED",
                    "category": "MARKETING",
                    "language": "en_US",
                    "components": [{"type": "BODY", "text": "AIS 140 tracker details"}]
                },
                {
                    "name": "gps_tracking_device",
                    "status": "APPROVED",
                    "category": "MARKETING",
                    "language": "te",
                    "components": [{"type": "BODY", "text": "AIS 140 tracker details in Telugu"}]
                },
                {
                    "name": "fuel_alert",
                    "status": "APPROVED",
                    "category": "UTILITY",
                    "language": "en_US",
                    "components": [{"type": "BODY", "text": "Fuel drop alert for {{1}}"}]
                },
                {
                    "name": "ais_140_gps_mining_device",
                    "status": "APPROVED",
                    "category": "UTILITY",
                    "language": "en_US",
                    "components": [
                        {"type": "HEADER", "format": "IMAGE"},
                        {"type": "BODY", "text": "Mining details"}
                    ]
                },
                {
                    "name": "pending_template",
                    "status": "PENDING",
                    "category": "UTILITY",
                    "language": "en_US",
                    "components": [{"type": "BODY", "text": "Hello"}]
                }
            ]
        }
        mock_get.return_value = mock_response

        from bot.admin import sync_whatsapp_templates_from_meta
        result = sync_whatsapp_templates_from_meta()

        self.assertIsNotNone(result)
        self.assertIn("hello_world", result)
        self.assertIn("gps_tracking_device", result)
        self.assertIn("fuel_alert", result)
        self.assertIn("ais_140_gps_mining_device", result)
        self.assertNotIn("pending_template", result) # Should filter out pending

        self.assertEqual(result["hello_world"], ["en_US"])
        self.assertEqual(result["gps_tracking_device"], ["en_US", "te"])
        self.assertEqual(result["fuel_alert"], ["en_US"])
        self.assertEqual(result["ais_140_gps_mining_device"], ["en_US"])

        # Check DB objects
        t_hello = WhatsAppTemplate.objects.get(template_name="hello_world")
        self.assertFalse(t_hello.has_variables)
        self.assertFalse(t_hello.has_header)
        self.assertEqual(t_hello.header_type, "none")
        self.assertEqual(t_hello.languages, "en_US")

        t_fuel = WhatsAppTemplate.objects.get(template_name="fuel_alert")
        self.assertTrue(t_fuel.has_variables)
        self.assertFalse(t_fuel.has_header)
        self.assertEqual(t_fuel.languages, "en_US")

        t_gps = WhatsAppTemplate.objects.get(template_name="gps_tracking_device")
        self.assertFalse(t_gps.has_variables)
        self.assertFalse(t_gps.has_header)
        self.assertEqual(t_gps.languages, "en_US,te")

        t_mining = WhatsAppTemplate.objects.get(template_name="ais_140_gps_mining_device")
        self.assertFalse(t_mining.has_variables)
        self.assertTrue(t_mining.has_header)
        self.assertEqual(t_mining.header_type, "image")

    @patch("bot.admin.requests.get")
    @patch("bot.admin.os.getenv")
    def test_broadcast_view_contains_template_mapping(self, mock_getenv, mock_get):
        mock_getenv.side_effect = lambda key, default=None: {
            "WHATSAPP_TOKEN": "fake_token",
            "WHATSAPP_BUSINESS_ACCOUNT_ID": "fake_waba_id"
        }.get(key, default)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "name": "gps_tracking_device",
                    "status": "APPROVED",
                    "category": "MARKETING",
                    "language": "en_US",
                    "components": []
                }
            ]
        }
        mock_get.return_value = mock_response

        url = reverse("admin:bot_fleetcustomer_broadcast")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("templates_mapping_json", response.context)
        
        # Verify custom template and synced templates are in mapping
        mapping = json.loads(response.context["templates_mapping_json"])
        self.assertIn("gps_tracking_device", mapping)
        self.assertEqual(mapping["gps_tracking_device"], ["en_US"])


class WhatsAppTemplateHeaderTests(TestCase):
    def setUp(self):
        WhatsAppTemplate.objects.all().delete()
        # Patch upload_media_to_meta globally for this test suite to avoid real API calls on save()
        self.upload_patcher = patch("bot.utils.upload_media_to_meta", return_value="fake_media_id_123")
        self.mock_upload = self.upload_patcher.start()

    def tearDown(self):
        try:
            self.upload_patcher.stop()
        except RuntimeError:
            pass

    @patch("requests.post")
    @patch("bot.utils.os.getenv")
    def test_upload_media_to_meta_success(self, mock_getenv, mock_post):
        # Stop the class-level patcher so we can test the real utility
        self.upload_patcher.stop()
        try:
            mock_getenv.side_effect = lambda key, default=None: {
                "WHATSAPP_TOKEN": "fake_token",
                "PHONE_NUMBER_ID": "fake_phone_id"
            }.get(key, default)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "meta_returned_media_id_999"}
            mock_post.return_value = mock_response

            from bot.utils import upload_media_to_meta
            # Pass a local file path that physically exists
            import sys
            import os
            test_file_path = os.path.abspath(__file__)
            media_id = upload_media_to_meta(test_file_path)
            
            self.assertEqual(media_id, "meta_returned_media_id_999")
            self.assertEqual(mock_post.call_count, 1)
        finally:
            self.upload_patcher.start()

    @patch("bot.broadcast.requests.post")
    def test_send_whatsapp_template_with_header_media_id(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_post.return_value = mock_response

        # Create template with header_media_id set
        WhatsAppTemplate.objects.create(
            template_name="ais_140_gps_mining_device",
            description="Mining Device Info",
            has_variables=False,
            has_header=True,
            header_type="image",
            header_media_id="meta_media_id_123",
            languages="en_US"
        )

        from bot.broadcast import send_whatsapp_template
        success, error = send_whatsapp_template(
            to_phone="916281670029",
            template_name="ais_140_gps_mining_device",
            language_code="en_US"
        )

        self.assertTrue(success)
        self.assertEqual(mock_post.call_count, 1)

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertIn("components", payload["template"])
        components = payload["template"]["components"]
        self.assertEqual(components[0]["type"], "header")
        self.assertEqual(components[0]["parameters"][0]["type"], "image")
        self.assertEqual(components[0]["parameters"][0]["image"]["id"], "meta_media_id_123")
        self.assertNotIn("link", components[0]["parameters"][0]["image"])

    @patch("bot.broadcast.requests.post")
    def test_send_whatsapp_template_with_image_header_url(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_post.return_value = mock_response

        # Create template with image header using URL and empty media ID
        WhatsAppTemplate.objects.create(
            template_name="ais_140_gps_mining_device",
            description="Mining Device Info",
            has_variables=False,
            has_header=True,
            header_type="image",
            header_image_url="https://your-public-image-url.com/mining-header.jpg",
            header_media_id="",
            languages="en_US"
        )

        from bot.broadcast import send_whatsapp_template
        success, error = send_whatsapp_template(
            to_phone="916281670029",
            template_name="ais_140_gps_mining_device",
            language_code="en_US"
        )

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(mock_post.call_count, 1)

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["template"]["name"], "ais_140_gps_mining_device")
        
        # Verify components structure fallback to link
        self.assertIn("components", payload["template"])
        components = payload["template"]["components"]
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]["type"], "header")
        self.assertEqual(components[0]["parameters"][0]["type"], "image")
        self.assertEqual(components[0]["parameters"][0]["image"]["link"], "https://your-public-image-url.com/mining-header.jpg")

    @patch("bot.broadcast.requests.post")
    def test_send_whatsapp_template_with_image_header_id_fallback(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_post.return_value = mock_response

        # Create template with image header using Meta media ID (numeric ID in image_url field)
        WhatsAppTemplate.objects.create(
            template_name="ais_140_gps_mining_device",
            description="Mining Device Info",
            has_variables=False,
            has_header=True,
            header_type="image",
            header_image_url="123456789012345",
            header_media_id="",
            languages="en_US"
        )

        from bot.broadcast import send_whatsapp_template
        success, error = send_whatsapp_template(
            to_phone="916281670029",
            template_name="ais_140_gps_mining_device",
            language_code="en_US"
        )

        self.assertTrue(success)
        self.assertEqual(mock_post.call_count, 1)

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        components = payload["template"]["components"]
        self.assertEqual(components[0]["parameters"][0]["image"]["id"], "123456789012345")
        self.assertNotIn("link", components[0]["parameters"][0]["image"])

    @patch("bot.broadcast.requests.post")
    def test_send_whatsapp_template_with_no_header(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_post.return_value = mock_response

        # Create template with no header
        WhatsAppTemplate.objects.create(
            template_name="simple_template",
            description="No Header Info",
            has_variables=False,
            has_header=False,
            header_type="none",
            header_image_url="",
            header_media_id="",
            languages="en_US"
        )

        from bot.broadcast import send_whatsapp_template
        success, error = send_whatsapp_template(
            to_phone="916281670029",
            template_name="simple_template",
            language_code="en_US"
        )

        self.assertTrue(success)
        self.assertEqual(mock_post.call_count, 1)

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertNotIn("components", payload["template"])

    @patch("bot.broadcast.requests.post")
    def test_send_whatsapp_template_with_image_header_uploaded_file(self, mock_post):
        from django.core.files.uploadedfile import SimpleUploadedFile
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_post.return_value = mock_response

        # Temporarily mock upload_media_to_meta to return a dummy so it runs save hook
        # Actually it's already mocked in setUp to return fake_media_id_123

        # Create template with uploaded image file
        mock_file = SimpleUploadedFile("my_downloaded_image.jpg", b"fake_image_bytes", content_type="image/jpeg")
        template = WhatsAppTemplate.objects.create(
            template_name="ais_140_gps_mining_device",
            description="Mining Device Info",
            has_variables=False,
            has_header=True,
            header_type="image",
            header_file=mock_file,
            header_media_id="", # will get populated by save hook to fake_media_id_123
            languages="en_US"
        )

        self.assertEqual(template.header_media_id, "fake_media_id_123")

        from bot.broadcast import send_whatsapp_template
        success, error = send_whatsapp_template(
            to_phone="916281670029",
            template_name="ais_140_gps_mining_device",
            language_code="en_US"
        )

        self.assertTrue(success)
        self.assertEqual(mock_post.call_count, 1)

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertIn("components", payload["template"])
        components = payload["template"]["components"]
        self.assertEqual(components[0]["parameters"][0]["image"]["id"], "fake_media_id_123")

        # Clean up the file created by SimpleUploadedFile
        if template.header_file and os.path.exists(template.header_file.path):
            try:
                os.remove(template.header_file.path)
            except Exception:
                pass




