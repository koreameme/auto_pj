"""
content_writer.py
카테고리별로 최적화된 마크다운 포스팅을 자동 생성한다.
- health       : 쿠팡 파트너스 상품 섹션 포함
- ai_news      : HTML 자동 슬라이드 배너 삽입 (상품 링크 3개 회전)
- latest_issue : HTML 자동 슬라이드 배너 삽입
"""

import os
import re
import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone

def _now_kst():
    """GitHub Actions(UTC 환경) 및 로컬 모두에서 KST 시간을 정확히 반환"""
    return datetime.now(timezone.utc) + timedelta(hours=9)

def _make_description(body: str, max_len: int = 155) -> str:
    """본문에서 SEO용 meta description 자동 추출 (이모지·마크다운 제거)"""
    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '', body)
    # 마크다운 이미지/링크 제거
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', text)
    # 마크다운 기호 제거
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'[*_`~>#\-]', '', text)
    # 이모지 제거 (유니코드 대역 기반)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    # 불필요한 공백/개행 정리
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return ""
    
    # 문장 구분을 위해 온점으로 쪼개어 첫 번째 의미 있는 문장을 찾는다.
    for part in text.split('.'):
        part = part.strip()
        if len(part) > 20:
            desc = (part[:max_len] + '...') if len(part) > max_len else part + '.'
            return desc.replace('"', "'")
            
    # 의미 있는 긴 문장이 없으면 그냥 잘라서 반환
    desc = (text[:max_len] + '...') if len(text) > max_len else text
    return desc.replace('"', "'")

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


def _parse_ai_response(response_text: str, keyword: str) -> dict:
    """AI 응답 텍스트에서 [TITLE], [SLUG], [BODY]를 파싱하여 반환한다."""
    title = keyword
    slug = ""
    body = response_text

    # 대소문자 구분 없이 매칭하고 앞뒤 공백 제거
    title_match = re.search(r'\[TITLE\]\s*(.*?)\s*(?=\[SLUG\]|\[BODY\]|$)', response_text, re.IGNORECASE | re.DOTALL)
    slug_match = re.search(r'\[SLUG\]\s*(.*?)\s*(?=\[TITLE\]|\[BODY\]|$)', response_text, re.IGNORECASE | re.DOTALL)
    body_match = re.search(r'\[BODY\]\s*(.*?)\s*(?=\[TITLE\]|\[SLUG\]|$)', response_text, re.IGNORECASE | re.DOTALL)

    if title_match:
        title = title_match.group(1).strip().replace('"', "'")
    if slug_match:
        raw_slug = slug_match.group(1).strip().lower()
        slug = re.sub(r'[^a-z0-9-]', '-', raw_slug)
        slug = re.sub(r'-+', '-', slug).strip('-')
    if body_match:
        body = body_match.group(1).strip()

    if not slug:
        h = hashlib.md5(response_text.encode('utf-8')).hexdigest()[:6]
        slug = f"post-{h}"

    # 제목이 마크다운 헤더로 시작하면 # 제거
    if title.startswith("# "):
        title = title[2:].strip().replace('"', "'")

    # 구분자가 전혀 없을 때의 폴백: 첫 번째 라인을 제목으로 파싱하고 본문에서 제거
    if not title_match and body.startswith("# "):
        lines = body.split("\n")
        first_line = lines[0]
        title = first_line[2:].strip().replace('"', "'")
        body = "\n".join(lines[1:]).strip()

    return {"title": title, "slug": slug, "body": body}


FORMAT_INSTRUCTION = """
반드시 아래와 같은 포맷으로만 출력하세요. 다른 인사말이나 설명은 일절 생략하세요:

[TITLE]
(여기에 후킹성이 강한 매력적인 국문 제목을 작성)
[SLUG]
(여기에 제목이나 키워드에 어울리는 3~5단어 내외의 영문 소문자 및 하이픈(-) 조합의 URL 슬러그를 작성. 예: goat-milk-protein)
[BODY]
(여기에 마크다운 형식의 블로그 본문을 작성. 마크다운 첫 줄에 제목(#)은 넣지 마세요.)
"""


