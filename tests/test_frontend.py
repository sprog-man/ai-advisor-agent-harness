"""前端界面测试"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestFrontendFiles:
    def test_index_html_exists(self):
        html_path = Path(__file__).parent.parent / "frontend" / "index.html"
        assert html_path.exists(), "index.html 不存在"

    def test_css_file_exists(self):
        css_path = Path(__file__).parent.parent / "frontend" / "css" / "style.css"
        assert css_path.exists(), "style.css 不存在"

    def test_js_file_exists(self):
        js_path = Path(__file__).parent.parent / "frontend" / "js" / "app.js"
        assert js_path.exists(), "app.js 不存在"

    def test_index_html_has_structure(self):
        html_path = Path(__file__).parent.parent / "frontend" / "index.html"
        content = html_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "<title>AI Advisor Agent</title>" in content
        assert "messageInput" in content
        assert "sendBtn" in content

    def test_css_has_dark_theme(self):
        css_path = Path(__file__).parent.parent / "frontend" / "css" / "style.css"
        content = css_path.read_text(encoding="utf-8")
        assert "#0d0d0d" in content or "#171717" in content
        assert "var(--bg-primary)" in content

    def test_js_has_chat_app(self):
        js_path = Path(__file__).parent.parent / "frontend" / "js" / "app.js"
        content = js_path.read_text(encoding="utf-8")
        assert "class ChatApp" in content
        assert "sendMessage" in content
        assert "streamResponse" in content


class TestServerFile:
    def test_server_exists(self):
        server_path = Path(__file__).parent.parent / "server.py"
        assert server_path.exists(), "server.py 不存在"

    def test_server_has_api_endpoint(self):
        server_path = Path(__file__).parent.parent / "server.py"
        content = server_path.read_text(encoding="utf-8")
        assert "@app.post(\"/api/chat\")" in content
        assert "ChatRequest" in content
        assert "ChatResponse" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
