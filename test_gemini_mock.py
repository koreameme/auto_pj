import sys
import os
import unittest
import re
from unittest.mock import MagicMock, patch

# 프로젝트 워크스페이스 경로를 sys.path에 추가
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from content_writer import ContentWriter, _parse_ai_response

class TestGeminiAndParserMock(unittest.TestCase):

    def test_parser_normal_format(self):
        # 1. 정상 구분자 형식 파싱 테스트
        ai_output = """
[TITLE]
아침 방송 극찬! 보스웰리아 비교 TOP 3 추천
[SLUG]
boswellia-comparison-top3
[BODY]
보스웰리아는 관절 건강에 매우 좋은 식품입니다.
식약처 인증 고함량 제품을 고르는 것이 중요합니다.
"""
        parsed = _parse_ai_response(ai_output, "보스웰리아")
        self.assertEqual(parsed["title"], "아침 방송 극찬! 보스웰리아 비교 TOP 3 추천")
        self.assertEqual(parsed["slug"], "boswellia-comparison-top3")
        self.assertTrue("관절 건강에 매우 좋은" in parsed["body"])

    def test_parser_fallback_format(self):
        # 2. 구분자가 없는 원시 마크다운 형식 폴백 파싱 테스트
        ai_output = """# 엄청난 효능의 초록입홍합 가이드
초록입홍합은 관절 염증 완화에 탁월한 효과가 있습니다.
가성비 좋은 제품 리스트를 공개합니다.
"""
        parsed = _parse_ai_response(ai_output, "초록입홍합")
        self.assertEqual(parsed["title"], "엄청난 효능의 초록입홍합 가이드")
        self.assertTrue(parsed["slug"].startswith("post-")) # 영문 난수 슬러그 자동 생성 확인
        self.assertTrue("관절 염증 완화에 탁월한" in parsed["body"])

    def test_markdown_file_creation(self):
        # 3. 마크다운 생성 결과물 및 permalink 주입 여부 테스트
        writer = ContentWriter()
        ai_output = """
[TITLE]
최신 AI 동향 분석! ChatGPT 5 출시 임박
[SLUG]
chatgpt-5-upcoming-release
[BODY]
OpenAI가 드디어 차세대 거대 언어 모델 출시를 준비 중입니다.
"""
        # 임시 파일 작성을 시도하고 생성된 파일의 내용 확인
        file_path, slug = writer.write_to_markdown_file("ai_news", "ChatGPT", ai_output)
        
        self.assertEqual(slug, "chatgpt-5-upcoming-release")
        self.assertTrue(os.path.exists(file_path))
        self.assertTrue(file_path.endswith(f"{slug}.md"))

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Front Matter permalink 확인
        self.assertTrue("permalink: /posts/chatgpt-5-upcoming-release/\n" in content)
        self.assertTrue('title: "최신 AI 동향 분석! ChatGPT 5 출시 임박"\n' in content)
        self.assertTrue("OpenAI가 드디어 차세대" in content)

        # 테스트 후 파일 삭제
        if os.path.exists(file_path):
            os.remove(file_path)

    @patch('content_writer.genai')
    def test_gemini_methods(self, mock_genai):
        # 4. Gemini SDK Mock 객체 동작 확인
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "[TITLE]\n후킹 건강 정보\n[SLUG]\nhealth-info\n[BODY]\nGemini가 쓴 관절 건강 이야기"
        mock_client.models.generate_content.return_value = mock_response
        
        writer = ContentWriter()
        writer.gemini_client = mock_client
        writer.gemini_enabled = True
        
        products = [
            {"productName": "건강보조제 A", "productPrice": 10000, "discountRate": 10, "productImage": "img1.jpg", "productUrl": "url1"}
        ]
        res_health = writer._gemini_health_post("루테인", products)
        self.assertTrue("[TITLE]" in res_health)
        
        res_news = writer._gemini_ai_news_body("새로운 AI 등장", "ChatGPT 5 요약", "http://source.link")
        self.assertTrue("[SLUG]" in res_news)
        
        res_issue = writer._gemini_issue_body("실시간 핫이슈", "실시간 검색어 요약")
        self.assertTrue("[BODY]" in res_issue)
        
        self.assertEqual(mock_client.models.generate_content.call_count, 3)
        print("\n[OK] All mock and parser unit tests passed successfully!")

if __name__ == '__main__':
    unittest.main()