class ContentWriter:

    def __init__(self):
        # OpenAI 세팅
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key and api_key != "your_openai_api_key_here" else None

        # 디버그 로그용 리스트 초기화
        self.debug_logs = []
        self.debug_logs.append("=== ContentWriter Initialization Debug ===")

        # Gemini 세팅 (다중 API 키 로드)
        gemini_keys_str = os.getenv("GEMINI_API_KEYS", "")
        self.api_keys = [k.strip() for k in gemini_keys_str.split(",") if k.strip()]
        
        self.debug_logs.append(f"GEMINI_API_KEYS 환경변수 길이: {len(gemini_keys_str)}")
        
        # GEMINI_API_KEYS가 없으면 기존 GEMINI_API_KEY 사용
        if not self.api_keys:
            single_key = os.getenv("GEMINI_API_KEY", "")
            self.debug_logs.append(f"GEMINI_API_KEY 환경변수 존재 여부: {bool(single_key)}")
            if single_key and single_key != "your_gemini_api_key_here":
                self.api_keys = [single_key]
        
        self.debug_logs.append(f"로드된 API 키 개수: {len(self.api_keys)}")
        if self.api_keys:
            masked = [f"{k[:6]}...{k[-4:]}" if len(k) > 10 else "invalid_key" for k in self.api_keys]
            self.debug_logs.append(f"로드된 API 키 목록: {', '.join(masked)}")
        
        self.current_key_idx = 0
        self.gemini_client = None
        self.gemini_enabled = False
        
        if self.api_keys:
            try:
                self.gemini_client = genai.Client(api_key=self.api_keys[self.current_key_idx])
                self.gemini_enabled = True
                logging.info(f"Google Gemini API 초기화 성공 (총 {len(self.api_keys)}개 키 로드)")
                self.debug_logs.append(f"Google Gemini API 초기화 성공 (첫 번째 키 활성화)")
            except Exception as e:
                logging.error(f"Google Gemini API 초기화 실패: {e}")
                self.debug_logs.append(f"Google Gemini API 초기화 실패 에러: {e}")

    # ────────────────────────────────────────────────
    # 공개 메서드
    # ────────────────────────────────────────────────
    def _call_gemini_api(self, user_prompt: str, system_prompt: str) -> str:
        """429 쿼터 초과 시 API 키를 자동으로 다음 키로 로테이션하여 호출하는 헬퍼 메서드"""
        if not self.gemini_enabled or not self.api_keys:
            self.debug_logs.append("API 호출 차단: Gemini API가 비활성화되어 있거나 키 목록이 비어있습니다.")
            raise Exception("Gemini API가 활성화되지 않았거나 API 키가 없습니다.")
            
        total_keys = len(self.api_keys)
        
        for attempt in range(total_keys):
            try:
                # 현재 클라이언트가 없거나 인덱스가 바뀐 경우 재생성
                if self.gemini_client is None:
                    self.gemini_client = genai.Client(api_key=self.api_keys[self.current_key_idx])
                    
                response = self.gemini_client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=user_prompt,
                    config=genai.types.GenerateContentConfig(
                        system_instruction=system_prompt
                    )
                )
                self.debug_logs.append(f"API 호출 성공 (시도 #{attempt+1}, 사용된 키 인덱스: {self.current_key_idx})")
                return response.text.strip()
            except Exception as e:
                err_str = str(e)
                self.debug_logs.append(f"API 호출 실패 (시도 #{attempt+1}, 키 인덱스: {self.current_key_idx}) - 에러: {err_str[:120]}")
                # 429 Resource Exhausted 에러 발생 시 다음 키로 스위칭
                if '429' in err_str:
                    next_idx = (self.current_key_idx + 1) % total_keys
                    logging.warning(
                        f"Gemini API 429 쿼터 초과 감지. "
                        f"현재 키(인덱스 {self.current_key_idx}) -> 다음 키(인덱스 {next_idx})로 전환하여 재시도합니다. (시도 {attempt + 1}/{total_keys})"
                    )
                    self.current_key_idx = next_idx
                    # 클라이언트 객체 초기화 (다음 루프에서 새 키로 재생성되도록 함)
                    self.gemini_client = None
                    time.sleep(1) # 짧은 대기 후 즉시 재시도
                    continue
                # 429 외의 다른 에러는 즉시 예외를 발생시킴
                logging.error(f"Gemini API 호출 중 오류 발생: {e}")
                self.debug_logs.append(f"API 호출 즉시 중단 에러: {err_str[:120]}")
                raise e
                
        # 모든 키가 한도 초과된 경우
        self.debug_logs.append("API 호출 최종 실패: 모든 API 키의 하루 쿼터(429)가 초과되었습니다.")
        raise Exception("모든 등록된 Gemini API 키의 하루 쿼터(한도)가 초과되었습니다.")

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

    def write_to_markdown_file(self, category: str, keyword: str, content: str) -> tuple:
        """Jekyll Front Matter를 부착해 _posts 폴더에 파일 저장."""
        output_dir = "_posts"
        os.makedirs(output_dir, exist_ok=True)

        now = _now_kst()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Y-%m-%d %H:%M:%S +0900")

        parsed = _parse_ai_response(content, keyword)
        title = parsed["title"]
        slug = parsed["slug"]
        body = parsed["body"]

        # 본문에 간혹 들어가는 잘못된 이미지 도메인 주소(예: https://auto_pj/...) 및 슬래시 누락 경로 보정
        body = re.sub(r'(?:https?://)?/?auto_pj/assets/images/', r'/auto_pj/assets/images/', body)

        filename = f"{date_str}-{slug}.md"
        file_path = os.path.join(output_dir, filename)

        cat_map = {"health": "health", "ai_news": "ai-news", "latest_issue": "latest-issue"}
        tag_map = {
            "health": f"{keyword}, 아침방송트렌드, 건강정보, 추천상품",
            "ai_news": "AI뉴스, 인공지능, 최신AI트렌드",
            "latest_issue": "이슈, 실시간트렌드, 핫뉴스",
        }

        # ─── 대표 이미지(썸네일) 파싱 및 기본 이미지 매핑 로직 ───
        img_match = re.search(r'!\[.*?\]\((.*?)\)', body)
        image_path = ""
        if img_match:
            raw_img_path = img_match.group(1).strip()
            # baseurl 제거 처리 (예: /auto_pj/assets/images/... -> assets/images/...)
            baseurl = "/auto_pj"
            if raw_img_path.startswith(f"{baseurl}/"):
                image_path = raw_img_path[len(baseurl)+1:]
            elif raw_img_path.startswith("/"):
                image_path = raw_img_path[1:]
            else:
                image_path = raw_img_path
        else:
            # 본문에 이미지가 없을 때 (ai_news, latest_issue 등)
            # title 해시값 기반으로 assets/images/1.jpg ~ 17.jpg 중 하나 지정
            h_val = int(hashlib.md5(title.encode('utf-8')).hexdigest(), 16)
            img_idx = (h_val % 17) + 1
            image_path = f"assets/images/{img_idx}.jpg"

        description = _make_description(body)
        front_matter = (
            f"---\n"
            f"layout: post\n"
            f"title: \"{title}\"\n"
            f"date: {time_str}\n"
            f"permalink: /posts/{slug}/\n"
            f"image: {image_path}\n"
            f"author: admin\n"
            f"description: \"{description}\"\n"
            f"categories: {cat_map.get(category, 'general')}\n"
            f"tags: [{tag_map.get(category, keyword)}]\n"
            f"---\n\n"
        )

        # 포스팅 하단에 디버그용 HTML 주석을 덧붙임
        debug_comment = ""
        if hasattr(self, 'debug_logs') and self.debug_logs:
            debug_comment = "\n\n<!-- [AI GENERATION DEBUG]\n" + "\n".join(self.debug_logs) + "\n-->"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(front_matter + body + debug_comment)

        logging.info(f"포스팅 저장 완료: {file_path} (대표 이미지: {image_path})")
        return file_path, slug

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
{FORMAT_INSTRUCTION}
"""
        try:
            return self._call_gemini_api(user, system)
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
{FORMAT_INSTRUCTION}
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
        title = f"\"진작 알았더라면...\" 아침방송 난리난 {keyword} 숨겨진 효능과 안 사면 손해인 가성비 TOP 3"
        
        h = hashlib.md5(keyword.encode('utf-8')).hexdigest()[:6]
        slug = f"health-{h}-top3"
        
        body = f"""
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
        return f"[TITLE]\n{title}\n[SLUG]\n{slug}\n[BODY]\n{body}"

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
{FORMAT_INSTRUCTION}
"""
            try:
                res = self.client.chat.completions.create(
                    model="gpt-4o", temperature=0.75, max_tokens=2000,
                    messages=[{"role":"system","content":system},{"role":"user","content":user}]
                )
                body_raw = res.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"OpenAI 호출 실패(ai_news): {e}")
                body_raw = self._fallback_ai_news_body(title, summary)
        elif self.gemini_enabled:
            body_raw = self._gemini_ai_news_body(title, summary, source_link)
        else:
            body_raw = self._fallback_ai_news_body(title, summary)

        parsed = _parse_ai_response(body_raw, title)
        banner_body = parsed["body"] + f"\n\n---\n\n## 🛒 오늘의 쇼핑 핫딜 배너\n\n{banner}"
        
        return f"[TITLE]\n{parsed['title']}\n[SLUG]\n{parsed['slug']}\n[BODY]\n{banner_body}"

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
{FORMAT_INSTRUCTION}
"""
        try:
            return self._call_gemini_api(user, system)
        except Exception as e:
            logging.error(f"Gemini API 호출 실패(ai_news): {e}")
            return self._fallback_ai_news_body(title, summary)

    def _fallback_ai_news_body(self, title: str, summary: str) -> str:
        h = hashlib.md5(title.encode('utf-8')).hexdigest()[:6]
        slug = f"ai-news-{h}"
        body = f"""
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
        return f"[TITLE]\n🤖 전 세계가 주목! {title}\n[SLUG]\n{slug}\n[BODY]\n{body}"

    # ────────────────────────────────────────────────
    # 최신 이슈 포스팅 (슬라이드 배너) - AI 작성 우선
    # ────────────────────────────────────────────────
    def _generate_latest_issue_post(self, topic: dict) -> str:
        title = topic.get("title", "오늘의 핫이슈")
        summary = topic.get("summary", "")
        banner = _build_slide_banner()

        if self.client:
            # OpenAI를 우선 시도
            system = "대한민국 최고 바이럴 콘텐츠 전문가. 실시간 트렌드 이슈를 깊이 있게 분석하고 독자를 끌어당기는 매력적인 한국어 마크다운 포스팅을 작성한다."
            user = f"""
