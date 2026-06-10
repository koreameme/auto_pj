import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
import random
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class KeywordAnalyzer:
    """실시간 트렌드 및 아침 건강 정보 방송(KBS/MBC) 기반 키워드 분석기"""

    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
        ]
        # 대표적인 아침 건강 방송 단골 주제 및 상품 키워드 사전 (크롤링 차단 대비 Fallback)
        self.health_keywords = [
            "콘드로이친", "보스웰리아", "MSM", "상어연골", "초록입홍합", # 관절 건강
            "유산균", "프로바이오틱스", "프리바이오틱스", "포스트바이오틱스", # 장 건강/면역
            "콜라겐", "엘라스틴", "글루타치온", # 피부 미용
            "단백질", "산양유 단백질", "초유 단백질", "유청 단백질", # 근력/영양
            "루테인", "아스타잔틴", "지아잔틴", # 눈 건강
            "크릴오일", "오메가3", "알티지 오메가3", # 혈관/오일
            "쏘팔메토", "옥타코사놀", # 남성 건강
            "멀티비타민", "비타민D", "비타민C", "마그네슘", "밀크씨슬", # 종합 영양
            "안마의자", "손마사지기", "족욕기", "저주파 마사지기" # 건강 보조 기기
        ]

    def get_headers(self):
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3"
        }

    def fetch_kbs_health_topics(self) -> list:
        """KBS 무엇이든 물어보세요 최근 방영 정보 파싱"""
        url = "https://program.kbs.co.kr/1tv/culture/ask/pc/list.html?smenu=c19a9d"
        topics = []
        try:
            logging.info("KBS '무엇이든 물어보세요' 방송 정보 수집 중...")
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                # 회차 정보 리스트 항목 파싱 (KBS 퍼블리싱 태그 구조에 기인)
                titles = soup.select(".title, .subject, a strong")
                for t in titles:
                    text = t.get_text().strip()
                    if len(text) > 5:
                        topics.append(text)
            logging.info(f"KBS 파싱 성공: {len(topics)}개 주제 수집")
        except Exception as e:
            logging.error(f"KBS 수집 실패: {e}")
        return topics

    def fetch_mbc_health_topics(self) -> list:
        """MBC 기분 좋은 날 최근 방영 정보 파싱"""
        url = "https://program.imbc.com/Gibu"
        topics = []
        try:
            logging.info("MBC '기분 좋은 날' 방송 정보 수집 중...")
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                titles = soup.select(".title, .txt, .subject")
                for t in titles:
                    text = t.get_text().strip()
                    if len(text) > 5:
                        topics.append(text)
            logging.info(f"MBC 파싱 성공: {len(topics)}개 주제 수집")
        except Exception as e:
            logging.error(f"MBC 수집 실패: {e}")
        return topics

    def extract_health_keywords(self, topics: list) -> list:
        """방송 주제 텍스트 목록에서 사전에 정의된 핵심 건강식품/기기 키워드를 추출"""
        extracted = []
        for topic in topics:
            for keyword in self.health_keywords:
                if keyword in topic and keyword not in extracted:
                    extracted.append(keyword)
        return extracted

    def get_morning_show_keyword(self) -> str:
        """KBS/MBC 아침 방송 정보를 분석하여 오늘자 건강 타겟 키워드 1개 최종 추출"""
        kbs_topics = self.fetch_kbs_health_topics()
        mbc_topics = self.fetch_mbc_health_topics()
        
        all_topics = kbs_topics + mbc_topics
        extracted_keywords = self.extract_health_keywords(all_topics)
        
        # 만약 실제 방송 홈페이지 크롤링에서 매칭된 건강 키워드가 있다면 우선 선정
        if extracted_keywords:
            selected = random.choice(extracted_keywords)
            logging.info(f"방송 정보 크롤링 매칭 성공: {selected} (총 {len(extracted_keywords)}개 후보 중 선정)")
            return selected
            
        # 크롤링 차단 혹은 오늘 방송 주제가 새로운 경우, 건강 사전에서 무작위 선택하여 배포 흐름 보장 (Fallback)
        selected = random.choice(self.health_keywords)
        logging.info(f"방송 정보 매칭 실패로 건강 사전에서 키워드를 선정했습니다: {selected}")
        return selected

    def fetch_google_trends(self) -> list:
        """구글 일일 트렌드 RSS를 파싱하여 실시간 인기 검색어 목록을 반환"""
        url = "https://trends.google.co.kr/trends/trendingsearches/daily/rss?geo=KR"
        keywords = []
        try:
            logging.info("구글 트렌드 RSS 수집 시작...")
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                for item in root.findall(".//item"):
                    title = item.find("title")
                    if title is not None and title.text:
                        keywords.append(title.text.strip())
            logging.info(f"구글 트렌드 수집 완료: {len(keywords)}개 키워드")
        except Exception as e:
            logging.error(f"구글 트렌드 수집 중 오류 발생: {e}")
        return keywords

    def get_target_keyword(self) -> str:
        """아침 건강 방송 연동 전략에 기반한 최종 키워드 탐색"""
        # 기본적으로 건강 방송 연동 키워드를 타겟팅
        return self.get_morning_show_keyword()

if __name__ == "__main__":
    analyzer = KeywordAnalyzer()
    print("오늘의 아침 방송 건강 타겟 키워드:", analyzer.get_target_keyword())
