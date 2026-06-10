import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ContentWriter:
    """AI를 활용해 마크다운 포스팅 원고를 자동 생성하고 파일로 기록하는 클래스"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        # API key가 존재할 경우에만 OpenAI 클라이언트 초기화
        self.client = OpenAI(api_key=self.api_key) if self.api_key and self.api_key != "your_openai_api_key_here" else None

    def generate_blog_post(self, keyword: str, products: list) -> str:
        """키워드와 상품 목록을 기반으로 블로그 포스팅 원고 생성 (Front Matter 포함)"""
        
        # 상품 리스트 정보를 프롬프트용 문자열로 가공
        products_info = ""
        for idx, prod in enumerate(products, 1):
            products_info += (
                f"{idx}. 상품명: {prod['productName']}\n"
                f"   - 가격: {prod['productPrice']}원 (할인율: {prod.get('discountRate', 0)}%)\n"
                f"   - 이미지 주소: {prod['productImage']}\n"
                f"   - 구매 링크: {prod['productUrl']}\n\n"
            )

        # API Key가 유효하지 않을 경우 Fallback 로컬 템플릿 사용
        if not self.client:
            logging.warning("OpenAI API Key가 설정되지 않았습니다. 내장 템플릿으로 원고를 생성합니다.")
            return self._generate_fallback_post(keyword, products)

        # AI 프롬프트 설계
        system_prompt = (
            "당신은 전문 상품 리뷰어이자 SEO 최적화 전문 블로거입니다. "
            "주어진 상품 정보를 바탕으로 독자에게 진정성 있고 설득력 있는 구매 가이드 및 추천 글을 작성해야 합니다. "
            "글은 정중하고 신뢰감 있는 어조로 작성하며, 구글 검색 엔진에 상위 노출될 수 있도록 구조적인 마크다운 형식으로 작성하세요."
        )

        user_prompt = f"""
다음 키워드와 상품 목록을 기반으로 최고의 추천 포스팅을 작성해 주세요.

[타겟 키워드]: {keyword}

[추천 상품 목록]:
{products_info}

[작성 가이드라인]:
1. 글 제목은 키워드가 자연스럽게 들어가며 클릭을 유도하는 매력적인 제목으로 정하세요.
2. 서론에서 해당 키워드 상품이 최근 인기 있는 이유와 구매 시 핵심 고려사항을 설명하세요.
3. 각 상품별 장단점, 가격 대비 성능(가성비), 주요 특징을 풍부하고 전문적으로 서술하세요.
4. **중요**: 각 상품 설명 끝부분에 아래 양식으로 링크와 이미지를 마크다운 형태로 자연스럽게 삽입하세요.
   - 이미지: `![상품명](이미지 주소)`
   - 구매 버튼: `[▶ 최저가 및 후기 확인하기](구매 링크)`
5. 결론부에 종합적인 추천(예: '가성비를 중시한다면 A, 고성능을 원한다면 B')을 요약해 주세요.
6. 본문에 쿠팡 파트너스 안내 문구(예: '이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.')를 본문 맨 아래에 반드시 한 번 포함시키세요.
7. 본문 텍스트 외에 코드 블록이나 마크다운 백틱 가이드 등의 불필요한 메타 대화는 절대 포함하지 마세요. 오직 발행할 본문만 출력하세요.
"""

        try:
            logging.info("OpenAI API를 통한 포스팅 원고 생성 시작...")
            response = self.client.chat.completions.create(
                model="gpt-4o",  # 가성비 및 성능 고려 gpt-4o 채택
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2500
            )
            content = response.choices[0].message.content.strip()
            logging.info("OpenAI API 포스팅 원고 생성 완료")
            return content
        except Exception as e:
            logging.error(f"OpenAI API 호출 중 예외 발생: {e}")
            logging.info("Fallback 로직으로 전환합니다.")
            return self._generate_fallback_post(keyword, products)

    def _generate_fallback_post(self, keyword: str, products: list) -> str:
        """API 호출 실패 혹은 API Key 미등록 시 대체 마크다운 포스팅 생성"""
        title = f"2026년 가성비 {keyword} 추천 및 인기 순위 비교 분석"
        
        products_section = ""
        for idx, prod in enumerate(products, 1):
            products_section += f"""