이슈 키워드: {title}
검색 동향: {summary}

아래 요구사항을 반드시 지켜 포스팅을 작성하세요:
1. 서론: 이슈가 왜 지금 화제인지 배경과 맥락을 생생하게 2~3문단으로 서술
2. ## 이슈 배경 파헤치기: 사건/상황의 경위와 핵심 내용을 400자 이상 상세 설명
3. ## 각계의 반응과 논쟁: 찬성/반대 혹은 다양한 입장을 구체적 근거와 함께 400자 이상 서술
4. ## 사회적 파급력과 향후 전망: 이 이슈가 미칠 영향과 앞으로의 전개 방향을 300자 이상 예측
5. ## 핵심 정리: 독자가 꼭 알아야 할 3가지 포인트를 bullet point로 정리
6. 결론: 독자에게 공유·댓글 참여를 유도하는 액션 촉구 문장으로 마무리
- 전체 본문은 반드시 1,500자 이상으로 작성할 것
- 이모지를 소제목·핵심 단어에 적극 활용할 것
{FORMAT_INSTRUCTION}
"""
            try:
                res = self.client.chat.completions.create(
                    model="gpt-4o", temperature=0.8, max_tokens=2500,
                    messages=[{"role":"system","content":system},{"role":"user","content":user}]
                )
                body_raw = res.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"OpenAI 호출 실패(latest_issue): {e}")
                # OpenAI 실패 시 Gemini fallback 시도
                if self.gemini_enabled:
                    logging.info("OpenAI 실패 -> Gemini로 latest_issue 생성 재시도")
                    body_raw = self._gemini_issue_body(title, summary)
                else:
                    body_raw = self._fallback_issue_body(title, summary)
        elif self.gemini_enabled:
            body_raw = self._gemini_issue_body(title, summary)
        else:
            body_raw = self._fallback_issue_body(title, summary)

        parsed = _parse_ai_response(body_raw, title)
        banner_body = parsed["body"] + f"\n\n---\n\n## 🛒 오늘의 쇼핑 핫딜 배너\n\n{banner}"
        
        return f"[TITLE]\n{parsed['title']}\n[SLUG]\n{parsed['slug']}\n[BODY]\n{banner_body}"

    def _gemini_issue_body(self, title: str, summary: str) -> str:
        """Gemini AI를 사용해 최신 이슈 포스팅 본문을 생성한다."""
        system = "대한민국 최고 바이럴 콘텐츠 전문가. 실시간 트렌드 이슈를 깊이 있게 분석하고 독자를 끌어당기는 매력적인 한국어 마크다운 포스팅을 작성한다."
        user = f"""
