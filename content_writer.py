"""
content_writer.py
카테고리별로 최적화된 마크다운 포스팅을 자동 생성한다.
- health       : 쿠팡 파트너스 상품 섹션 포함
- ai_news      : HTML 자동 슬라이드 배너 삽입 (상품 링크 3개 회전)
- latest_issue : HTML 자동 슬라이드 배너 삽입
"""

import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from google import genai

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ─── 슬라이드 배너에 들어갈 Coupang 딥링크 (AI·이슈 포스팅용 고정 인기 카테고리) ───
SLIDE_BANNER_LINKS = [
    {"label": "💊 오늘의 건강 베스트셀러 보러가기",  "url": "https://link.coupang.com/a/cSECTJ"},
    {"label": "🏠 생활용품 오늘의 특가 확인",        "url": "https://link.coupang.com/a/cSECTK"},
    {"label": "📱 전자기기 최저가 &amp; 리얼 후기 보기", "url": "https://link.coupang.com/a/cSECTL"},
    {"label": "🎁 부모님 선물용 건강식품 인기 TOP",  "url": "https://link.coupang.com/a/cSECTM"},
    {"label": "🌿 유산균·비타민 가성비 종결 제품",   "url": "https://link.coupang.com/a/cSECTN"},
]

SLIDE_BANNER_HTML = """
<style>
.cp-banner-wrap{{position:relative;overflow:hidden;border-radius:12px;
  background:linear-gradient(135deg,#ff6b35,#f7931e);padding:4px;margin:2em 0;}}
.cp-banner{{display:flex;transition:transform .5s ease;}}
.cp-banner-item{{min-width:100%;box-sizing:border-box;
  background:#fff;border-radius:10px;padding:20px 24px;text-align:center;}}
.cp-banner-item a{{display:block;font-weight:700;font-size:1.05rem;
  color:#e94e1b;text-decoration:none;letter-spacing:-.3px;}}
.cp-banner-item a:hover{{text-decoration:underline;}}
.cp-banner-dots{{text-align:center;margin-top:6px;}}
.cp-banner-dots span{{display:inline-block;width:8px;height:8px;margin:0 3px;
  border-radius:50%;background:#ccc;cursor:pointer;}}
.cp-banner-dots span.active{{background:#e94e1b;}}
.cp-notice{{font-size:.72rem;color:#999;text-align:center;margin-top:4px;}}
</style>
<div class="cp-banner-wrap">
  <div class="cp-banner" id="cpBanner">
    {slides}
  </div>
</div>
<div class="cp-banner-dots" id="cpDots">{dots}</div>
<p class="cp-notice">※ 이 배너는 쿠팡 파트너스 제휴 링크를 포함하며, 구매 시 일정 수수료를 제공받습니다.</p>
<script>
(function(){{
  var items=document.querySelectorAll('#cpBanner .cp-banner-item');
  var dots=document.querySelectorAll('#cpDots span');
  var idx=0;
  function go(n){{
    idx=(n+items.length)%items.length;
    document.getElementById('cpBanner').style.transform='translateX(-'+idx*100+'%)';
    dots.forEach(function(d,i){{d.className=i===idx?'active':'';}}); 
  }}
  dots.forEach(function(d,i){{d.addEventListener('click',function(){{go(i);}});}});
  setInterval(function(){{go(idx+1);}},3500);
}})();
</script>
"""


def _build_slide_banner() -> str:
    slides = "\n".join(
        f'<div class="cp-banner-item"><a href="{item["url"]}" target="_blank" rel="noopener">{item["label"]}</a></div>'
        for item in SLIDE_BANNER_LINKS
    )
    dots = "\n".join(
        f'<span class="{"active" if i == 0 else ""}"></span>'
        for i in range(len(SLIDE_BANNER_LINKS))
    )
    return SLIDE_BANNER_HTML.format(slides=slides, dots=dots)


