import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class DockerDeliveryTests(unittest.TestCase):
    def test_image_runs_one_non_root_loopback_service_with_healthcheck(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("FROM python:3.12-slim", dockerfile)
        self.assertIn("USER smmd", dockerfile)
        self.assertIn("SMMD_CONFIG=/data/sync.yaml", dockerfile)
        self.assertIn("SMMD_LOG_DIR=/data/logs", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn('CMD ["python", "-m", "src.controller.server"]', dockerfile)

    def test_compose_has_one_service_and_loopback_only_publishing(self):
        compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))

        self.assertEqual(list(compose["services"]), ["workbench"])
        service = compose["services"]["workbench"]
        self.assertEqual(service["ports"], ["127.0.0.1:8000:8000"])
        self.assertEqual(service["volumes"], ["sm-md-data:/data"])
        self.assertEqual(service["environment"]["SMMD_CONFIG"], "/data/sync.yaml")
        self.assertEqual(service["environment"]["SMMD_LOG_DIR"], "/data/logs")


if __name__ == "__main__":
    unittest.main()