이슈 키워드: {title}
검색 동향: {summary}

아래 요구사항을 반드시 지켜 포스팅을 작성하세요:
1. 서론: 이슈가 왜 지금 화제인지 배경과 맥락을 생생하게 2~3문단으로 서술
2. ## 이슈 배경 파헤치기: 사건/상황의 경위와 핵심 내용을 400자 이상 상세 설명
3. ## 각계의 반응과 논쟁: 찬성/반대 혹은 다양한 입장을 구체적 근거와 함께 400자 이상 서술
4. ## 사회적 파급력과 향후 전망: 이 이슈가 미칠 영향과 앞으로의 전개 방향을 300자 이상 예측
5. ## 핵심 정리: 독자가 꼭 알아야 할 3가지 포인트를 bullet point로 정리
6. 결론: 독자에게 공유·댓글 참여를 유도하는 액션 촉구 문장으로 마무리
- 전체 본문은 반드시 1,500자 이상으로 작성할 것
- 이모지를 소제목·핵심 단어에 적극 활용할 것
{FORMAT_INSTRUCTION}
"""
        try:
            result = self._call_gemini_api(user, system)
            logging.info(f"[latest_issue] Gemini AI 포스팅 생성 완료: {title[:30]}")
            return result
        except Exception as e:
            logging.error(f"Gemini API 호출 실패(latest_issue): {e}")
            return self._fallback_issue_body(title, summary)

    def _fallback_issue_body(self, title: str, summary: str) -> str:
        """AI API 완전 실패 시 사용하는 최소 품질 보장 fallback 템플릿."""
        h = hashlib.md5(title.encode('utf-8')).hexdigest()[:6]
        slug = f"issue-{h}"
        traffic_info = summary if summary else "검색량 급상승 중"
        body = f"""지금 대한민국 검색창이 폭발하고 있습니다. **'{title}'** — 이 키워드 하나가 오늘 하루 온라인을 가득 채웠습니다. {traffic_info}이라는 수치가 말해주듯, 수십만 명이 동시에 이 단어를 검색했습니다. 왜 지금, 이 이슈인 걸까요?

