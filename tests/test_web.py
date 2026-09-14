import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("flask"), "Flask is not installed")
class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        from flashcard_generator.web import create_app

        self.client = create_app({"TESTING": True}).test_client()

    def test_home_page_loads(self) -> None:
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Turn notes into cards worth studying.", response.data)

    def test_rules_generation_uses_the_existing_pipeline(self) -> None:
        response = self.client.post(
            "/api/generate",
            json={
                "notes": "Atom: The smallest unit of matter.",
                "engine": "rules",
                "polish": "auto",
                "device": "auto",
                "offline": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["summary"]["accepted"], 1)
        self.assertEqual(response.json["cards"][0]["front"], "What is Atom?")

    def test_generation_rejects_empty_notes(self) -> None:
        response = self.client.post("/api/generate", json={"notes": "", "engine": "rules"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("required", response.json["error"])