### {idx}. {prod['productName']}
* **가격**: {prod['productPrice']:,}원 (할인율: {prod.get('discountRate', 0)}%)
* **주요 특징**: 실사용자 평점이 높고 합리적인 가격대를 보여주는 최고의 인기 제품군입니다. 심플한 디자인과 탄탄한 기본 성능으로 만족도가 우수합니다.

![{prod['productName']}]({prod['productImage']})

[▶ 최저가 및 후기 확인하기]({prod['productUrl']})

---
"""

        fallback_content = f"""# {title}

안녕하세요! 오늘은 최근 큰 관심을 모으고 있는 **{keyword}** 제품군에 대해 자세히 알아보고, 가장 합리적이고 성능이 우수한 제품들을 골라 추천 순위를 정리해 드립니다.

## {keyword} 선택 시 핵심 체크리스트
1. **가성비**: 가격 대비 내구성과 핵심 기능이 충실한지 비교해야 합니다.
2. **실사용 평가**: 먼저 구매한 고객들의 평점과 만족도가 증명된 상품인지 확인하세요.

---

## 🏆 베스트 추천 상품 리스트

{products_section}

## 종합 구매 가이드
각 상품마다 장단점이 뚜렷하므로 본인의 목적(가성비 지향, 성능 최우선 등)에 맞추어 올바른 제품을 골라보시길 권장합니다. 현명한 쇼핑에 큰 도움이 되었기를 바랍니다!

<br>

---
*이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.*
"""
        return fallback_content.strip()

    def write_to_markdown_file(self, keyword: str, content: str, output_dir: str = "_posts") -> str:
        """Jekyll/Hugo 양식의 Front Matter를 부착하여 마크다운 파일로 저장"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logging.info(f"포스팅 저장 디렉터리 생성 완료: {output_dir}")

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Y-%m-%d %H:%M:%S +0900")
        
        # 파일명 형식: YYYY-MM-DD-keyword.md
        # 파일명 내 특수문자나 공백 정제
        safe_keyword = "".join([c if c.isalnum() or c in ["-", "_"] else "_" for c in keyword])
        filename = f"{date_str}-{safe_keyword}.md"
        file_path = os.path.join(output_dir, filename)

        # 제목 추출 (content의 첫 줄이 # 제목 일 경우 활용)
        title = f"가장 합리적인 {keyword} 추천 가이드"
        lines = content.split("\n")
        for line in lines[:3]:
            if line.startswith("# "):
                title = line.replace("# ", "").strip()
                # 본문에서 중복 출력을 피하기 위해 # 제목 라인 제거
                content = content.replace(line, "", 1).strip()
                break

        # Jekyll 호환 Front Matter 생성
        front_matter = (
            f"---\n"
            f"layout: post\n"
            f"title: \"{title}\"\n"
            f"date: {time_str}\n"
            f"categories: shopping\n"
            f"tags: [{keyword}, 추천상품, 쇼핑가이드]\n"
            f"---\n\n"
        )

        full_content = front_matter + content

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_content)
        
        logging.info(f"성공적으로 마크다운 포스팅을 기록했습니다: {file_path}")
        return file_path

if __name__ == "__main__":
    writer = ContentWriter()
    mock_products = [
        {"productName": "삼성 가성비 노트북", "productPrice": 590000, "productImage": "https://dummy.com/1.jpg", "productUrl": "https://link.coupang.com/a/1"},
        {"productName": "LG 고성능 그램 노트북", "productPrice": 1290000, "productImage": "https://dummy.com/2.jpg", "productUrl": "https://link.coupang.com/a/2"}
    ]
    raw_post = writer.generate_blog_post("노트북", mock_products)
    saved_file = writer.write_to_markdown_file("노트북", raw_post, "test_posts")
    print(f"저장된 파일: {saved_file}")