---

## 📌 이슈 배경 파헤치기

**{title}**이(가) 갑자기 급상승한 데에는 분명한 이유가 있습니다. 이 이슈는 단순한 해프닝을 넘어 우리 사회의 다양한 층위와 맞닿아 있습니다. 최근 몇 가지 사건과 변화가 맞물리면서 대중의 관심이 한꺼번에 쏠렸고, 그 결과 실시간 트렌드 상위권을 차지하게 됐습니다.

이슈의 핵심은 **"왜 지금인가?"**라는 질문에 있습니다. 비슷한 주제가 과거에도 논의됐지만, 현재의 사회·경제·문화적 맥락과 맞물리면서 새로운 의미와 파급력을 가지게 됐습니다. 많은 사람들이 이 이슈에 자신의 이야기를 투영하고, 다양한 감정과 의견을 쏟아내고 있는 것은 바로 그런 이유 때문입니다.

---

## 🔍 각계의 반응과 논쟁

이슈가 터지자마자 온라인 커뮤니티와 SNS에는 다양한 시각이 넘쳐났습니다.

**찬성/공감하는 측**에서는 "이 문제는 오래전부터 예견됐다", "이제서야 제대로 짚어봐야 할 때"라는 반응이 주를 이뤘습니다. 특히 해당 이슈로 직접적인 영향을 받는 당사자들 사이에서는 자신의 경험담을 공유하며 공감 여론이 형성되고 있습니다.

