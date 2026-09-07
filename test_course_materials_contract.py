from __future__ import annotations

import ast
import hashlib
import json
import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
COURSE_DOCUMENTS = (
    Path("README.md"),
    Path("docs/PARTICIPANT_PREFLIGHT.md"),
    Path("docs/INSTRUCTOR_RUNBOOK.md"),
    Path("docs/COURSE_REHEARSAL_CHECKLIST.md"),
    Path("docs/PPT_ALIGNMENT_PLAN.md"),
)
DELIVERY_CONTRACT_DOCUMENTS = COURSE_DOCUMENTS
PPT_PLAN = ROOT / "docs/PPT_ALIGNMENT_PLAN.md"
WEEK_SEQUENCE_DOCUMENTS = (
    Path("docs/PPT_ALIGNMENT_PLAN.md"),
    Path("docs/INSTRUCTOR_RUNBOOK.md"),
    Path("OpenDART_HR_Analytics_4시간_커리큘럼.md"),
)
FINAL_OUTLINE = Path("training_deck/final_60/outline.md")
FINAL_SPEECH = Path("training_deck/final_60/speech.md")
FINAL_DECK_SPEC = Path("training_deck/final_60/deck_spec.json")
LOCAL_FINAL_DECK_AVAILABLE = all(
    (ROOT / path).is_file()
    for path in (FINAL_OUTLINE, FINAL_SPEECH, FINAL_DECK_SPEC)
)
SPEAKER_NOTE_FIELDS = (
    "[권장 시간]",
    "[강사 조작]",
    "[수강생 행동]",
    "[기대 결과]",
    "[통과 기준]",
    "[실패 복구]",
    "[체크포인트]",
    "[Sources]",
)
AI_POLICY_REASON_CODES = (
    "uncited_factual_claim",
    "unsupported_causal_assertion",
    "automated_hr_action_recommendation",
    "protected_characteristic_judgment",
)

MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HTML_LINK_RE = re.compile(r"(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s<>)\]`\"']+")
BACKTICK_PNG_RE = re.compile(r"`([^`]+\.png)`")
MARKED_UNCAPTURED_PNG_RE = re.compile(r"`([^`]+\.png)`\(미촬영\)")
MARKED_CAPTURED_PNG_RE = re.compile(r"`([^`]+\.png)`\(촬영 완료\)")

EXPECTED_BODY_SOURCES = (
    "1",
    "2",
    "3",
    "4",
    "5",
    "7",
    "9",
    "10",
    "11",
    "13",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "25",
    "26",
    "28",
    "29",
    "30",
    "31",
    "33",
    "35",
    "36",
    "37",
    "38",
    "42",
    "43",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "50",
    "53",
    "54",
    "55",
    "56",
)
EXPECTED_APPENDIX_SOURCES = (
    "6",
    "8",
    "12",
    "14",
    "23",
    "24",
    "27",
    "32",
    "34",
    "39",
    "40",
    "41",
    "51",
    "52",
    "신규",
    "신규",
    "신규",
    "신규",
)

STANDARD_CAPTURE_ASSETS = frozenset(
    {
        "docs/assets/classroom-sample-entry.png",
        "docs/assets/classroom-sample-ui.png",
        "docs/assets/classroom-sample-strategy.png",
        "docs/assets/classroom-sample-mobile-controls.png",
        "docs/assets/ai-live-consent-disconnect.png",
    }
)
NON_PREFERRED_DUPLICATE_ASSETS = {
    "docs/assets/classroom-sample-header.png": "docs/assets/classroom-sample-ui.png",
    "docs/assets/classroom-sample-mobile.png": (
        "docs/assets/classroom-sample-mobile-controls.png"
    ),
}
ALLOWED_UNCAPTURED_PPT_ASSETS = frozenset()
CAPTURED_GOLDEN_PATH_ASSETS = frozenset(
    {
        "training_deck/assets/screenshots/classroom-preflight-pass.png",
        "training_deck/assets/screenshots/terminal-start-8765-health.png",
        "training_deck/assets/screenshots/classroom-bootstrap.png",
    }
)
CAPTURED_RECOVERY_ASSETS = frozenset(
    {
        "training_deck/assets/screenshots/comparison-timeout.png",
        "training_deck/assets/screenshots/request-id-error.png",
        "training_deck/assets/screenshots/selection-aborted.png",
    }
)
CAPTURED_POLICY_ASSETS = frozenset(
    {"training_deck/assets/screenshots/ai-policy-fallback.png"}
)
KNOWN_DEPLOYMENT_ORIGINS = frozenset({"https://dart-ruby-zeta.vercel.app"})


