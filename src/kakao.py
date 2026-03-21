"""
Kakao Business 업로드 (Playwright)
- pyautogui, pyperclip 완전 제거
- 텍스트: fill()
- 파일: set_input_files() → expect_file_chooser() 폴백
"""
import os
import re
from playwright.sync_api import sync_playwright, Page

from src.config import (
    KAKAO_STATE, KAKAO_USERNAME, KAKAO_PASSWORD,
    KAKAO_POST_URL, KAKAO_MSG_URL, DEBUG_DIR,
)


# ── 헬퍼 ──────────────────────────────────────────────────────────

def _save_debug(page: Page, name: str) -> None:
    path = os.path.join(DEBUG_DIR, f"{name}.png")
    try:
        page.screenshot(path=path)
        print(f"   📷 스크린샷: {path}")
    except Exception:
        pass


def _make_context(playwright, headless: bool = True):
    browser = playwright.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        storage_state=KAKAO_STATE if os.path.exists(KAKAO_STATE) else None,
    )
    return browser, context


def _ensure_logged_in(page: Page) -> None:
    """로그인 상태 확인, 필요 시 자동 로그인 시도"""
    page.goto(KAKAO_POST_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    current = page.url
    _save_debug(page, "kakao_session_check")
    print(f"   세션 확인 URL: {current}")
    if "login" not in current and "accounts.kakao" not in current:
        print("   ✅ 카카오 세션 유효")
        return

    print("   🔐 카카오 로그인 필요...")
    if not KAKAO_USERNAME or not KAKAO_PASSWORD:
        raise RuntimeError("KAKAO_USERNAME / KAKAO_PASSWORD 환경변수 없음")

    try:
        page.locator('input[name="loginId"]').fill(KAKAO_USERNAME, timeout=10000)
        page.locator('input[name="password"]').fill(KAKAO_PASSWORD)
        page.keyboard.press("Enter")
        page.wait_for_timeout(8000)

        # 재확인
        page.goto(KAKAO_POST_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        if "login" in page.url or "accounts.kakao" in page.url:
            _save_debug(page, "kakao_login_failed")
            raise RuntimeError("카카오 로그인 실패 (2FA/CAPTCHA 가능성). 세션을 갱신하세요.")
        print("   ✅ 카카오 로그인 성공")

    except RuntimeError:
        raise
    except Exception as e:
        _save_debug(page, "kakao_login_error")
        raise RuntimeError(f"카카오 로그인 오류: {e}") from e


def _upload_file(page: Page, locator_css: str, img_path: str) -> bool:
    """
    파일 업로드 시도
    방법 1: set_input_files (hidden/disabled 요소에도 동작)
    방법 2: expect_file_chooser (파일 다이얼로그 가로채기)
    """
    if not img_path or not os.path.exists(img_path):
        print(f"   ⚠️ 이미지 없음: {img_path}")
        return False

    # 방법 1
    try:
        file_input = page.locator(locator_css).first
        file_input.wait_for(state="attached", timeout=5000)
        # disabled 제거
        page.evaluate(
            "el => { el.removeAttribute('disabled'); el.style.display = 'block'; }",
            file_input.element_handle(),
        )
        file_input.set_input_files(img_path)
        print(f"   ✅ 파일 업로드 (set_input_files)")
        return True
    except Exception:
        pass

    # 방법 2
    try:
        upload_btns = [
            'button:has-text("첨부")',
            'div[class*="upload"]',
            'label[class*="upload"]',
        ]
        for btn_sel in upload_btns:
            try:
                with page.expect_file_chooser(timeout=5000) as fc_info:
                    page.locator(btn_sel).first.click()
                fc_info.value.set_files(img_path)
                print(f"   ✅ 파일 업로드 (file_chooser)")
                return True
            except Exception:
                continue
    except Exception:
        pass

    print("   ⚠️ 파일 업로드 실패")
    _save_debug(page, "upload_failed")
    return False


def _clean_text(text: str) -> str:
    """게시물 본문 정제 (타임스탬프, 버튼 텍스트 제거)"""
    lines = text.split("\n")
    if lines and lines[0].strip() == "evonikpc":
        lines = lines[1:]

    result = []
    for line in lines:
        if "원문 보기" in line or "번역 보기" in line:
            break
        result.append(line)

    while result and (
        not result[-1].strip()
        or re.search(r"\d+[주일시간분]$", result[-1].strip())
    ):
        result.pop()

    return "\n".join(result).strip()


# ── 소식 업로드 ────────────────────────────────────────────────────

def upload_post(page: Page, title: str, body: str, img_path: str) -> None:
    """소식(Posts) 임시저장"""
    page.goto(KAKAO_POST_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(5000)
    _save_debug(page, "post_page_loaded")
    print(f"   현재 URL: {page.url}")

    # "새 소식" 또는 "글쓰기" 버튼 클릭 시도 (목록 페이지인 경우)
    for btn_text in ["새 소식", "글쓰기", "새글 작성", "작성하기"]:
        try:
            btn = page.locator(f'a:has-text("{btn_text}"), button:has-text("{btn_text}")').first
            if btn.is_visible(timeout=2000):
                btn.click()
                page.wait_for_timeout(2000)
                _save_debug(page, "post_after_new_btn")
                print(f"   ✅ '{btn_text}' 버튼 클릭")
                break
        except Exception:
            continue

    # 제목 입력 (여러 셀렉터 시도)
    title_input = None
    for sel in ["input.tf_g", "input[placeholder*='제목']", "input[type='text']"]:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=5000)
            title_input = el
            print(f"   ✅ 제목 입력창 발견: {sel}")
            break
        except Exception:
            continue

    if title_input is None:
        _save_debug(page, "post_no_title_input")
        print("   ⚠️ 제목 입력창을 찾을 수 없음 - 스크린샷 확인 필요")
        return

    title_input.fill(title[:40])
    page.wait_for_timeout(500)

    # 본문 입력
    body_area = None
    for sel in ["textarea.textbox___1Ig6T", "textarea[placeholder*='내용']", "textarea"]:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=5000)
            body_area = el
            print(f"   ✅ 본문 입력창 발견: {sel}")
            break
        except Exception:
            continue

    if body_area is None:
        _save_debug(page, "post_no_body_input")
        print("   ⚠️ 본문 입력창을 찾을 수 없음")
        return

    body_area.fill(body)
    page.wait_for_timeout(500)

    # 이미지
    _upload_file(page, 'input[type="file"]', img_path)
    page.wait_for_timeout(3000)

    # 임시저장 → 등록 → 확인
    try:
        page.locator('label:has-text("임시저장")').first.click(timeout=10000)
        page.locator('button:has-text("등록")').first.click(timeout=10000)
        page.locator('button:has-text("확인")').first.click(timeout=10000)
        page.wait_for_timeout(2000)
    except Exception as e:
        _save_debug(page, "post_save_failed")
        print(f"   ⚠️ 소식 임시저장 실패: {e}")


# ── 메시지 업로드 ──────────────────────────────────────────────────

def upload_message(page: Page, message: str, img_path: str) -> None:
    """피드 메시지 임시저장"""
    page.goto(KAKAO_MSG_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    # 이미지 업로드 라디오 선택
    image_selected = False
    # 방법 1: 라디오 버튼 JS 클릭
    try:
        radio = page.locator('input[value="image"], input[id*="media.type"]').first
        page.evaluate("""el => {
            el.checked = true;
            el.dispatchEvent(new Event('change', {bubbles: true}));
            el.dispatchEvent(new Event('click', {bubbles: true}));
        }""", radio.element_handle())
        image_selected = True
        print("   ✅ 이미지 타입 선택 (라디오 JS)")
    except Exception:
        pass

    # 방법 2: 라벨 클릭
    if not image_selected:
        try:
            page.locator('label:has-text("이미지 업로드"), label[for*="media.type"]').first.click(timeout=3000)
            image_selected = True
            print("   ✅ 이미지 타입 선택 (라벨)")
        except Exception:
            print("   ⚠️ 이미지 타입 선택 실패")

    page.wait_for_timeout(2000)

    # 이미지 업로드
    # 방법 1: disabled 아닌 file input에 직접 주입 (원본 kakao_agent.py 방식)
    uploaded = False
    for sel in ['input.custom.uploadInput', 'input.uploadInput', 'input[type="file"][accept*="image"]', 'input[type="file"]']:
        try:
            file_input = page.locator(sel).first
            file_input.wait_for(state="attached", timeout=3000)
            is_disabled = page.evaluate("el => el.disabled", file_input.element_handle())
            if not is_disabled:
                file_input.set_input_files(img_path)
                print(f"   ✅ 파일 업로드 완료 (set_input_files: {sel})")
                uploaded = True
                break
        except Exception:
            continue

    # 방법 2: "첨부" 버튼 클릭 → expect_file_chooser로 가로채기 (원본의 pyautogui 대체)
    if not uploaded:
        try:
            attach_btn = page.locator('button:has-text("첨부")').first
            attach_btn.wait_for(state="visible", timeout=5000)
            with page.expect_file_chooser(timeout=5000) as fc_info:
                attach_btn.click()
            fc_info.value.set_files(img_path)
            print("   ✅ 파일 업로드 완료 (첨부 버튼 → file_chooser)")
            uploaded = True
        except Exception:
            pass

    if not uploaded:
        _save_debug(page, "upload_failed")
        print("   ⚠️ 파일 업로드 실패")

    page.wait_for_timeout(3000)

    # 메시지 입력 (textarea 우선순위 순)
    textarea_selectors = [
        "#messageWrite",
        'textarea[name*="message"]',
        "textarea.textarea",
        "textarea",
    ]
    textarea = None
    for sel in textarea_selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=5000)
            textarea = el
            break
        except Exception:
            continue

    if textarea is None:
        _save_debug(page, "msg_no_textarea")
        print("   ⚠️ 메시지 입력창 없음")
        return

    # fill()로 직접 입력 (클립보드 불필요)
    textarea.click()
    textarea.fill(message)
    page.wait_for_timeout(1000)

    # 입력 검증
    entered = textarea.input_value() or ""
    if len(entered) < 10:
        # JS 폴백
        page.evaluate(
            "([el, val]) => { el.value = val; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }",
            [textarea.element_handle(), message],
        )
        page.wait_for_timeout(500)
        entered = textarea.input_value() or ""

    print(f"   ✅ 메시지 입력 완료 ({len(entered)}자)")

    # 임시저장 → 확인
    try:
        page.locator('button:has-text("임시저장")').first.click(timeout=10000)
        page.locator('button:has-text("확인")').first.click(timeout=10000)
        page.wait_for_timeout(2000)
    except Exception as e:
        _save_debug(page, "msg_save_failed")
        print(f"   ⚠️ 메시지 임시저장 실패: {e}")


# ── 메인 함수 ──────────────────────────────────────────────────────

def upload_all(
    titles: list[str],
    bodies: list[str],
    messages: list[str],
    img_paths: list[str],
) -> None:
    """소식 전체 + 메시지 전체 업로드"""
    count = len(titles)

    with sync_playwright() as p:
        browser, context = _make_context(p, headless=True)
        page = context.new_page()

        _ensure_logged_in(page)

        # 소식 업로드
        print(f"\n{'='*55}")
        print("📰 소식 업로드")
        print(f"{'='*55}")
        for i in range(count):
            body = _clean_text(bodies[i])
            print(f"\n   소식 {i+1}/{count}: {titles[i][:40]}")
            upload_post(page, titles[i], body, img_paths[i])
            print(f"   ✅ 임시저장 완료")

        # 메시지 업로드
        print(f"\n{'='*55}")
        print("💬 피드 메시지 업로드")
        print(f"{'='*55}")
        for i in range(count):
            print(f"\n   메시지 {i+1}/{count}")
            upload_message(page, messages[i], img_paths[i])
            print(f"   ✅ 임시저장 완료")

        browser.close()