반면 **반대/우려하는 측**에서는 "과도한 반응이다", "근본적인 해결책 없이 소모적인 논쟁만 이어진다"는 목소리도 적지 않습니다. 전문가들은 이 이슈가 단순히 개인 차원의 문제가 아닌, 사회 구조적인 문제와 깊게 연결되어 있다고 분석합니다.

---

## 📊 사회적 파급력과 향후 전망

이번 이슈는 단기적인 화제로 끝나지 않을 전망입니다. 이미 관련 커뮤니티와 미디어에서 후속 보도가 이어지고 있으며, 관계 기관과 전문가들의 공식 반응도 나오기 시작했습니다.

앞으로 이 이슈가 어떻게 전개될지는 **여론의 지속성**과 **당사자들의 대응**에 달려 있습니다. 과거 비슷한 이슈들이 사회 변화를 이끌어낸 사례를 참고하면, 이번에도 의미 있는 논의와 변화로 이어질 가능성이 충분합니다. 무엇보다 중요한 것은 이 이슈를 일회성 이벤트로 소비하지 않고, 깊이 있는 대화로 발전시키는 것입니다.

---

## ✅ 핵심 정리

- 🔑 **이슈 핵심**: '{title}' 키워드가 실시간 급상승하며 대중의 폭발적 관심을 받고 있음
- 🗣️ **반응**: 찬반 의견이 팽팽히 맞서는 가운데, 사회적 공감대 형성이 진행 중
- 🔮 **전망**: 단기 화제성을 넘어 사회 구조적 논의로 발전할 가능성 높음

이 이슈, 당신은 어떻게 생각하시나요? 댓글로 의견을 남겨주세요! 그리고 주변 지인들과 이 글을 공유해서 더 넓은 대화로 이어가 보세요. 🙌""".strip()
        return f"[TITLE]\n🔥 왜 갑자기 모두가 '{title}'을 검색하나? 지금 바로 확인하세요\n[SLUG]\n{slug}\n[BODY]\n{body}"


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
        saved_file, slug = writer.write_to_markdown_file(cat, topic["keyword"], content)
        print(f"[{cat}] 저장: {saved_file} (슬러그: {slug})")