def _read(relative_path: Path | str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _normalize_command_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\\", "/")).strip()


def _markdown_target_path(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    if not target or target.startswith(("#", "//")):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    path = unquote(parsed.path)
    return path or None


def _relative_link_targets(text: str) -> set[str]:
    raw_targets = {
        match.group(1) for match in MARKDOWN_LINK_RE.finditer(text)
    } | {match.group(1) for match in HTML_LINK_RE.finditer(text)}
    return {
        path
        for target in raw_targets
        if (path := _markdown_target_path(target)) is not None
    }


def _assigned_constant(source: str, name: str) -> object:
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        value = node.value
        if not isinstance(value, ast.Constant):
            raise AssertionError(f"{name} must remain a literal constant")
        return value.value
    raise AssertionError(f"missing constant: {name}")


def _section(text: str, start_heading: str, end_heading: str) -> str:
    start = text.rfind(start_heading)
    if start < 0:
        raise AssertionError(f"missing section heading: {start_heading}")
    end = text.find(end_heading, start + len(start_heading))
    if end < 0:
        raise AssertionError(f"missing section boundary: {end_heading}")
    return text[start:end]


def _matrix_rows(section: str, prefix: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        if not re.match(rf"^\| {prefix}\d{{2}} \|", line):
            continue
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def _sha256(relative_path: str) -> str:
    return hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()


class CourseMaterialLinkContractTests(unittest.TestCase):
    def test_all_course_document_relative_links_resolve_inside_workspace(self) -> None:
        for relative_document in COURSE_DOCUMENTS:
            document = ROOT / relative_document
            self.assertTrue(document.is_file(), relative_document.as_posix())
            for target in sorted(_relative_link_targets(document.read_text(encoding="utf-8"))):
                with self.subTest(document=relative_document.as_posix(), target=target):
                    resolved = (document.parent / target).resolve()
                    self.assertTrue(resolved.is_relative_to(ROOT))
                    self.assertTrue(resolved.exists(), str(resolved))

    def test_urls_use_verified_origins_and_no_placeholder_deployment_url(self) -> None:
        forbidden_fragments = (
            "example.com",
            "example.invalid",
            "your-project",
            "your-app",
            "project-name.vercel.app",
        )
        for relative_document in COURSE_DOCUMENTS:
            text = _read(relative_document)
            lowered = text.lower()
            for fragment in forbidden_fragments:
                with self.subTest(document=relative_document.as_posix(), fragment=fragment):
                    self.assertNotIn(fragment, lowered)
            for raw_url in URL_RE.findall(text):
                parsed = urlsplit(raw_url.rstrip(".,;"))
                with self.subTest(document=relative_document.as_posix(), url=raw_url):
                    if parsed.hostname and parsed.hostname.endswith(".vercel.app"):
                        origin = f"{parsed.scheme}://{parsed.netloc}"
                        self.assertIn(origin, KNOWN_DEPLOYMENT_ORIGINS)
                    if parsed.hostname == "127.0.0.1" and parsed.port == 8000:
                        self.assertEqual(relative_document, Path("README.md"))
                        self.assertEqual(parsed.path, "/demo.html")
                    elif parsed.hostname == "127.0.0.1":
                        self.assertEqual(parsed.port, 8765)


class CourseCommandContractTests(unittest.TestCase):
    def test_preflight_health_bootstrap_and_secret_scan_commands_match_code(self) -> None:
        server_source = _read("server.py")
        preflight_source = _read("tools/classroom_preflight.py")
        secret_scan_source = _read("tools/release_secret_scan.py")
        self.assertEqual(_assigned_constant(server_source, "DEFAULT_PORT"), 8765)
        self.assertEqual(_assigned_constant(preflight_source, "DEFAULT_PORT"), 8765)
        self.assertEqual(
            _assigned_constant(server_source, "APP_ID"),
            "kr.opendart.dart-hr-briefing",
        )
        self.assertEqual(
            _assigned_constant(preflight_source, "EXPECTED_APP_ID"),
            "kr.opendart.dart-hr-briefing",
        )
        self.assertIn('parsed.path == "/api/health"', server_source)
        self.assertIn('parsed.path == "/api/classroom/bootstrap"', server_source)
        self.assertIn('parser.add_argument("--root"', secret_scan_source)

        combined = _normalize_command_text(
            "\n".join(_read(document) for document in COURSE_DOCUMENTS)
        )
        self.assertIn("tools/classroom_preflight.py", combined)
        self.assertIn("http://127.0.0.1:8765/api/health", combined)
        self.assertIn("http://127.0.0.1:8765/api/classroom/bootstrap", combined)
        self.assertIn("python -X utf8 tools/release_secret_scan.py --root .", combined)
        self.assertTrue((ROOT / "tools/classroom_preflight.py").is_file())
        self.assertTrue((ROOT / "tools/release_secret_scan.py").is_file())

    def test_each_operational_document_keeps_its_required_command_contract(self) -> None:
        requirements = {
            "README.md": (
                "/api/health",
                "/api/classroom/bootstrap",
                "tools/release_secret_scan.py --root .",
            ),
            "docs/PARTICIPANT_PREFLIGHT.md": (
                "tools/classroom_preflight.py",
                "http://127.0.0.1:8765/api/health",
                "http://127.0.0.1:8765/api/classroom/bootstrap",
            ),
            "docs/INSTRUCTOR_RUNBOOK.md": (
                "tools/classroom_preflight.py",
                "/api/health",
                "/api/classroom/bootstrap",
            ),
            "docs/COURSE_REHEARSAL_CHECKLIST.md": (
                "tools/classroom_preflight.py",
                "http://127.0.0.1:8765/api/health",
                "/api/classroom/bootstrap",
            ),
            "docs/PPT_ALIGNMENT_PLAN.md": (
                "tools/classroom_preflight.py",
                "127.0.0.1:8765",
                "/api/classroom/bootstrap",
            ),
        }
        for relative_document, fragments in requirements.items():
            text = _normalize_command_text(_read(relative_document))
            for fragment in fragments:
                with self.subTest(document=relative_document, fragment=fragment):
                    self.assertIn(fragment, text)

    def test_shared_classroom_operations_wording_is_unambiguous(self) -> None:
        canonical_preflight = "py -3.12 -X utf8 tools/classroom_preflight.py"
        documents = (
            Path("docs/PARTICIPANT_PREFLIGHT.md"),
            Path("docs/INSTRUCTOR_RUNBOOK.md"),
            Path("docs/COURSE_REHEARSAL_CHECKLIST.md"),
            Path("docs/PPT_ALIGNMENT_PLAN.md"),
            Path("OpenDART_HR_Analytics_4시간_커리큘럼.md"),
        ) + ((FINAL_OUTLINE, FINAL_SPEECH) if LOCAL_FINAL_DECK_AVAILABLE else ())
        for document in documents:
            with self.subTest(document=document.as_posix(), contract="preflight"):
                self.assertIn(canonical_preflight, _normalize_command_text(_read(document)))

        threshold_documents = (
            Path("docs/INSTRUCTOR_RUNBOOK.md"),
            Path("docs/COURSE_REHEARSAL_CHECKLIST.md"),
            Path("docs/PPT_ALIGNMENT_PLAN.md"),
            Path("OpenDART_HR_Analytics_4시간_커리큘럼.md"),
        ) + ((FINAL_OUTLINE, FINAL_SPEECH) if LOCAL_FINAL_DECK_AVAILABLE else ())
        for document in threshold_documents:
            text = _read(document)
            with self.subTest(document=document.as_posix(), contract="80-percent"):
                self.assertIn("정시 통과율이 80% 미만", text)
                if document != Path("docs/PPT_ALIGNMENT_PLAN.md"):
                    self.assertNotIn("반의 80%가 막히면", text)

        retry_documents = (
            Path("docs/INSTRUCTOR_RUNBOOK.md"),
            Path("docs/COURSE_REHEARSAL_CHECKLIST.md"),
            Path("docs/PPT_ALIGNMENT_PLAN.md"),
            Path("OpenDART_HR_Analytics_4시간_커리큘럼.md"),
        ) + ((FINAL_OUTLINE, FINAL_SPEECH) if LOCAL_FINAL_DECK_AVAILABLE else ())
        for document in retry_documents:
            with self.subTest(document=document.as_posix(), contract="retry"):
                text = _read(document)
                self.assertIn("최초 요청 포함 최대 3회", text)
                self.assertIn("재시도 최대 2회", text)

    def test_final_sixty_delivery_and_human_ai_boundaries_are_consistent(self) -> None:
        shared_fragments = (
            "본문 42장",
            "부록 18장",
            "총 60장",
            "정시 통과율이 80% 미만",
            "최초 요청 포함 최대 3회",
            "재시도 최대 2회",
            "사람의 역할",
            "AI의 역할",
            "최종 판단 책임",
            "개인 평가",
            "자동 인사조치",
            "합성 샘플로 시작",
            "실데이터 화면으로 돌아가기",
            "전송 동의",
            "AI 키·대화 연결 해제",
        )
        for document in DELIVERY_CONTRACT_DOCUMENTS:
            text = _normalize_command_text(_read(document))
            for fragment in shared_fragments:
                with self.subTest(document=document.as_posix(), fragment=fragment):
                    self.assertIn(fragment, text)

        readme = _read("README.md")
        self.assertNotIn("56장", readme)
        self.assertNotIn("training_deck/training_deck.pptx", readme)

        plan = _normalize_command_text(_read(PPT_PLAN))
        self.assertIn("레거시 56장 참고본", plan)
        self.assertIn("최종 60장 실습 PPT로 안내하지 않음", plan)

    def test_all_documented_policy_reason_codes_match_the_product_contract(self) -> None:
        policy_documents = (
            Path("docs/PARTICIPANT_PREFLIGHT.md"),
            Path("docs/INSTRUCTOR_RUNBOOK.md"),
            Path("docs/COURSE_REHEARSAL_CHECKLIST.md"),
            Path("docs/PPT_ALIGNMENT_PLAN.md"),
        ) + ((FINAL_OUTLINE, FINAL_SPEECH) if LOCAL_FINAL_DECK_AVAILABLE else ())
        for document in policy_documents:
            text = _read(document)
            for reason_code in AI_POLICY_REASON_CODES:
                with self.subTest(document=document.as_posix(), reason_code=reason_code):
                    self.assertIn(reason_code, text)

    def test_week_sequence_ready_meaning_and_builder_handoff_are_explicit(self) -> None:
        required_fragments = (
            "`ready`",
            "성공확률",
            "인사조치 권고",
            "근거 이용 가능성",
            "결정 브리프",
            "`다음 내부 데이터`",
            "WEEK 3 데이터 빌더의 입력",
            "필드",
            "단위",
            "집계수준",
            "강사 수용 기준",
        )
        for document in WEEK_SEQUENCE_DOCUMENTS:
            text = _normalize_command_text(_read(document))
            with self.subTest(document=document.as_posix(), sequence="WEEK 1→2→3"):
                self.assertLess(text.index("WEEK 1 면접"), text.index("WEEK 2 DART"))
                self.assertLess(text.index("WEEK 2 DART"), text.index("WEEK 3 데이터"))
            for fragment in required_fragments:
                with self.subTest(document=document.as_posix(), fragment=fragment):
                    self.assertIn(fragment, text)


class PptCaptureMatrixContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = PPT_PLAN.read_text(encoding="utf-8")
        matrix = _section(
            self.plan,
            "## 최종 60장 자산·조작·통과 증거 대조표",
            "## 다시 촬영할 화면",
        )
        body = _section(matrix, "### 본문 42장", "### 부록 18장")
        appendix = _section(matrix, "### 부록 18장", "### 60장 대조 결론")
        self.body_rows = _matrix_rows(body, "B")
        self.appendix_rows = _matrix_rows(appendix, "A")
        self.matrix = matrix

    def test_matrix_has_all_60_rows_with_asset_action_and_pass_evidence(self) -> None:
        self.assertEqual(len(self.body_rows), 42)
        self.assertEqual(len(self.appendix_rows), 18)
        self.assertEqual(
            [row[0] for row in self.body_rows],
            [f"B{number:02d}" for number in range(1, 43)],
        )
        self.assertEqual(
            [row[0] for row in self.appendix_rows],
            [f"A{number:02d}" for number in range(1, 19)],
        )
        self.assertEqual([row[1] for row in self.body_rows], list(EXPECTED_BODY_SOURCES))
        self.assertEqual(
            [row[1] for row in self.appendix_rows],
            list(EXPECTED_APPENDIX_SOURCES),
        )

        for row in self.body_rows + self.appendix_rows:
            with self.subTest(slide=row[0]):
                self.assertEqual(len(row), 5)
                self.assertTrue(all(cell for cell in row))
                self.assertTrue(BACKTICK_PNG_RE.search(row[2]), "asset filename is missing")
                self.assertGreaterEqual(len(row[3]), 8, "instructor action is too vague")
                self.assertGreaterEqual(len(row[4]), 8, "learner evidence is too vague")

    def test_each_slide_has_an_existing_asset_and_only_allowlisted_missing_captures(self) -> None:
        if not LOCAL_FINAL_DECK_AVAILABLE:
            self.skipTest("training_deck is a local-only presentation artifact")
        observed_missing: set[str] = set()
        for row in self.body_rows + self.appendix_rows:
            assets = BACKTICK_PNG_RE.findall(row[2])
            existing = [asset for asset in assets if (ROOT / asset).is_file()]
            with self.subTest(slide=row[0]):
                self.assertTrue(existing, f"no existing asset or layout reference: {assets}")
            for asset in assets:
                if (ROOT / asset).is_file():
                    continue
                observed_missing.add(asset)
                with self.subTest(slide=row[0], missing=asset):
                    self.assertIn(asset, ALLOWED_UNCAPTURED_PPT_ASSETS)
                    self.assertIn(f"`{asset}`(미촬영)", row[2])

        self.assertEqual(observed_missing, set(ALLOWED_UNCAPTURED_PPT_ASSETS))
        gitignore = _read(".gitignore").splitlines()
        self.assertIn("training_deck/", {line.strip() for line in gitignore})
        self.assertTrue(
            all(path.startswith("training_deck/assets/screenshots/") for path in observed_missing)
        )

    def test_capture_status_markers_match_the_filesystem(self) -> None:
        if not LOCAL_FINAL_DECK_AVAILABLE:
            self.skipTest("training_deck is a local-only presentation artifact")
        marked_uncaptured = set(MARKED_UNCAPTURED_PNG_RE.findall(self.plan))
        marked_captured = set(MARKED_CAPTURED_PNG_RE.findall(self.plan))

        self.assertEqual(marked_uncaptured, set(ALLOWED_UNCAPTURED_PPT_ASSETS))
        self.assertTrue(CAPTURED_GOLDEN_PATH_ASSETS.issubset(marked_captured))
        self.assertTrue(CAPTURED_RECOVERY_ASSETS.issubset(marked_captured))
        self.assertTrue(CAPTURED_POLICY_ASSETS.issubset(marked_captured))
        self.assertTrue(marked_uncaptured.isdisjoint(marked_captured))

        for asset in marked_uncaptured:
            with self.subTest(uncaptured=asset):
                self.assertFalse((ROOT / asset).exists())
        for asset in marked_captured:
            with self.subTest(captured=asset):
                self.assertTrue((ROOT / asset).is_file())

        rehearsal = _read("docs/COURSE_REHEARSAL_CHECKLIST.md")
        for asset in CAPTURED_GOLDEN_PATH_ASSETS | CAPTURED_POLICY_ASSETS:
            asset_name = Path(asset).name
            rows = [
                line
                for line in rehearsal.splitlines()
                if f"`{asset_name}`" in line
            ]
            with self.subTest(rehearsal_capture=asset_name):
                self.assertEqual(len(rows), 1)
                self.assertTrue(rows[0].rstrip().endswith("| [x] |"))

        policy_contract_fragments = (
            "정책 차단 UI 계약 재현",
            "route mock",
            "외부 DART/provider 요청 0회",
            "QA 회사",
            "qa request ID",
            "실제 라이브 provider 응답",
        )
        for document in (
            Path("docs/PPT_ALIGNMENT_PLAN.md"),
            Path("docs/COURSE_REHEARSAL_CHECKLIST.md"),
        ):
            text = _read(document)
            for fragment in policy_contract_fragments:
                with self.subTest(policy_capture=document.as_posix(), fragment=fragment):
                    self.assertIn(fragment, text)

    def test_standard_and_duplicate_capture_statuses_are_consistent(self) -> None:
        for asset in STANDARD_CAPTURE_ASSETS:
            with self.subTest(standard=asset):
                self.assertTrue((ROOT / asset).is_file())
                self.assertIn(f"`{asset}`", self.plan)

        matrix_assets = {
            asset
            for row in self.body_rows + self.appendix_rows
            for asset in BACKTICK_PNG_RE.findall(row[2])
        }
        for duplicate, standard in NON_PREFERRED_DUPLICATE_ASSETS.items():
            with self.subTest(duplicate=duplicate, standard=standard):
                self.assertTrue((ROOT / duplicate).is_file())
                self.assertEqual(_sha256(duplicate), _sha256(standard))
                self.assertNotIn(duplicate, matrix_assets)
                duplicate_lines = [
                    line
                    for line in self.plan.splitlines()
                    if f"`{duplicate}`" in line
                ]
                self.assertTrue(duplicate_lines)
                self.assertTrue(any("비권장" in line for line in duplicate_lines))
                self.assertTrue(any("사용하지 않음" in line for line in duplicate_lines))

                duplicate_name = Path(duplicate).name
                for document in COURSE_DOCUMENTS:
                    if document == Path("docs/PPT_ALIGNMENT_PLAN.md"):
                        continue
                    with self.subTest(
                        duplicate=duplicate_name,
                        operational_document=document.as_posix(),
                    ):
                        self.assertNotIn(duplicate_name, _read(document))

        conclusion = _section(
            self.plan,
            "### 60장 대조 결론",
            "## 다시 촬영할 화면",
        )
        self.assertIn(
            f"현재 존재하지 않는 필수 캡처는 "
            f"{len(ALLOWED_UNCAPTURED_PPT_ASSETS)}개다",
            conclusion,
        )
        for asset in ALLOWED_UNCAPTURED_PPT_ASSETS:
            with self.subTest(conclusion=asset):
                self.assertIn(Path(asset).name, conclusion)
        captured_assets = (
            CAPTURED_GOLDEN_PATH_ASSETS
            | CAPTURED_RECOVERY_ASSETS
            | CAPTURED_POLICY_ASSETS
        )
        for asset in captured_assets:
            with self.subTest(not_missing_in_conclusion=asset):
                self.assertNotIn(Path(asset).name, conclusion)


@unittest.skipUnless(
    LOCAL_FINAL_DECK_AVAILABLE,
    "training_deck is a local-only presentation artifact",
)
class FinalSixtySlideTextContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.outline = _read(FINAL_OUTLINE)
        self.speech = _read(FINAL_SPEECH)
        self.spec = json.loads(_read(FINAL_DECK_SPEC))

    def test_outline_speech_and_spec_have_the_same_60_slide_titles(self) -> None:
        outline_titles = [
            match.group(2)
            for match in re.finditer(
                r"^## Slide (\d+): (.+?) \((?:본문|부록)\)$",
                self.outline,
                re.MULTILINE,
            )
        ]
        speech_titles = [
            match.group(2)
            for match in re.finditer(
                r"^## Slide (\d+): (.+)$",
                self.speech,
                re.MULTILINE,
            )
        ]
        spec_titles = [slide["title"] for slide in self.spec["slides"]]
        self.assertEqual(len(outline_titles), 60)
        self.assertEqual(outline_titles, speech_titles)
        self.assertEqual(outline_titles, spec_titles)

    def test_every_slide_has_executable_natural_korean_speaker_notes(self) -> None:
        for field in SPEAKER_NOTE_FIELDS:
            with self.subTest(field=field):
                self.assertEqual(self.speech.count(field), 60)
        forbidden_fragments = (
            "다입니다",
            "설명를",
            "기록를",
            "확인를",
            "적음를",
            "말함를",
            "표시를",
            "선택를",
            "작성를",
            "없음를",
            "재현를",
            "채점를",
            "이 증거를 확보한 뒤",
            "화면의 수치나 배지를 결론으로 먼저 읽지 말고",
        )
        for fragment in forbidden_fragments:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, self.speech)

    def test_speaker_note_sources_are_relative_and_exist(self) -> None:
        source_paths = re.findall(r"^- ([^\r\n]+)$", self.speech, re.MULTILINE)
        self.assertGreaterEqual(len(source_paths), 120)
        for source in source_paths:
            with self.subTest(source=source):
                self.assertFalse(Path(source).is_absolute())
                self.assertTrue((ROOT / source).is_file())

    def test_replacement_assets_and_regeneration_markers_are_explicit(self) -> None:
        self.assertNotIn("app-home.png", self.outline)
        self.assertNotIn("app-home.png", json.dumps(self.spec, ensure_ascii=False))
        self.assertIn("docs\\assets\\classroom-sample-entry.png", self.outline)
        required_image_paths = {
            image["path"]
            for slide in self.spec["slides"]
            for image in slide.get("required_images", [])
        }
        self.assertTrue(
            any(
                path.endswith("docs\\assets\\classroom-sample-entry.png")
                for path in required_image_paths
            )
        )
        plan = _read(PPT_PLAN)
        for marker in (
            "현재 raster의 “반의 80%가 막히면”",
            "고정 테스트 파일 수",
            "slide 13 재생성 필요",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, plan)


if __name__ == "__main__":
    unittest.main()
