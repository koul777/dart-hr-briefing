from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parent
DOCUMENTS = (
    ROOT / "README.md",
    ROOT / "CLAUDE.md",
    ROOT / "OpenDART_HR_Analytics_4시간_커리큘럼.md",
    ROOT / "docs" / "PARTICIPANT_PREFLIGHT.md",
    ROOT / "docs" / "INSTRUCTOR_RUNBOOK.md",
    ROOT / "docs" / "COURSE_REHEARSAL_CHECKLIST.md",
    ROOT / "docs" / "PPT_ALIGNMENT_PLAN.md",
    ROOT / "docs" / "PRODUCTION_RELEASE_CHECKLIST.md",
    ROOT / "docs" / "OVERNIGHT_6H_EXECUTION_PLAN.md",
)
MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HTML_LINK_PATTERN = re.compile(
    r"\b(?:href|src)=[\"']([^\"']+)[\"']",
    flags=re.IGNORECASE,
)
EXTERNAL_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "data:",
    "javascript:",
)


def _local_targets(document: Path) -> list[tuple[str, int]]:
    targets: list[tuple[str, int]] = []
    for line_number, line in enumerate(
        document.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        raw_targets = [
            *MARKDOWN_LINK_PATTERN.findall(line),
            *HTML_LINK_PATTERN.findall(line),
        ]
        for raw_target in raw_targets:
            target = raw_target.strip().strip("<>")
            if not target or target.startswith("#"):
                continue
            if target.casefold().startswith(EXTERNAL_PREFIXES):
                continue
            # Markdown may append a quoted title after the path.
            target = re.sub(r"\s+[\"'].*[\"']\s*$", "", target).strip()
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if target:
                targets.append((target, line_number))
    return targets


class DocumentationContractTests(unittest.TestCase):
    def test_core_course_documents_exist_and_have_no_broken_local_links(self) -> None:
        missing_documents = [
            path.relative_to(ROOT).as_posix()
            for path in DOCUMENTS
            if not path.is_file()
        ]
        self.assertEqual(missing_documents, [])

        broken: list[str] = []
        for document in DOCUMENTS:
            for raw_target, line_number in _local_targets(document):
                resolved = (document.parent / raw_target).resolve()
                try:
                    resolved.relative_to(ROOT)
                except ValueError:
                    broken.append(
                        f"{document.relative_to(ROOT).as_posix()}:{line_number} "
                        f"escapes workspace: {raw_target}"
                    )
                    continue
                if not resolved.exists():
                    broken.append(
                        f"{document.relative_to(ROOT).as_posix()}:{line_number} "
                        f"missing: {raw_target}"
                    )

        self.assertEqual(broken, [])


if __name__ == "__main__":
    unittest.main()
