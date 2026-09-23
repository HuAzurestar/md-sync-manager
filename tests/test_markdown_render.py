import unittest

from fastapi.testclient import TestClient

from src.api.app import create_app


class MarkdownRenderTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_commonmark_is_rendered_by_the_standard_adapter(self):
        response = self.client.post(
            "/api/v1/document/render",
            json={
                "name": "sample.md",
                "content": "# Heading\n\n**bold**\n\n```mermaid\ngraph TD; A-->B\n```\n",
            },
        )

        self.assertEqual(response.status_code, 200)
        html = response.json()["data"]["html"]
        self.assertIn("<h1>Heading</h1>", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn('class="language-mermaid"', html)
        self.assertIn("graph TD; A--&gt;B", html)

    def test_raw_html_is_not_executed(self):
        response = self.client.post(
            "/api/v1/document/render",
            json={
                "name": "unsafe.md",
                "content": '<script>alert("x")</script>\n\n[x](javascript:alert(1))\n',
            },
        )

        html = response.json()["data"]["html"]
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn('href="javascript:', html)


if __name__ == "__main__":
    unittest.main()
