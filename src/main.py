"""
에보닉 인스타→카카오 자동 포스팅 에이전트 (Playwright)
"""
import os
import shutil

from src.config import IMAGES_DIR, DRY_RUN
from src.state import load_texts, save_texts, filter_new
from src.instagram import scrape_posts
from src.openai_gen import generate_title, generate_message
from src.kakao import upload_all
from src.email_notify import send_notification_email


def main() -> None:
    print("=" * 60)
    print("🚀 에보닉 인스타→카카오 자동 포스팅 시작")
    if DRY_RUN:
        print("⚠️  DRY RUN 모드 (업로드/이메일 생략)")
    print("=" * 60)

    # ── 1. Instagram 수집 ────────────────────────────────────────
    print("\n📸 Instagram 수집 시작...")
    loaded_texts = load_texts()
    english_texts, korean_texts, img_paths = scrape_posts(loaded_texts)

    # 신규 게시물 필터링
    new_english, new_korean = filter_new(english_texts, korean_texts, loaded_texts)
    count = len(new_english)
    new_img_paths = img_paths[:count]

    print(f"\n{'='*60}")
    print(f"📊 수집 결과: 총 {len(english_texts)}개 / 신규 {count}개")
    print(f"{'='*60}")

    if count == 0:
        print("📭 새 게시물 없음, 종료")
        return

    # ── 2. OpenAI 콘텐츠 생성 ───────────────────────────────────
    print("\n🤖 OpenAI 콘텐츠 생성...")
    titles, messages = [], []

    for i, eng in enumerate(new_english):
        title = generate_title(eng)
        msg = generate_message(eng)
        titles.append(title)
        messages.append(msg)

        print(f"\n{'='*55}")
        print(f"✨ 게시물 {i+1}/{count} - LLM 생성 완료")
        print(f"   📌 제목 ({len(title)}자): {title}")
        print(f"   💬 메시지 ({len(msg)}자): {msg[:80]}...")
        print(f"{'='*55}")

    # ── 3. Kakao 업로드 ─────────────────────────────────────────
    if DRY_RUN:
        print("\n[DRY RUN] Kakao 업로드 생략")
        upload_ok = True
    else:
        print("\n📤 Kakao 업로드 시작...")
        upload_ok = upload_all(titles, new_korean, messages, new_img_paths)

    # texts.json은 업로드 성공 시에만 저장
    if upload_ok:
        save_texts(loaded_texts + new_english)
        print(f"✅ texts.json 업데이트 ({len(loaded_texts)} → {len(loaded_texts) + count}개)")
    else:
        print("⚠️ 업로드 실패 항목이 있어 texts.json 업데이트 생략")

    # ── 4. 정리 및 이메일 ────────────────────────────────────────
    shutil.rmtree(IMAGES_DIR, ignore_errors=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    posts_data = [
        {
            "english": new_english[i],
            "korean": new_korean[i],
            "title": titles[i],
            "message": messages[i],
        }
        for i in range(count)
    ]

    if DRY_RUN:
        print("\n[DRY RUN] 이메일 생략")
        for i, d in enumerate(posts_data):
            print(f"\n--- 게시물 {i+1} ---")
            print(f"제목: {d['title']}")
            print(f"메시지: {d['message'][:100]}...")
    else:
        send_notification_email(count, posts_data)

    print("\n" + "=" * 60)
    print(f"🎉 완료! 총 {count}개 게시물 임시저장")
    print("=" * 60)


if __name__ == "__main__":
    main()
