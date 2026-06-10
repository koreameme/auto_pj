import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class ContentWriter:
    """AI를 활용해 후킹성 강력한 마크다운 포스팅 원고를 자동 생성하고 파일로 기록하는 클래스"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key) if self.api_key and self.api_key != "your_openai_api_key_here" else None

    def generate_blog_post(self, keyword: str, products: list) -> str:
        """키워드와 상품 목록을 기반으로 강력한 후킹성 블로그 포스팅 원고 생성 (Front Matter 포함)"""
        
        products_info = ""
        for idx, prod in enumerate(products, 1):
            products_info += (
                f"{idx}. 상품명: {prod['productName']}\n"
                f"   - 가격: {prod['productPrice']}원 (할인율: {prod.get('discountRate', 0)}%)\n"
                f"   - 이미지 주소: {prod['productImage']}\n"
                f"   - 구매 링크: {prod['productUrl']}\n\n"
            )

        if not self.client:
            logging.warning("OpenAI API Key가 설정되지 않았습니다. 후킹성 고도화 템플릿으로 원고를 생성합니다.")
            return self._generate_fallback_post(keyword, products)

        # AI 프롬프트 - 후킹성 및 스토리텔링 지침 극대화
        system_prompt = (
            "당신은 대한민국 최고 수준의 바이럴 마케터이자 SEO 카피라이터입니다. "
            "당신의 목표는 독자가 제목을 보자마자 클릭하지 않고는 못 배기게 만드는 '강력한 후킹성 제목'을 짓고, "
            "본문에서는 독자의 고통과 갈증(Pain Point)을 자극하며 몰입하게 만드는 스토리텔링형 글을 쓰는 것입니다. "
            "글은 절대 기계적이지 않으며 감정에 호소하면서도 논리적인 설득력을 가져야 합니다. "
            "구글 검색 엔진 최적화(SEO) 기준에 맞는 마크다운 포맷으로만 작성하세요."
        )

        user_prompt = f"""
다음 키워드와 상품 정보를 기반으로 클릭을 유도하는 최상급 후킹성 포스팅 원고를 작성해 주세요.

[타겟 키워드]: {keyword}

[추천 상품 목록]:
{products_info}

[🚨 필수 작성 규칙 및 가이드라인]:
1. **헤드라인(제목)**:
   - 독자의 궁금증을 폭발시키는 제목, 충격적인 수치나 진실을 밝히는 문장, 안 보면 무조건 손해라는 심리를 자극하는 문장 중 하나로 지으세요.
   - 예시 스타일: "의사들이 절대 말 안 해주는 [키워드]의 진실? 오늘 아침 방영 후 난리 난 품절대란 OOO 비교", "관절 수명 20년 살리는 비밀? 안 보면 무조건 후회하는 [키워드] 가성비 종결템"
2. **서론**:
   - 아침 방송(MBC 기분 좋은 날, KBS 무엇이든 물어보세요 등)에서 다룬 내용을 언급하며 오늘 당장 구매해야만 하는 당위성을 소구하세요.
   - 독자가 겪고 있을 만한 건강 악화나 고통스러운 증상(예: '시큰거리는 무릎', '침침해지는 눈')을 생생하게 묘사하여 몰입감을 높이세요.
3. **본문 (상품 추천)**:
   - 각 상품명은 단순히 나열하지 말고, 각 상품의 개성을 드러내는 수식어(예: '가성비 종결', '전문가 극찬', '대용량 끝판왕')와 함께 소개하세요.
   - 장단점을 쓸 때, 상품 상세페이지 글을 복사한 느낌이 아닌 '직접 한 달 이상 장기 복용/사용해 본 구매자의 생생한 비밀 후기'처럼 상세하게 스토리를 풀어 작성하세요.
   - 각 상품 하단에 이미지와 최저가 버튼을 다음과 같이 삽입하세요.
     - 이미지: `![상품명](이미지 주소)`
     - 버튼: `[▶ 최저가 혜택 및 리얼 후기 보러가기](구매 링크)`
4. **결론**:
   - 마지막까지 독자의 구매 전환을 강하게 촉구하며, 어떤 타겟에게 어떤 제품이 가장 완벽한 핏인지 확실하게 요약 추천해 주세요.
   - 본문 맨 끝에 쿠팡 파트너스 안내 문구('이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.')를 필수 삽입하세요.
5. 오직 발행할 본문 마크다운만 출력하고, 불필요한 서두/미사여구 대화는 배제하세요.
"""

        try:
            logging.info("OpenAI API를 통한 후킹성 포스팅 원고 생성 시작...")
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.8,
                max_tokens=2500
            )
            content = response.choices[0].message.content.strip()
            logging.info("OpenAI API 후킹성 원고 생성 완료")
            return content
        except Exception as e:
            logging.error(f"OpenAI API 호출 실패: {e} - Fallback으로 우회합니다.")
            return self._generate_fallback_post(keyword, products)

    def _generate_fallback_post(self, keyword: str, products: list) -> str:
        """API 미작동 시 생성할 강력한 후킹성 고도화 마크다운 본문"""
        title = f"\"진작 알았더라면...\" 아침 방송 난리난 {keyword} 숨겨진 효능과 안 사면 손해인 가성비 TOP 3"
        
        products_section = ""
        for idx, prod in enumerate(products, 1):
            # 수식어 부여
            labels = ["압도적 가성비 1위", "재구매율 99% 프리미엄", "부모님 선물용 선호도 1위"]
            label = labels[idx-1] if idx-1 < len(labels) else "초특가 추천작"

            products_section += f"""