class ContentWriter:

    def __init__(self):
        # OpenAI 세팅
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key and api_key != "your_openai_api_key_here" else None

        # Gemini 세팅
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_client = None
        self.gemini_enabled = False
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            try:
                self.gemini_client = genai.Client(api_key=gemini_key)
                self.gemini_enabled = True
                logging.info("Google Gemini API 초기화 성공")
            except Exception as e:
                logging.error(f"Google Gemini API 초기화 실패: {e}")

    # ────────────────────────────────────────────────
    # 공개 메서드
    # ────────────────────────────────────────────────
    def generate_blog_post(self, category: str, topic: dict, products: list = None) -> str:
        """카테고리에 따라 적합한 포스팅 본문(마크다운)을 생성한다."""
        if category == "health":
            return self._generate_health_post(topic["keyword"], products or [])
        elif category == "ai_news":
            return self._generate_ai_news_post(topic)
        elif category == "latest_issue":
            return self._generate_latest_issue_post(topic)
        else:
            raise ValueError(f"지원하지 않는 카테고리: {category}")

    def write_to_markdown_file(self, category: str, keyword: str, content: str) -> str:
        """Jekyll Front Matter를 부착해 _posts 폴더에 파일 저장."""
        output_dir = "_posts"
        os.makedirs(output_dir, exist_ok=True)

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Y-%m-%d %H:%M:%S +0900")

        # 파일명 정제
        safe_kw = "".join(c if c.isalnum() or c in "-_" else "_" for c in keyword)[:50]
        filename = f"{date_str}-{safe_kw}.md"
        file_path = os.path.join(output_dir, filename)

        # 제목 추출
        title = keyword
        for line in content.split("\n")[:6]:
            if line.startswith("# "):
                title = line[2:].strip().replace('"', '\\"')
                content = content.replace(line, "", 1).strip()
                break

        cat_map = {"health": "health", "ai_news": "ai-news", "latest_issue": "latest-issue"}
        tag_map = {
            "health": f"{keyword}, 아침방송트렌드, 건강정보, 추천상품",
            "ai_news": "AI뉴스, 인공지능, 최신AI트렌드",
            "latest_issue": "이슈, 실시간트렌드, 핫뉴스",
        }

        front_matter = (
            f"---\n"
            f"layout: post\n"
            f"title: \"{title}\"\n"
            f"date: {time_str}\n"
            f"categories: {cat_map.get(category, 'general')}\n"
            f"tags: [{tag_map.get(category, keyword)}]\n"
            f"---\n\n"
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(front_matter + content)

        logging.info(f"포스팅 저장 완료: {file_path}")
        return file_path

    # ────────────────────────────────────────────────
    # 건강 포스팅 (쿠팡 상품 포함)
    # ────────────────────────────────────────────────
    def _generate_health_post(self, keyword: str, products: list) -> str:
        if self.client:
            return self._gpt_health_post(keyword, products)
        elif self.gemini_enabled:
            return self._gemini_health_post(keyword, products)
        return self._fallback_health_post(keyword, products)

    def _gemini_health_post(self, keyword: str, products: list) -> str:
        product_info = "\n".join(
            f"{i+1}. {p['productName']} | 가격:{p['productPrice']}원 "
            f"| 할인:{p.get('discountRate',0)}% | 이미지:{p['productImage']} | 링크:{p['productUrl']}"
            for i, p in enumerate(products)
        )
        system = (
            "대한민국 최고 바이럴 마케터·SEO 카피라이터. "
            "후킹성 강한 제목과 스토리텔링 본문으로 구매를 유도하는 마크다운 포스팅을 작성한다."
        )
        user = f"""
키워드: {keyword}
상품목록:
{product_info}

규칙:
1. 제목(#): 독자의 고통·호기심 자극. 예 → "진작 알았더라면... 아침방송 난리난 {keyword} 비교 TOP3"
2. 서론: 오늘 아침 방송 언급 + 건강 위기감 소구
3. 상품별: 수식어(가성비 1위·재구매율 최고 등) + 장기 복용 리얼 후기 스토리텔링
         각 상품 하단: ![상품명](이미지) 및 <a href="링크" target="_blank" rel="noopener noreferrer">▶ 최저가 및 리얼 후기 보러가기</a>
4. 결론: 타겟별 최종 추천 + 구매 촉구
5. 맨 마지막: 쿠팡 파트너스 수수료 안내 문구
6. 마크다운 본문만 출력(서두 대화 제외)
"""
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=user,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system
                )
            )
            return response.text.strip()
        except Exception as e:
            logging.error(f"Gemini API 호출 실패(health): {e}")
            return self._fallback_health_post(keyword, products)

    def _gpt_health_post(self, keyword: str, products: list) -> str:
        product_info = "\n".join(
            f"{i+1}. {p['productName']} | 가격:{p['productPrice']}원 "
            f"| 할인:{p.get('discountRate',0)}% | 이미지:{p['productImage']} | 링크:{p['productUrl']}"
            for i, p in enumerate(products)
        )
        system = (
            "대한민국 최고 바이럴 마케터·SEO 카피라이터. "
            "후킹성 강한 제목과 스토리텔링 본문으로 구매를 유도하는 마크다운 포스팅을 작성한다."
        )
        user = f"""
키워드: {keyword}
상품목록:
{product_info}

규칙:
1. 제목(#): 독자의 고통·호기심 자극. 예 → "진작 알았더라면... 아침방송 난리난 {keyword} 비교 TOP3"
2. 서론: 오늘 아침 방송 언급 + 건강 위기감 소구
3. 상품별: 수식어(가성비 1위·재구매율 최고 등) + 장기 복용 리얼 후기 스토리텔링
         각 상품 하단: ![상품명](이미지) 및 <a href="링크" target="_blank" rel="noopener noreferrer">▶ 최저가 및 리얼 후기 보러가기</a>
4. 결론: 타겟별 최종 추천 + 구매 촉구
5. 맨 마지막: 쿠팡 파트너스 수수료 안내 문구
6. 마크다운 본문만 출력(서두 대화 제외)
"""
        try:
            res = self.client.chat.completions.create(
                model="gpt-4o", temperature=0.8, max_tokens=2500,
                messages=[{"role":"system","content":system},{"role":"user","content":user}]
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"OpenAI 호출 실패: {e}")
            return self._fallback_health_post(keyword, products)

    def _fallback_health_post(self, keyword: str, products: list) -> str:
        labels = ["압도적 가성비 1위 🥇", "재구매율 99% 프리미엄 🏆", "부모님 선물 선호도 1위 🎁"]
        prods_md = ""
        for i, p in enumerate(products):
            label = labels[i] if i < len(labels) else "추천 아이템"
            prods_md += f"""
### ⭐ {i+1}위: {p['productName']} ({label})
* **판매가**: {p['productPrice']:,}원 (할인 {p.get('discountRate',0)}% 적용)
* **리얼 후기**: 섭취 2주 만에 "아침에 몸이 가볍다"는 후기가 쏟아지는 검증된 아이템입니다.
  고함량 원료 대비 가격 거품이 없어 장기 복용에 부담이 없습니다.

![{p['productName']}]({p['productImage']})

<a href="{p['productUrl']}" target="_blank" rel="noopener noreferrer">▶ 최저가 혜택 및 리얼 후기 보러가기</a>

---
"""
        return f"""# "진작 알았더라면..." 아침방송 난리난 {keyword} 숨겨진 효능과 안 사면 손해인 가성비 TOP 3

"하루라도 늦으면 되돌릴 수 없습니다. 당신의 건강은 안녕하신가요?"

오늘 아침 공중파 방송에서 **{keyword}**의 충격적인 실체와 올바른 복용법이 집중 조명되었습니다.
잘못된 제품 선택 하나가 수개월의 시간과 비용을 날려버립니다.
쿠팡 판매량·후기를 전부 분석해 진짜 효과 있는 베스트 TOP 3만 추렸습니다.

---

## 🔍 절대 실패 없는 {keyword} 3가지 핵심 감별법
1. **식약처 인증 고함량**: 하루 권장량을 꽉 채운 제품인지 확인
2. **흡수율 검증 원료**: 저분자 또는 특수 추출 공법 적용 여부 체크
3. **가성비 장기 복용**: 3개월 이상 무리 없는 가격대인지 비교

---

## 🏆 놓치면 후회하는 {keyword} 가성비 종결템
{prods_md}

## 💡 마케터의 최종 한 줄 추천
* 가성비 최우선 → **1위** 선택
* 부모님·선물용 → **2위** 선택

"건강은 건강할 때 지켜야 합니다. 오늘 바로 투자를 시작하세요!"

<br>

---
*이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.*
""".strip()

    # ────────────────────────────────────────────────
    # AI 뉴스 포스팅 (슬라이드 배너)
    # ────────────────────────────────────────────────
    def _generate_ai_news_post(self, topic: dict) -> str:
        title = topic.get("title", "오늘의 AI 뉴스")
        summary = topic.get("summary", "")
        source_link = topic.get("link", "")
        banner = _build_slide_banner()

        if self.client:
            system = (
                "AI·기술 전문 블로거. SEO 최적화된 후킹성 제목과 읽기 쉬운 "
                "뉴스 해설 본문(마크다운)을 작성한다."
            )
            user = f"""
뉴스 제목: {title}
요약: {summary}
원문 링크: {source_link}

규칙:
1. 제목(#): 클릭 유도 강한 후킹 문구로 변환 (예 → "전 세계가 주목! ...")
2. 서론: 뉴스 핵심을 2~3문장으로 임팩트 있게 요약
3. 본문: 배경·의미·독자에게 미치는 영향을 3개 소제목으로 상세 설명
4. 결론: 앞으로 주목해야 할 포인트 + 독자 행동 유도
5. 마크다운 본문만 출력 (슬라이드 배너 HTML은 직접 삽입할 것이므로 제외)
"""
            try:
                res = self.client.chat.completions.create(
                    model="gpt-4o", temperature=0.75, max_tokens=2000,
                    messages=[{"role":"system","content":system},{"role":"user","content":user}]
                )
                body = res.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"OpenAI 호출 실패(ai_news): {e}")
                body = self._fallback_ai_news_body(title, summary)
        elif self.gemini_enabled:
            body = self._gemini_ai_news_body(title, summary, source_link)
        else:
            body = self._fallback_ai_news_body(title, summary)

        # 슬라이드 배너를 본문 중간(결론 직전)에 삽입
        return body + f"\n\n---\n\n## 🛒 오늘의 쇼핑 핫딜 배너\n\n{banner}"

    def _gemini_ai_news_body(self, title: str, summary: str, source_link: str) -> str:
        system = (
            "AI·기술 전문 블로거. SEO 최적화된 후킹성 제목과 읽기 쉬운 "
            "뉴스 해설 본문(마크다운)을 작성한다."
        )
        user = f"""
뉴스 제목: {title}
요약: {summary}
원문 링크: {source_link}

규칙:
1. 제목(#): 클릭 유도 강한 후킹 문구로 변환 (예 → "전 세계가 주목! ...")
2. 서론: 뉴스 핵심을 2~3문장으로 임팩트 있게 요약
3. 본문: 배경·의미·독자에게 미치는 영향을 3개 소제목으로 상세 설명
4. 결론: 앞으로 주목해야 할 포인트 + 독자 행동 유도
5. 마크다운 본문만 출력 (설명이나 인사말 등은 제외)
"""
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=user,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system
                )
            )
            return response.text.strip()
        except Exception as e:
            logging.error(f"Gemini API 호출 실패(ai_news): {e}")
            return self._fallback_ai_news_body(title, summary)

    def _fallback_ai_news_body(self, title: str, summary: str) -> str:
        return f"""# 🤖 전 세계가 주목! {title}

지금 AI·IT 업계에서 가장 뜨거운 이슈가 터졌습니다.
{summary or "인공지능 기술이 또 한 번 패러다임을 바꾸는 소식이 들려오고 있습니다."}

---

## 📌 핵심 내용 요약

AI 기술의 발전 속도가 점점 빨라지면서 일상과 산업 전반에 걸친 변화가 가속화되고 있습니다.
이번 뉴스는 그중에서도 특히 **실생활 적용 가능성**이 높은 내용으로, 전문가들 사이에서 큰 반향을 일으키고 있습니다.

## 🔍 이 뉴스가 중요한 이유

1. **산업 변화**: 기존 업무 방식과 비즈니스 모델에 직접적인 영향을 미칩니다.
2. **일상 적용**: 일반 소비자도 곧 체감할 수 있는 실질적인 변화가 예상됩니다.
3. **글로벌 경쟁**: 국내외 기업들이 발 빠르게 대응 전략을 수립 중입니다.

## 💡 앞으로 주목해야 할 포인트

AI 트렌드는 단순한 기술 이슈를 넘어 **투자·취업·교육** 전반에 영향을 미칩니다.
지금 이 흐름을 놓치지 않도록, 최신 AI 뉴스를 매일 팔로우하세요!
""".strip()

    # ────────────────────────────────────────────────
    # 최신 이슈 포스팅 (슬라이드 배너)
    # ────────────────────────────────────────────────
    def _generate_latest_issue_post(self, topic: dict) -> str:
        title = topic.get("title", "오늘의 핫이슈")
        summary = topic.get("summary", "")
        banner = _build_slide_banner()

        if self.client:
            system = "바이럴 콘텐츠 전문가. 후킹성 강한 제목과 몰입감 있는 이슈 해설 마크다운을 작성한다."
            user = f"""
이슈 키워드: {title}
검색 동향: {summary}

규칙:
1. 제목(#): 호기심 폭발 후킹 문구 (예 → "왜 갑자기 모두가 '{title}'을 검색하나?")
2. 서론: 이슈의 배경과 사람들이 관심 갖는 이유를 생생하게 소개
3. 본문: 이슈의 전말·다양한 시각·향후 전망을 3개 소제목으로 상세 서술
4. 결론: 핵심 정리 + 독자에게 액션 촉구
5. 마크다운 본문만 출력 (배너 HTML 제외)
"""
            try:
                res = self.client.chat.completions.create(
                    model="gpt-4o", temperature=0.8, max_tokens=2000,
                    messages=[{"role":"system","content":system},{"role":"user","content":user}]
                )
                body = res.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"OpenAI 호출 실패(latest_issue): {e}")
                body = self._fallback_issue_body(title, summary)
        elif self.gemini_enabled:
            body = self._gemini_issue_body(title, summary)
        else:
            body = self._fallback_issue_body(title, summary)

        return body + f"\n\n---\n\n## 🛒 오늘의 쇼핑 핫딜 배너\n\n{banner}"

    def _gemini_issue_body(self, title: str, summary: str) -> str:
        system = "바이럴 콘텐츠 전문가. 후킹성 강한 제목과 몰입감 있는 이슈 해설 마크다운을 작성한다."
        user = f"""
이슈 키워드: {title}
검색 동향: {summary}

규칙:
1. 제목(#): 호기심 폭발 후킹 문구 (예 → "왜 갑자기 모두가 '{title}'을 검색하나?")
2. 서론: 이슈의 배경과 사람들이 관심 갖는 이유를 생생하게 소개
3. 본문: 이슈의 전말·다양한 시각·향후 전망을 3개 소제목으로 상세 서술
4. 결론: 핵심 정리 + 독자에게 액션 촉구
5. 마크다운 본문만 출력 (설명이나 인사말 등은 제외)
"""
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-1.5-flash',
                contents=user,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system
                )
            )
            return response.text.strip()
        except Exception as e:
            logging.error(f"Gemini API 호출 실패(latest_issue): {e}")
            return self._fallback_issue_body(title, summary)

    def _fallback_issue_body(self, title: str, summary: str) -> str:
        return f"""# 🔥 왜 갑자기 모두가 '{title}'을 검색하나? 지금 바로 확인하세요

{summary or "지금 대한민국에서 가장 뜨거운 키워드가 등장했습니다!"}
이 이슈 하나가 오늘 하루 온라인을 가득 채웠고, 수십만 명이 동시에 검색창에 이 단어를 입력했습니다.

---

## 📌 이슈의 핵심, 30초 만에 파악하기

**{title}** — 이 키워드가 갑자기 급상승한 데에는 분명한 이유가 있습니다.
단순한 해프닝을 넘어 많은 사람들의 공감을 이끌어낸 사회적 맥락이 담겨 있습니다.

## 🔍 다양한 시각으로 본 이번 이슈

1. **화제의 중심**: 이슈의 발단과 전개 과정을 시간순으로 정리했습니다.
2. **여론의 반응**: 각계각층의 다양한 반응과 의견이 엇갈리고 있습니다.
3. **앞으로의 전망**: 이 이슈가 어디까지 이어질지, 전문가 시각을 담았습니다.

## 💬 당신의 생각은?

매일 새로운 이슈가 터지는 세상, 중요한 건 빠른 판단입니다.
오늘 이슈도 북마크해 두고 흐름을 놓치지 마세요!
""".strip()


if __name__ == "__main__":
    writer = ContentWriter()
    mock_products = [
        {"productName": "가성비 콘드로이친 1200 골드",        "productPrice": 29800,
         "productImage": "/assets/images/posts/test1.jpg",   "productUrl": "https://link.coupang.com/a/1", "discountRate": 15},
        {"productName": "프리미엄 소연골 콘드로이친 순도 90%", "productPrice": 42000,
         "productImage": "/assets/images/posts/test2.jpg",   "productUrl": "https://link.coupang.com/a/2", "discountRate": 10},
    ]

    for cat, topic in [
        ("health",       {"keyword": "콘드로이친", "title": "콘드로이친", "summary": ""}),
        ("ai_news",      {"keyword": "ChatGPT", "title": "ChatGPT-5 출시 임박", "summary": "OpenAI가 차세대 모델 발표를 준비 중", "link": ""}),
        ("latest_issue", {"keyword": "아이유", "title": "아이유", "summary": "급상승 검색어 1위"}),
    ]:
        print(f"\n{'='*60}")
        content = writer.generate_blog_post(cat, topic, mock_products if cat == "health" else None)
        saved   = writer.write_to_markdown_file(cat, topic["keyword"], content)
        print(f"[{cat}] 저장: {saved}")
