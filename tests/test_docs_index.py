"""docs-index.py의 심링크 경로와 문서 디렉터리 오버라이드 테스트."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "core/scripts/docs-index.py"


class TestDocsIndex(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        core_scripts = self.root / "core/scripts"
        core_scripts.mkdir(parents=True)
        # 킷 배치의 결정적 마커. 이게 없으면 구현이 'scripts/ 가 있으면 킷'이라는
        # 약한 추론에 기대게 된다 (Phase 12 리뷰 🔴 — 비킷 프로젝트 오판).
        (self.root / "core" / "install-manifest.tsv").write_text(
            "any\tfile\tcore/scripts/docs-index.py\t.local/bin/docs-index.py\n",
            encoding="utf-8")
        shutil.copy2(SOURCE, core_scripts / "docs-index.py")
        scripts = self.root / "scripts"
        scripts.mkdir()
        os.symlink("../core/scripts/docs-index.py", scripts / "docs-index.py")

    def write_phase_document(self, docs_dir):
        docs_dir.mkdir(parents=True)
        (docs_dir / "PHASE1_dummy.md").write_text(
            "---\nphase: 1\ndate: 2026-08-11\nkind: task\n"
            "summary: 더미 페이즈 문서\n---\n# 더미 페이즈 문서\n",
            encoding="utf-8",
        )

    def run_index(self, *args):
        return subprocess.run(
            [sys.executable, str(self.root / "scripts/docs-index.py"), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_symlink_execution_writes_index_in_repository_docs(self):
        docs_dir = self.root / "DOCs"
        self.write_phase_document(docs_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((docs_dir / "INDEX.md").is_file())

    def test_docs_dir_override_writes_index_in_specified_directory(self):
        docs_dir = self.root / "다른-문서"
        self.write_phase_document(docs_dir)

        result = self.run_index("--docs-dir", str(docs_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((docs_dir / "INDEX.md").is_file())

    # Phase 8 RED (오케스트레이터 작성·동결 — 위임 수정 금지)
    def test_docs_dir_prefers_docs_phases(self):
        docs_dir = self.root / "docs" / "phases"
        self.write_phase_document(docs_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((docs_dir / "INDEX.md").is_file())
        first_line = (docs_dir / "INDEX.md").read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("docs/phases", first_line)

    def test_docs_dir_prefers_docs_phases_over_DOCs(self):
        new_dir = self.root / "docs" / "phases"
        self.write_phase_document(new_dir)
        legacy_dir = self.root / "DOCs"
        self.write_phase_document(legacy_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((new_dir / "INDEX.md").is_file())
        self.assertFalse((legacy_dir / "INDEX.md").exists())

    def test_empty_docs_phases_falls_back_to_DOCs(self):
        # 전환기 상태: docs/phases는 존재하지만 비어있고 실문서는 DOCs에 있다
        (self.root / "docs" / "phases").mkdir(parents=True)
        legacy_dir = self.root / "DOCs"
        self.write_phase_document(legacy_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((legacy_dir / "INDEX.md").is_file())
        self.assertFalse((self.root / "docs" / "phases" / "INDEX.md").exists())

    def test_scaffolding_only_docs_phases_falls_back_to_DOCs(self):
        # docs/phases에 스캔 제외 대상(TEMPLATES·specs)만 있으면 실문서 없는 것으로 판정
        scaffold = self.root / "docs" / "phases"
        (scaffold / "TEMPLATES").mkdir(parents=True)
        (scaffold / "TEMPLATES" / "CURRENT_TASK_template.md").write_text("stub")
        (scaffold / "specs").mkdir()
        (scaffold / "specs" / "design.md").write_text("stub")
        legacy_dir = self.root / "DOCs"
        self.write_phase_document(legacy_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((legacy_dir / "INDEX.md").is_file())
        self.assertFalse((scaffold / "INDEX.md").exists())

    def test_reviews_only_docs_phases_preferred_over_DOCs(self):
        # reviews/ 하위 실문서만으로도 docs/phases가 선택된다 (phase-tools와 동일 판정 계약)
        reviews = self.root / "docs" / "phases" / "reviews"
        reviews.mkdir(parents=True)
        (reviews / "PHASE12_REVIEW.md").write_text(
            "---\nphase: 12\nkind: review\nstatus: done\nsummary: 리뷰\n---\n",
            encoding="utf-8",
        )
        legacy_dir = self.root / "DOCs"
        self.write_phase_document(legacy_dir)

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "docs" / "phases" / "INDEX.md").is_file())
        self.assertFalse((legacy_dir / "INDEX.md").exists())

    def test_missing_docs_dir_fails_clearly(self):
        result = self.run_index()

        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(result.stderr.strip(), "빈 stderr — 침묵 실패 금지")

    # Phase 14 RED (오케스트레이터 작성·동결 — 위임 수정 금지)
    # KF-1: 부트스트랩 산출물 DESIGN_*·PLAN_* 이 인덱스 스캔에서 통누락되던 실측 결함.
    def index_row_for(self, docs_dir, needle):
        text = (docs_dir / "INDEX.md").read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if needle in line]
        self.assertEqual(len(rows), 1, f"{needle} 행이 정확히 1개여야 한다:\n{text}")
        return rows[0]

    def test_design_doc_indexed_with_inferred_kind(self):
        # KF-1 실측 시나리오 그대로: frontmatter 없는 DESIGN_ 문서 단독
        docs_dir = self.root / "docs" / "phases"
        docs_dir.mkdir(parents=True)
        (docs_dir / "DESIGN_repo-bootstrap-20260901.md").write_text(
            "# 저장소 부트스트랩 설계\n", encoding="utf-8"
        )

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1개 문서", result.stdout, "0개 문서면 KF-1 재발")
        row = self.index_row_for(docs_dir, "DESIGN_repo-bootstrap-20260901.md")
        self.assertIn("| design |", row)

    def test_plan_doc_indexed_with_inferred_kind(self):
        docs_dir = self.root / "docs" / "phases"
        docs_dir.mkdir(parents=True)
        (docs_dir / "PLAN_roadmap.md").write_text("# 로드맵\n", encoding="utf-8")

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        row = self.index_row_for(docs_dir, "PLAN_roadmap.md")
        self.assertIn("| plan |", row)

    def test_frontmatter_kind_overrides_filename_inference(self):
        docs_dir = self.root / "docs" / "phases"
        docs_dir.mkdir(parents=True)
        (docs_dir / "DESIGN_x.md").write_text(
            "---\nkind: plan\ndate: 2026-09-01\nsummary: frontmatter 우선\n---\n",
            encoding="utf-8",
        )

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        row = self.index_row_for(docs_dir, "DESIGN_x.md")
        self.assertIn("| plan |", row)
        self.assertNotIn("| design |", row)

    # Phase 14 Task 1b RED (리뷰 🟠 대응: DESIGN/PLAN은 흔한 어간 — 구분자 없는 접두 검사는 오분류)
    def test_prefix_collision_not_indexed(self):
        docs_dir = self.root / "docs" / "phases"
        self.write_phase_document(docs_dir)
        (docs_dir / "PLANK_unrelated-initiative.md").write_text("# 무관\n", encoding="utf-8")
        (docs_dir / "DESIGNATED_owner-list.md").write_text("# 무관\n", encoding="utf-8")

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1개 문서", result.stdout, "충돌 파일명이 조용히 인덱싱되면 오분류")
        text = (docs_dir / "INDEX.md").read_text(encoding="utf-8")
        self.assertNotIn("PLANK_unrelated-initiative.md", text)
        self.assertNotIn("DESIGNATED_owner-list.md", text)

    def test_bare_and_delimited_design_plan_still_indexed(self):
        # 핀 고정: 구분자 강제가 정상 명명(bare·하이픈)까지 조이지 않아야 한다
        docs_dir = self.root / "docs" / "phases"
        docs_dir.mkdir(parents=True)
        (docs_dir / "DESIGN.md").write_text("# 설계\n", encoding="utf-8")
        (docs_dir / "PLAN-roadmap.md").write_text("# 로드맵\n", encoding="utf-8")

        result = self.run_index()

        self.assertEqual(result.returncode, 0, result.stderr)
        row = self.index_row_for(docs_dir, "DESIGN.md")
        self.assertIn("| design |", row)
        row = self.index_row_for(docs_dir, "PLAN-roadmap.md")
        self.assertIn("| plan |", row)

    def test_convention_docstring_matches_indexer(self):
        # KF-2: 규약 주석 ↔ 부트스트랩 실사용 종류 정합 셀프체크 (동결 형태)
        lines = SOURCE.read_text(encoding="utf-8").splitlines()
        kind_line = next(l for l in lines if l.strip().startswith("kind:"))
        for value in ("task", "review", "investigation", "design", "plan"):
            self.assertIn(value, kind_line)
        status_line = next(l for l in lines if l.strip().startswith("status:"))
        for value in ("done", "in-progress", "superseded", "decided", "draft"):
            self.assertIn(value, status_line)

    # Phase 12 RED (오케스트레이터 작성·동결 — 위임 수정 금지)
    def test_real_path_execution_finds_repository_docs(self):
        """`core/scripts/docs-index.py` 실경로로 불러도 저장소 문서를 찾아야 한다.

        `scripts/` 심링크 진입점만 상정한 '한 단계 위' 루트 계산은 실경로에서
        `core/` 를 루트로 착각한다 — 실측 출력:
        `문서 디렉터리를 찾을 수 없습니다: <root>/core/docs/phases`.
        """
        docs_dir = self.root / "docs" / "phases"
        self.write_phase_document(docs_dir)

        result = subprocess.run(
            [sys.executable, str(self.root / "core/scripts/docs-index.py")],
            capture_output=True, text=True, timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(
            (docs_dir / "INDEX.md").is_file(),
            "실경로 호출이 문서 디렉터리를 찾지 못했다:\n"
            f"{result.stdout}{result.stderr}",
        )

    def test_stamped_project_layout_still_finds_docs(self):
        """설치된 프로젝트 배치(`<proj>/scripts/` 실파일, `core/` 없음)를 깨지 말 것.

        `lib/stamp.sh:30` 이 `core/scripts/*` 를 `<proj>/scripts/*` **실파일**로
        복사하므로 그 배치의 루트는 스크립트 기준 **한 단계** 위다. 실경로 문제를
        '두 단계 위'로 일괄 고정하면 설치된 모든 프로젝트가 깨진다 — 회귀 가드.
        """
        with tempfile.TemporaryDirectory() as stamped:
            project = Path(stamped)
            scripts = project / "scripts"
            scripts.mkdir()
            shutil.copy2(SOURCE, scripts / "docs-index.py")
            docs_dir = project / "docs" / "phases"
            self.write_phase_document(docs_dir)

            result = subprocess.run(
                [sys.executable, str(scripts / "docs-index.py")],
                capture_output=True, text=True, timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(
                (docs_dir / "INDEX.md").is_file(),
                "설치된 프로젝트 배치에서 문서를 찾지 못했다:\n"
                f"{result.stdout}{result.stderr}",
            )

    # Phase 12 라운드 2 RED (오케스트레이터 작성·동결 — 위임 수정 금지)
    def test_sibling_scripts_dir_alone_is_not_a_kit_marker(self):
        """`scripts/` 가 있다는 이유만으로 부모를 킷 루트로 승격하면 안 된다.

        비킷 프로젝트가 우연히 `core/scripts/` 와 최상위 `scripts/` 를 함께 가지는 것은
        흔한 구조다. 킷 마커(`core/install-manifest.tsv`)가 없으면 승격하지 말아야 한다.
        승격해 버리면 실제 문서가 있는 `core/docs/phases` 를 통째로 건너뛴다.
        """
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "myproj"
            (proj / "core" / "scripts").mkdir(parents=True)
            (proj / "scripts").mkdir()          # 킷과 무관한 동명 디렉터리
            (proj / "scripts" / "build.sh").write_text("#!/bin/sh\n", encoding="utf-8")
            shutil.copy2(SOURCE, proj / "core" / "scripts" / "docs-index.py")
            docs_dir = proj / "core" / "docs" / "phases"
            self.write_phase_document(docs_dir)

            result = subprocess.run(
                [sys.executable, str(proj / "core" / "scripts" / "docs-index.py")],
                capture_output=True, text=True, timeout=10,
            )

            self.assertEqual(result.returncode, 0, f"{result.stdout}{result.stderr}")
            self.assertTrue(
                (docs_dir / "INDEX.md").is_file(),
                "매니페스트가 없는데도 조부모로 승격해 실제 문서를 건너뛰었다:\n"
                f"{result.stdout}{result.stderr}",
            )
