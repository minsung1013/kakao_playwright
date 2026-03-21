"""
OpenAI gpt-4o-mini로 소식 제목 및 피드 메시지 생성
"""
from openai import OpenAI
from src.config import OPENAI_API_KEY

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def generate_title(english_text: str) -> str:
    """소식 제목 생성 (이모지 1개 포함, 20~40자)"""
    prompt = f"""당신은 화장품/퍼스널케어 마케팅 전문가입니다.
아래 Instagram 게시물을 바탕으로 카카오 채널 소식의 제목을 작성하세요.

요구사항:
- 20~40자 사이로 작성
- 이모지 1개를 앞에 배치
- 클릭을 유도하는 매력적인 제목

원문:
{english_text[:500]}

제목만 출력하세요:"""

    response = get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def translate_to_korean(english_text: str) -> str:
    """영문 텍스트를 한국어로 번역"""
    prompt = f"""아래 영문 텍스트를 자연스러운 한국어로 번역하세요.
마케팅/화장품 분야 용어는 전문적으로 번역하고, 번역문만 출력하세요.

원문:
{english_text[:1000]}"""

    response = get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.3,
    )
    return response.choices[0].message.content.strip()


def generate_message(english_text: str) -> str:
    """피드 메시지 생성 (이모티콘 2~3개, 200~400자, ~요 체)"""
    prompt = f"""당신은 화장품/퍼스널케어 마케팅 전문가입니다.
아래 Instagram 게시물을 바탕으로 카카오 채널 메시지를 작성하세요.

요구사항:
- 200~400자 사이로 작성
- 이모티콘 2~3개 배치
- ~요 체로 친근하게 작성

원문:
{english_text[:800]}

메시지만 출력하세요:"""

    response = get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()
