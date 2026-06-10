import os
import requests
import logging
import re
from datetime import datetime
from dotenv import load_dotenv

# 모듈 로드
from keyword_analyzer import KeywordAnalyzer
from coupang_partner import CoupangPartnerAPI
from content_writer import ContentWriter

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class AutoPublisherController:
    """전체 자동화 수익 블로그 발행 단계를 총괄하는 컨트롤러"""

    def __init__(self):
        self.analyzer = KeywordAnalyzer()
        self.coupang = CoupangPartnerAPI()
        self.writer = ContentWriter()
        self.image_dir = "assets/images/posts"
        self.post_dir = "_posts"

    def _ensure_directories(self):
        """이미지 및 포스팅 폴더 생성 보장"""
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)
            logging.info(f"이미지 디렉터리 생성: {self.image_dir}")
        if not os.path.exists(self.post_dir):
            os.makedirs(self.post_dir)
            logging.info(f"포스팅 디렉터리 생성: {self.post_dir}")

    def _download_product_images(self, keyword: str, products: list) -> list:
        """[방안 B] 상품 썸네일 이미지를 다운로드하여 로컬 assets 폴더에 저장하고 상대 경로로 업데이트"""
        self._ensure_directories()
        date_str = datetime.now().strftime("%Y-%m-%d")
        
        # 파일명 정제 (한글/영어/숫자 외 제거)
        safe_keyword = re.sub(r'[^a-zA-Z0-9가-힣_-]', '_', keyword)

        updated_products = []
        for idx, prod in enumerate(products, 1):
            original_img_url = prod.get("productImage")
            # 기본 쿠팡 이미지 또는 dummy 이미지일 경우 통과
            if not original_img_url or "dummy.com" in original_img_url:
                updated_products.append(prod)
                continue

            # 파일명 규칙: YYYY-MM-DD-keyword-{index}.jpg
            img_filename = f"{date_str}-{safe_keyword}-{idx}.jpg"
            local_img_path = os.path.join(self.image_dir, img_filename)
            
            # 마크다운 본문에 삽입될 블로그 루트 기준의 경로
            blog_relative_path = f"/assets/images/posts/{img_filename}"

            try:
                logging.info(f"상품 이미지 다운로드 시도 ({idx}): {original_img_url}")
                # 쿠팡 이미지 서버의 차단을 피하기 위한 기본 헤더 설정
                headers = {"User-Agent": "Mozilla/5.0"}
                img_res = requests.get(original_img_url, headers=headers, timeout=10)
                
                if img_res.status_code == 200:
                    with open(local_img_path, "wb") as f:
                        f.write(img_res.content)
                    logging.info(f"이미지 로컬 저장 성공: {local_img_path}")
                    # 복사하여 이미지 경로 수정
                    updated_prod = prod.copy()
                    updated_prod["productImage"] = blog_relative_path
                    updated_products.append(updated_prod)
                else:
                    logging.warning(f"이미지 다운로드 실패 (HTTP {img_res.status_code}) - 원본 링크를 유지합니다.")
                    updated_products.append(prod)
            except Exception as e:
                logging.error(f"이미지 다운로드 예외 발생: {e} - 원본 링크를 유지합니다.")
                updated_products.append(prod)
        return updated_products

    def run_pipeline(self):
        """자동화 파이프라인의 전체 실행 컨트롤"""
        logging.info("=========================================")
        logging.info("자동화 포스팅 파이프라인 실행 시작")
        logging.info("=========================================")

        # 1단계: 오늘의 건강 타겟 키워드 선정 (아침 방송 기반)
        target_keyword = self.analyzer.get_target_keyword()
        logging.info(f"선정된 오늘의 키워드: {target_keyword}")

        # 2단계: 쿠팡 파트너스 API 상품 수집
        products = self.coupang.search_products(target_keyword, limit=3)
        if not products:
            logging.error("추천할 상품 리스트를 수집하지 못했습니다. 파이프라인을 종료합니다.")
            return

        # 3단계: 이미지 로컬 다운로드 가동 [방안 B]
        processed_products = self._download_product_images(target_keyword, products)

        # 4단계: AI 콘텐츠 초안 생성 (OpenAI API 또는 Fallback)
        raw_content = self.writer.generate_blog_post(target_keyword, processed_products)

        # 5단계: Jekyll/Hugo 포스팅 마크다운 파일로 영구 기록
        saved_file = self.writer.write_to_markdown_file(target_keyword, raw_content, self.post_dir)

        logging.info("=========================================")
        logging.info(f"파이프라인 성공 완료. 생성된 포스트: {saved_file}")
        logging.info("=========================================")

if __name__ == "__main__":
    controller = AutoPublisherController()
    controller.run_pipeline()