### ⭐ {idx}위: {prod['productName']} ({label})
* **판매가**: {prod['productPrice']:,}원 (할인율: {prod.get('discountRate', 0)}% 적용 완료)
* **리얼 분석 리뷰**: 
  이 제품은 단순히 유명세에 의존하는 것이 아닌, 실제 고함량 원료 성분을 극대화하여 신속한 효능 체감을 이끌어냅니다. 수백 개의 후기에서 증명하듯 "섭취 2주 만에 아침에 일어날 때 몸이 가볍다"는 간증이 쏟아지는 화제의 아이템입니다. 불필요한 마케팅 비용을 걷어내어 최상급 원료 대비 가격 거품이 아예 없는 혜자로운 상품입니다.

![{prod['productName']}]({prod['productImage']})

[▶ 최저가 혜택 및 리얼 후기 보러가기]({prod['productUrl']})

---
"""

        fallback_content = f"""# {title}

"하루라도 늦으면 되돌릴 수 없습니다. 당신의 관절과 건강은 안녕하신가요?"

오늘 아침 공중파 방송에서는 나이가 들면서 하루가 다르게 파괴되는 연골과 혈관 건강을 되살리는 **{keyword}**의 충격적인 실체와 복용법이 심층적으로 다루어졌습니다. 

연골이나 혈관 벽은 한 번 망가지기 시작하면 어떤 약을 먹어도 원래 상태로 재생되지 않습니다. 많은 의사들이 "예방을 위해 하루라도 빨리 {keyword}를 섭취하여 더 이상의 소실을 차단해야 한다"고 입을 모아 경고하는 이유가 바로 여기에 있습니다.

문제는 시중에 수많은 {keyword} 제품들이 광고 문구만 요란할 뿐 정작 핵심 성분의 함량이나 체내 흡수율은 턱없이 낮다는 사실입니다. 돈 낭비하지 않고 제대로 된 진짜배기 제품을 고르는 기준과, 쿠팡에서 판매량과 후기 검증을 통과한 베스트 TOP 3를 지금 공개합니다.

---

## 🔍 절대로 실패하지 않는 {keyword} 3가지 핵심 감별법

1. **식약처 인증 고함량 확인**: 성분 함량이 무늬만 들어간 미량 제품은 아무런 효과가 없습니다. 하루 권장 기준치를 초과하여 꽉 채운 1,200mg 이상 함량을 우선 확인하세요.
2. **원료의 체내 흡수 속도**: 단순 상어 연골보다 분자 구조가 미세하여 인체 흡수율이 수 배 빠른 특수 추출 소 연골이나 저분자 공법이 들어갔는지 눈여겨봐야 합니다.
3. **가성비 장기 복용성**: 건강기능식품은 최소 3개월 이상 장기 복용해야 온전한 피드백이 나타납니다. 한 달분 가격이 부담스럽지 않은 고품질 합리적 가격의 브랜드를 골라야 합니다.

---

## 🏆 놓치면 후회하는 {keyword} 가성비 종결 추천 템

{products_section}

## 💡 최종 마케터 추천의 글
* **만일 부모님이나 어르신 선물용으로 절대 실패하고 싶지 않다면?** 👉 **2위 프리미엄** 제품을 강력히 권장합니다.
* **가장 저렴하게 최대의 효과를 누리며 매일 부담 없이 꾸준히 먹고 싶다면?** 👉 **1위 가성비 종결** 제품이 최고의 픽입니다.

"건강은 건강할 때 지키는 자만이 누릴 수 있는 특권입니다. 늦기 전에 오늘부터 투자를 시작하세요!"

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
        
        safe_keyword = "".join([c if c.isalnum() or c in ["-", "_"] else "_" for c in keyword])
        filename = f"{date_str}-{safe_keyword}.md"
        file_path = os.path.join(output_dir, filename)

        title = f"가장 합리적인 {keyword} 추천 가이드"
        lines = content.split("\n")
        for line in lines[:5]:
            if line.startswith("# "):
                title = line.replace("# ", "").strip()
                # 따옴표 중복 탈출 처리
                title = title.replace('"', '\\"')
                content = content.replace(line, "", 1).strip()
                break

        front_matter = (
            f"---\n"
            f"layout: post\n"
            f"title: \"{title}\"\n"
            f"date: {time_str}\n"
            f"categories: health\n"
            f"tags: [{keyword}, 아침방송트렌드, 추천상품, 건강정보]\n"
            f"---\n\n"
        )

        full_content = front_matter + content

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_content)
        
        logging.info(f"성공적으로 후킹성 마크다운 포스팅을 기록했습니다: {file_path}")
        return file_path

if __name__ == "__main__":
    writer = ContentWriter()
    mock_products = [
        {"productName": "가성비 콘드로이친 1200 골드", "productPrice": 29800, "productImage": "https://dummy.com/1.jpg", "productUrl": "https://link.coupang.com/a/1", "discountRate": 15},
        {"productName": "프리미엄 소연골 콘드로이친 순도 90%", "productPrice": 42000, "productImage": "https://dummy.com/2.jpg", "productUrl": "https://link.coupang.com/a/2", "discountRate": 10}
    ]
    raw_post = writer.generate_blog_post("콘드로이친", mock_products)
    saved_file = writer.write_to_markdown_file("콘드로이친", raw_post, "test_posts")
    print(f"저장된 파일: {saved_file}")
