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


