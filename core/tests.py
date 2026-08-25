from unittest.mock import patch

from django.test import Client, TestCase


class CoreApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_api(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_districts_api_returns_seed_data(self):
        response = self.client.get("/api/districts")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("districts", data)
        self.assertGreater(len(data["districts"]), 0)
        self.assertIn("risks", data["districts"][0])
        self.assertIn("risk_drivers", data["districts"][0])
        self.assertIn("historical_hazard_profile", data["districts"][0])

    def test_prediction_api_returns_probability(self):
        response = self.client.post(
            "/api/predict/",
            data={
                "district": "Patna",
                "rainfall_mm": 280,
                "river_level_m": 8.5,
                "elevation_m": 50,
                "temperature_c": 30,
                "month": 8,
                "use_live": False,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("flood_probability", data)
        self.assertIn("historical_context", data)
        self.assertIn("model_probability", data)
        self.assertIn(data["risk_level"], ["LOW", "MEDIUM", "HIGH", "CRITICAL"])

    def test_monthly_api_returns_selected_hazard_series(self):
        response = self.client.post(
            "/api/predict/monthly",
            data={"district": "Patna", "hazard": "fire"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["hazard"], "fire")
        self.assertEqual(len(data["series"]), 12)
        self.assertIn("peak_month", data)

    def test_evacuation_api_returns_waypoints(self):
        response = self.client.post(
            "/api/evacuate/",
            data={
                "origin_district": "Patna",
                "destination_district": "Delhi",
                "disaster_type": "flood",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data["waypoints"]), 1)
        self.assertIn("suggested_resources", data)
        self.assertIn("route_note", data)
        self.assertIn("route_geometry", data)
        self.assertIn("route_steps", data)
        self.assertEqual(data["route_mode"], "manual_destination")

    def test_evacuation_auto_prefers_nearby_practical_destination(self):
        response = self.client.post(
            "/api/evacuate/",
            data={"origin_district": "Delhi", "disaster_type": "flood"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["route_mode"], "local_resource")
        self.assertLessEqual(data["distance_km"], 50)
        self.assertIn(data["route_band"], ["local_resource", "local_estimate"])
        self.assertIn("local", data["route_note"].lower())
        self.assertIn("route_geometry", data)
        self.assertIn("route_steps", data)
        self.assertGreaterEqual(len(data["route_geometry"]), 2)


    def test_alert_unsubscribe_link_works_with_get(self):
        from core.models import AlertSubscription
        sub = AlertSubscription.objects.create(email="test@example.com", hazards=["flood"], threshold=0.55)
        response = self.client.get(f"/api/alerts/unsubscribe?token={sub.unsubscribe_token}")
        self.assertEqual(response.status_code, 200)
        sub.refresh_from_db()
        self.assertFalse(sub.active)

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    def test_chat_api_uses_local_fallback_without_ai_key(self):
        response = self.client.post(
            "/api/chat",
            data={"message": "How do alerts work?"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "ClimateGuard")
        self.assertIn("Alerts panel", data["response"])

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    def test_chat_api_local_fallback_handles_hazard_questions(self):
        response = self.client.post(
            "/api/chat",
            data={"message": "What about earthquake risk?"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "ClimateGuard")
        self.assertIn("earthquake", data["response"].lower())

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    def test_chat_api_local_fallback_handles_district_questions(self):
        response = self.client.post(
            "/api/chat",
            data={"message": "Tell me about Patna"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["source"], "ClimateGuard")
        self.assertIn("Patna", data["response"])

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_MODEL": "qwen/qwen3-32b", "GEMINI_API_KEY": ""})
    @patch("core.views.requests.post")
    def test_chat_api_uses_openrouter_when_key_is_configured(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "OpenRouter answer"}}]
        }

        response = self.client.post(
            "/api/chat",
            data={"message": "How should I prepare for floods?", "district": "Patna"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["response"], "OpenRouter answer")
        self.assertEqual(data["source"], "OpenRouter · qwen/qwen3-32b")
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(kwargs["json"]["model"], "qwen/qwen3-32b")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
