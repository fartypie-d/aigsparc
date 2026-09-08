"""kit-doctor.sh 테스트 — 주입된 HOME 으로 진단·drift·누락 복사 동작만 확인한다.

동결 규약 (PITFALLS 14): 이 파일은 오케스트레이터가 작성·동결했다. 위임 구현자는 수정하지 않는다.
실제 ~/.claude·~/.config 는 절대 건드리지 않는다 — 모든 실행에 --home 을 주입한다.
"""
import json
import os
import re
import shutil
import stat
import subprocess
import unittest
from pathlib import Path

from _install_helpers import KIT, RUN_TIMEOUT, temporary_directory

DOCTOR = KIT / "core" / "scripts" / "kit-doctor.sh"
DOCTOR_LINK = KIT / "scripts" / "kit-doctor.sh"
MANIFEST = KIT / "core" / "install-manifest.tsv"

HARNESS_VALUES = {"any", "claude", "codex"}
MODE_VALUES = {"file", "seed", "tree"}
STATUSES = ("OK", "WARN", "FAIL", "DRIFT", "ADDED")
SUMMARY_PREFIX = "KIT_DOCTOR:"

# 진단 스크립트가 PATH 에서 필요로 하는 최소 도구 — 필수 도구 부재 테스트에서
# jq 등 "점검 대상"만 빼고 이 목록은 채워 준다.
SUPPORT_TOOLS = (
    "awk", "basename", "bash", "cat", "chmod", "cmp", "cp", "cut", "date", "diff",
    "dirname", "grep", "head", "id", "ls", "mkdir", "mktemp", "mv", "printf",
    "readlink", "rm", "sed", "sort", "tail", "tr", "uname", "wc",
)


def read_manifest():
    """매니페스트를 (harness, mode, src, dst) 튜플 목록으로 읽는다."""
    if not MANIFEST.exists():
        raise AssertionError(f"매니페스트가 없다: {MANIFEST}")
    rows = []
    for number, raw in enumerate(MANIFEST.read_text().splitlines(), start=1):
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) != 4:
            raise AssertionError(f"{MANIFEST.name}:{number} 열이 4개가 아니다: {columns!r}")
        rows.append(tuple(column.strip() for column in columns))
    if not rows:
        raise AssertionError("매니페스트에 항목이 하나도 없다")
    return rows


def run_doctor(home, *args, path=None):
    """주입된 HOME·KIT 으로 kit-doctor.sh 를 실행한다."""
    env = os.environ.copy()
    env["HOME"] = str(home)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        ["bash", str(DOCTOR), "--home", str(home), "--kit", str(KIT), *args],
        capture_output=True, text=True, env=env, timeout=RUN_TIMEOUT,
    )


def report_lines(result, status):
    """리포트에서 특정 상태의 줄만 뽑는다."""
    found = []
    for line in (result.stdout + result.stderr).splitlines():
        stripped = line.strip()
        for candidate in STATUSES:
            if stripped.startswith(candidate):
                if candidate == status:
                    found.append(stripped)
                break
    return found


def summary_counts(result):
    """`KIT_DOCTOR: ok=.. warn=.. drift=.. fail=..` 요약을 딕셔너리로 읽는다."""
    text = result.stdout + result.stderr
    for line in text.splitlines():
        if line.strip().startswith(SUMMARY_PREFIX):
            return {
                key: int(value)
                for key, value in re.findall(r"(\w+)=(\d+)", line.split(SUMMARY_PREFIX, 1)[1])
            }
    raise AssertionError(f"요약 줄({SUMMARY_PREFIX})이 없다:\n{text}")


def populate_home(home, rows, harnesses=("claude", "codex")):
    """매니페스트대로 완전한 설치 상태를 만든다."""
    for harness, mode, src, dst in rows:
        if harness != "any" and harness not in harnesses:
            continue
        source = KIT / src
        target = Path(home) / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        if mode == "tree":
            target.mkdir(parents=True, exist_ok=True)
            for entry in sorted(source.iterdir()):
                destination = target / entry.name
                if entry.is_dir():
                    shutil.copytree(entry, destination, dirs_exist_ok=True)
                else:
                    shutil.copy2(entry, destination)
        else:
            shutil.copy2(source, target)


def support_path(home, extra_tools=()):
    """SUPPORT_TOOLS + extra_tools 만 담긴 PATH 를 만든다 (점검 대상 도구는 제외)."""
    bin_dir = Path(home) / "fakebin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in (*SUPPORT_TOOLS, *extra_tools):
        real = shutil.which(name)
        if real is None:
            continue
        wrapper = bin_dir / name
        wrapper.write_text(f'#!/bin/bash\nexec {real} "$@"\n')
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return str(bin_dir)


class ManifestTest(unittest.TestCase):
    def test_manifest_exists_with_required_columns(self):
        rows = read_manifest()
        for harness, mode, src, dst in rows:
            self.assertIn(harness, HARNESS_VALUES, f"알 수 없는 harness 열: {harness}")
            self.assertIn(mode, MODE_VALUES, f"알 수 없는 mode 열: {mode}")
            self.assertFalse(src.startswith("/"), f"src 는 KIT 상대경로여야 한다: {src}")
            self.assertFalse(dst.startswith(("/", "~")), f"dst 는 HOME 상대경로여야 한다: {dst}")

    def test_manifest_src_paths_exist_in_kit(self):
        for _harness, _mode, src, _dst in read_manifest():
            self.assertTrue((KIT / src).exists(), f"매니페스트 src 가 저장소에 없다: {src}")

    def test_manifest_covers_install_copy_targets(self):
        """install.sh 가 $HOME 에 배치하는 자산이 전부 매니페스트에 있어야 한다."""
        source = (KIT / "install.sh").read_text()
        copied = set(
            re.findall(
                r'backup_and_copy\s+"\$KIT_DIR/[^"]+"\s*\\?\s*"\$HOME/([^"$]+)"',
                source,
            )
        )
        self.assertTrue(copied, "install.sh 의 backup_and_copy 호출을 찾지 못했다")
        manifest_targets = {dst for _h, _m, _s, dst in read_manifest()}
        self.assertLessEqual(copied, manifest_targets,
                             f"매니페스트에 없는 install.sh 배치 대상: {sorted(copied - manifest_targets)}")
        for required in (".claude/skills", ".codex/prompts", ".config/opencode/secrets.env"):
            self.assertIn(required, manifest_targets)

    def test_kit_doctor_symlink_points_to_core(self):
        self.assertTrue(DOCTOR_LINK.is_symlink(), f"{DOCTOR_LINK} 가 심링크가 아니다")
        self.assertEqual(os.readlink(DOCTOR_LINK), "../core/scripts/kit-doctor.sh")

    def test_symlink_entrypoint_resolves_kit_root(self):
        """문서가 안내하는 `bash scripts/kit-doctor.sh` 경로로도 KIT 루트를 찾아야 한다.

        `scripts/` 는 `core/scripts/` 심링크다. `$0` 의 dirname 이 `scripts` 이므로
        `../..` 로 KIT 을 계산하면 한 단계를 지나쳐 저장소 밖을 가리킨다 —
        도그푸딩에서 실측됐다 (`FAIL 매니페스트: ~/core/install-manifest.tsv`).
        `--kit` 를 주지 않고(=실사용 형태) 호출해도 매니페스트를 찾아야 한다.
        """
        with temporary_directory() as home:
            env = os.environ.copy()
            env["HOME"] = str(home)
            result = subprocess.run(
                ["bash", "scripts/kit-doctor.sh", "--home", str(home), "--claude"],
                capture_output=True, text=True, env=env, cwd=str(KIT), timeout=RUN_TIMEOUT,
            )
            manifest_failures = [line for line in report_lines(result, "FAIL")
                                 if "매니페스트" in line]
            self.assertEqual(
                manifest_failures, [],
                "심링크로 호출하면 KIT 루트 계산이 어긋나 매니페스트를 찾지 못한다:\n"
                f"{result.stdout}{result.stderr}",
            )
            self.assertTrue(
                any(".config/opencode/opencode.json" in line
                    for line in report_lines(result, "FAIL")),
                f"매니페스트 항목을 점검하지 않았다:\n{result.stdout}{result.stderr}",
            )

    # Phase 12 회귀 가드 (오케스트레이터 작성·동결 — 위임 수정 금지)
    def test_real_path_entrypoint_resolves_kit_root(self):
        """실경로 `core/scripts/kit-doctor.sh` 호출이 계속 동작해야 한다.

        `install.sh:112` 이 `exec bash "$KIT_DIR/core/scripts/kit-doctor.sh"` 로
        실경로를 직접 부른다 — 심링크 진입점을 고치면서 이 경로를 깨뜨리면
        `install.sh --doctor` 전체가 죽는다.
        """
        with temporary_directory() as home:
            env = os.environ.copy()
            env["HOME"] = str(home)
            result = subprocess.run(
                ["bash", "core/scripts/kit-doctor.sh",
                 "--home", str(home), "--claude"],
                capture_output=True, text=True, env=env,
                cwd=str(KIT), timeout=RUN_TIMEOUT,
            )
            manifest_failures = [line for line in report_lines(result, "FAIL")
                                 if "매니페스트" in line]
            self.assertEqual(
                manifest_failures, [],
                "실경로 호출이 매니페스트를 찾지 못한다:\n"
                f"{result.stdout}{result.stderr}",
            )



class DoctorDiagnosisTest(unittest.TestCase):
    def test_clean_home_reports_missing_as_fail(self):
        with temporary_directory() as home:
            result = run_doctor(home, "--claude")
            fails = report_lines(result, "FAIL")
            self.assertTrue(fails, f"빈 HOME 인데 FAIL 이 없다:\n{result.stdout}{result.stderr}")
            self.assertTrue(
                any(".config/opencode/opencode.json" in line for line in fails),
                f"누락 자산이 FAIL 로 보고되지 않았다:\n{chr(10).join(fails)}",
            )
            self.assertGreater(summary_counts(result)["fail"], 0)
            self.assertEqual(result.returncode, 1, "FAIL 이 있으면 exit 1 이어야 한다")

    def test_complete_home_reports_ok_and_exit_zero(self):
        rows = read_manifest()
        with temporary_directory() as home:
            populate_home(home, rows)
            result = run_doctor(home, "--claude", "--codex")
            self.assertEqual(report_lines(result, "FAIL"), [],
                             f"완전한 설치인데 FAIL 이 있다:\n{result.stdout}{result.stderr}")
            self.assertEqual(report_lines(result, "DRIFT"), [],
                             f"원본과 동일한데 DRIFT 가 보고됐다:\n{result.stdout}{result.stderr}")
            self.assertEqual(result.returncode, 0)
            self.assertGreater(summary_counts(result)["ok"], 0)

    def test_modified_asset_reports_drift(self):
        rows = read_manifest()
        with temporary_directory() as home:
            populate_home(home, rows)
            drifted = Path(home) / ".config/opencode/opencode.json"
            drifted.write_text(drifted.read_text() + "\n# 사용자가 손으로 고친 흔적\n")
            result = run_doctor(home, "--claude", "--codex")
            drifts = report_lines(result, "DRIFT")
            self.assertTrue(
                any(".config/opencode/opencode.json" in line for line in drifts),
                f"변조된 자산이 DRIFT 로 보고되지 않았다:\n{result.stdout}{result.stderr}",
            )
            self.assertEqual(report_lines(result, "FAIL"), [], "drift 는 FAIL 이 아니다")
            self.assertGreater(summary_counts(result)["drift"], 0)
            self.assertEqual(result.returncode, 0, "drift 만 있으면 exit 0 이어야 한다")

    def test_seed_entry_never_reports_drift(self):
        rows = read_manifest()
        seeds = [row for row in rows if row[1] == "seed"]
        self.assertTrue(seeds, "매니페스트에 seed 모드 항목이 없다")
        with temporary_directory() as home:
            populate_home(home, rows)
            for _harness, _mode, _src, dst in seeds:
                (Path(home) / dst).write_text("XAI_API_KEY=사용자가-넣은-실제-키\n")
            result = run_doctor(home, "--claude", "--codex")
            for _harness, _mode, _src, dst in seeds:
                offending = [
                    line for line in report_lines(result, "DRIFT") + report_lines(result, "FAIL")
                    if dst in line
                ]
                self.assertEqual(offending, [], f"seed 항목을 문제로 보고했다: {offending}")

    def test_missing_required_tool_reports_fail(self):
        with temporary_directory() as home:
            path = support_path(home)  # jq·git·curl·python3 없음
            result = run_doctor(home, "--claude", path=path)
            fails = report_lines(result, "FAIL")
            self.assertTrue(any("jq" in line for line in fails),
                            f"필수 도구 jq 부재가 FAIL 로 보고되지 않았다:\n{result.stdout}{result.stderr}")
            self.assertEqual(result.returncode, 1)


class DoctorAddMissingTest(unittest.TestCase):
    def test_add_missing_creates_absent_assets(self):
        rows = read_manifest()
        with temporary_directory() as home:
            added = run_doctor(home, "--claude", "--codex", "--add-missing")
            self.assertTrue(report_lines(added, "ADDED"),
                            f"ADDED 보고가 없다:\n{added.stdout}{added.stderr}")
            for _harness, mode, src, dst in rows:
                target = Path(home) / dst
                self.assertTrue(target.exists(), f"--add-missing 후에도 자산이 없다: {dst}")
                if mode == "file":
                    self.assertEqual(target.read_bytes(), (KIT / src).read_bytes(),
                                     f"복사본이 킷 원본과 다르다: {dst}")
                if mode == "seed":
                    self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600,
                                     f"seed 파일 권한이 600 이 아니다: {dst}")
            again = run_doctor(home, "--claude", "--codex")
            self.assertEqual(report_lines(again, "FAIL"), [],
                             f"--add-missing 후 재진단에 FAIL 이 남았다:\n{again.stdout}{again.stderr}")
            self.assertEqual(again.returncode, 0)

    def test_add_missing_never_overwrites_existing(self):
        sentinel = "SENTINEL-KEEP-ME"
        rows = read_manifest()
        with temporary_directory() as home:
            populate_home(home, rows)
            kept = Path(home) / ".config/opencode/opencode.json"
            kept.write_text(sentinel)
            run_doctor(home, "--claude", "--codex", "--add-missing")
            self.assertEqual(kept.read_text(), sentinel,
                             "--add-missing 이 기존 파일을 덮었다 (데이터 손실)")

    def test_add_missing_does_not_touch_drifted_files(self):
        rows = read_manifest()
        with temporary_directory() as home:
            populate_home(home, rows)
            drifted = Path(home) / ".config/orchestrate/ONBOARD-PROCEDURE.md"
            drifted.write_text("사용자가 고친 절차\n")
            result = run_doctor(home, "--claude", "--codex", "--add-missing")
            self.assertEqual(drifted.read_text(), "사용자가 고친 절차\n",
                             "--add-missing 이 drift 파일을 덮었다")
            self.assertTrue(
                any(".config/orchestrate/ONBOARD-PROCEDURE.md" in line
                    for line in report_lines(result, "DRIFT")),
                f"drift 보고가 사라졌다:\n{result.stdout}{result.stderr}",
            )


class DoctorFalseAllClearTest(unittest.TestCase):
    """거짓 안심(false all-clear) 방지 — silent-failure-hunter·bash-reviewer 지적(2026-08-17) 동결.

    진단 도구의 최악 실패는 "점검하지 못한 것"을 "문제 없음"으로 보고하는 것이다.
    """

    def test_skipped_harness_rows_are_reported_each(self):
        """하네스 미검출로 스킵한 행은 통째로 침묵하지 말고 행마다 보고해야 한다."""
        rows = read_manifest()
        harness_targets = [dst for harness, _mode, _src, dst in rows if harness != "any"]
        self.assertTrue(harness_targets, "매니페스트에 하네스 전용 행이 없다")
        with temporary_directory() as home:
            path = support_path(home, extra_tools=("git", "curl", "python3", "jq"))
            populate_home(home, [row for row in rows if row[0] == "any"], harnesses=())
            result = run_doctor(home, path=path)  # 하네스 플래그 없음 + PATH 에 CLI 없음
            reported = report_lines(result, "WARN") + report_lines(result, "FAIL")
            for target in harness_targets:
                self.assertTrue(
                    any(target in line for line in reported),
                    f"점검하지 못한 행({target})을 보고하지 않고 침묵했다:\n"
                    f"{result.stdout}{result.stderr}",
                )

    def test_empty_manifest_is_reported_not_silently_clean(self):
        """유효 행이 0건인 매니페스트가 '전부 정상'과 구별돼야 한다."""
        with temporary_directory() as home:
            manifest = Path(home) / "empty-manifest.tsv"
            manifest.write_text("# harness\tmode\tsrc\tdst\n\n")
            result = run_doctor(home, "--claude", "--manifest", str(manifest))
            reported = report_lines(result, "WARN") + report_lines(result, "FAIL")
            self.assertTrue(
                any(str(manifest) in line or "매니페스트" in line for line in reported),
                f"빈 매니페스트를 조용히 통과시켰다:\n{result.stdout}{result.stderr}",
            )

    def test_missing_harness_asset_is_fail(self):
        """--claude 를 명시했는데 스킬 자산이 없으면 FAIL 이다 (심각도 판정 표 확정분)."""
        rows = read_manifest()
        with temporary_directory() as home:
            populate_home(home, [row for row in rows if row[0] == "any"], harnesses=())
            result = run_doctor(home, "--claude")
            fails = report_lines(result, "FAIL")
            self.assertTrue(any(".claude/skills" in line for line in fails),
                            f"하네스 자산 부재가 FAIL 이 아니다:\n{result.stdout}{result.stderr}")
            self.assertEqual(result.returncode, 1)

    def test_report_has_no_foreign_lines(self):
        """리포트는 고정 문법만 출력해야 한다 — cmp/diff 자체 stderr 가 새면 파싱이 깨진다."""
        rows = read_manifest()
        with temporary_directory() as home:
            populate_home(home, rows)
            # dst 를 디렉터리로 바꿔 cmp 를 exit 2 (비교 실패)로 만든다.
            broken = Path(home) / ".config/orchestrate/ONBOARD-PROCEDURE.md"
            broken.unlink()
            broken.mkdir()
            result = run_doctor(home, "--claude", "--codex")
            foreign = [
                line for line in (result.stdout + result.stderr).splitlines()
                if line.strip()
                and not line.strip().startswith(STATUSES)
                and not line.strip().startswith(SUMMARY_PREFIX)
            ]
            self.assertEqual(foreign, [],
                             f"리포트 문법에 없는 줄이 새어 나왔다: {foreign}")


class DoctorRepairHonestyTest(unittest.TestCase):
    """"고쳐준다"는 약속의 정직성 — silent-failure-hunter 지적(2026-08-17 Task 4 리뷰) 동결.

    진단·복구 도구가 자기가 만든 손상을 정상으로 보고하면, 사용자는 복구됐다고 믿는다.
    """

    def write_manifest(self, directory, rows):
        path = Path(directory) / "manifest.tsv"
        path.write_text("".join("\t".join(row) + "\n" for row in rows))
        return path

    def test_seed_with_loose_permissions_is_reported(self):
        """secrets.env 가 600 보다 넓으면 보고해야 한다 (chmod 실패가 영구히 은폐되는 것을 막는다)."""
        rows = read_manifest()
        seeds = [row for row in rows if row[1] == "seed"]
        with temporary_directory() as home:
            populate_home(home, rows)
            for _harness, _mode, _src, dst in seeds:
                target = Path(home) / dst
                target.write_text("XAI_API_KEY=키\n")
                target.chmod(0o644)
            result = run_doctor(home, "--claude", "--codex")
            for _harness, _mode, _src, dst in seeds:
                reported = [line for line in report_lines(result, "WARN") + report_lines(result, "FAIL")
                            if dst in line]
                self.assertTrue(
                    reported,
                    f"자격증명 파일이 644 인데 문제로 보고하지 않았다 ({dst}):\n"
                    f"{result.stdout}{result.stderr}",
                )

    def failing_mv_path(self, home):
        """mv 만 실패하는 PATH 를 만든다 (일시적 복사 장애 재현용)."""
        bin_dir = Path(home) / "failbin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        for name in SUPPORT_TOOLS:
            real = shutil.which(name)
            if real is None or name == "mv":
                continue
            wrapper = bin_dir / name
            wrapper.write_text(f'#!/bin/bash\nexec {real} "$@"\n')
            wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
        failing = bin_dir / "mv"
        failing.write_text('#!/bin/bash\necho "mv: 일시적 실패" >&2\nexit 1\n')
        failing.chmod(failing.stat().st_mode | stat.S_IXUSR)
        return f"{bin_dir}:{os.environ.get('PATH', '')}"

    def test_staging_leftover_is_reported(self):
        """스테이징 잔재가 사용자 홈에 쌓이는데 진단이 침묵하면 "정상"이라는 착각을 준다."""
        rows = read_manifest()
        with temporary_directory() as home:
            populate_home(home, rows)
            target = Path(home) / ".config/opencode/opencode.json"
            target.unlink()
            leftover = Path(str(target) + ".kit-partial")
            leftover.write_text("이전 실패가 남긴 잔재\n")
            result = run_doctor(home, "--claude", "--codex")  # --add-missing 없는 평범한 진단
            reported = [line for line in report_lines(result, "WARN") + report_lines(result, "FAIL")
                        if "kit-partial" in line]
            self.assertTrue(
                reported,
                "스테이징 잔재가 홈에 남아 있는데 어떤 진단 줄에도 나타나지 않았다:\n"
                f"{result.stdout}{result.stderr}",
            )

    def test_transient_copy_failure_can_be_repaired_by_retry(self):
        """일시적 복사 장애가 해소되면 재시도가 실제로 복구해야 한다 (잔재가 복구를 막지 않을 것)."""
        rows = read_manifest()
        target_dst = ".config/opencode/opencode.json"
        with temporary_directory() as home:
            populate_home(home, [row for row in rows if row[3] != target_dst])
            first = run_doctor(home, "--claude", "--codex", "--add-missing",
                              path=self.failing_mv_path(home))
            self.assertEqual(first.returncode, 1,
                             f"mv 실패를 FAIL 로 알리지 않았다:\n{first.stdout}{first.stderr}")
            # 장애 해소 후 재시도 — 실제로 복구돼야 한다.
            second = run_doctor(home, "--claude", "--codex", "--add-missing")
            self.assertTrue(
                (Path(home) / target_dst).exists(),
                "일시적 장애가 해소됐는데도 재시도가 자산을 복구하지 못했다 "
                f"(잔재가 복구를 영구히 막는다):\n{second.stdout}{second.stderr}",
            )

    def test_failed_tree_copy_does_not_settle_into_silent_success(self):
        """tree 복사가 부분 실패하면, 재실행이 조용한 성공(exit 0)으로 굳어선 안 된다."""
        source_root = KIT / ".orchestrate" / "testsrc-tree"
        entry = source_root / "mytool"
        (entry / "sub").mkdir(parents=True, exist_ok=True)
        (entry / "a.txt").write_text("정상 파일\n")
        blocked = entry / "sub" / "c.txt"
        blocked.write_text("읽을 수 없는 파일\n")
        blocked.chmod(0o000)
        self.addCleanup(lambda: (blocked.chmod(0o644), shutil.rmtree(source_root, True)))
        with temporary_directory() as home:
            manifest = self.write_manifest(home, [
                ("any", "tree", ".orchestrate/testsrc-tree", ".claude/skills"),
            ])
            first = run_doctor(home, "--claude", "--manifest", str(manifest), "--add-missing")
            self.assertEqual(first.returncode, 1,
                             f"부분 복사 실패를 FAIL 로 알리지 않았다:\n{first.stdout}{first.stderr}")
            second = run_doctor(home, "--claude", "--manifest", str(manifest), "--add-missing")
            self.assertNotEqual(
                second.returncode, 0,
                "복사가 실패해 손상된 트리를 남긴 뒤, 재실행이 조용한 성공(exit 0)으로 굳었다 — "
                "고치지도 못하고 문제도 알리지 않는다:\n"
                f"{second.stdout}{second.stderr}",
            )


class DoctorPathContainmentTest(unittest.TestCase):
    """경로 봉쇄 — security-reviewer 지적(2026-08-17, Task 2 리뷰)을 동결한다.

    프로즈 조건은 죽는다. `--add-missing` 이 임의 파일 쓰기로 변질되지 않도록
    이탈 경로·심링크 거부를 테스트로 강제한다 (CWE-22 / CWE-59).
    """

    def write_manifest(self, directory, rows):
        path = Path(directory) / "manifest.tsv"
        path.write_text("".join("\t".join(row) + "\n" for row in rows))
        return path

    def test_traversal_in_manifest_dst_is_refused(self):
        with temporary_directory() as home:
            outside = Path(home).parent / "kit-doctor-outside-marker"
            outside.write_text("이 파일은 HOME 밖에 있다\n")
            self.addCleanup(outside.unlink)
            manifest = self.write_manifest(home, [
                ("any", "file", "core/opencode/opencode.json", f"../{outside.name}"),
            ])
            result = run_doctor(home, "--claude", "--manifest", str(manifest))
            # 이탈 행이 OK·DRIFT 로 판정되면 HOME 밖 파일을 실제로 열었다는 뜻이다.
            for status in ("OK", "DRIFT"):
                leaked = [line for line in report_lines(result, status) if outside.name in line]
                self.assertEqual(leaked, [],
                                 f"HOME 밖 경로를 {status} 로 판정했다 (경로 이탈): {leaked}")
            # 그 행 자체가 거부로 보고돼야 한다 — 무관한 WARN 으로 통과하지 못하게 dst 를 특정한다.
            refused = [line for line in report_lines(result, "FAIL") + report_lines(result, "WARN")
                       if outside.name in line]
            self.assertTrue(refused,
                            f"경로 이탈 행을 거부 보고하지 않았다:\n{result.stdout}{result.stderr}")

    def test_traversal_in_manifest_src_is_refused(self):
        # KIT 밖에 실재하는 파일을 가리킨다 — "경로가 해석되지 않아서" 통과하는 우연을 배제한다
        # (저장소 깊이에 의존하는 ../../../../etc/passwd 는 단정으로 쓸 수 없다).
        marker = KIT.parent / "kit-doctor-src-marker.json"
        marker.write_text('{"이 파일은": "KIT 밖에 있다"}\n')
        self.addCleanup(marker.unlink)
        with temporary_directory() as home:
            # dst 는 실재하게 만든다 — 거부가 없으면 OK·DRIFT 로 판정될 상황이어야 단정이 유효하다.
            destination = Path(home) / ".config/opencode/opencode.json"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(KIT / "core/opencode/opencode.json", destination)
            manifest = self.write_manifest(home, [
                ("any", "file", f"../{marker.name}", ".config/opencode/opencode.json"),
            ])
            result = run_doctor(home, "--claude", "--manifest", str(manifest))
            for status in ("OK", "DRIFT"):
                leaked = [line for line in report_lines(result, status)
                          if ".config/opencode/opencode.json" in line]
                self.assertEqual(leaked, [],
                                 f"킷 밖 src 를 {status} 로 판정했다 (경로 이탈): {leaked}")
            refused = [line for line in report_lines(result, "FAIL") + report_lines(result, "WARN")
                       if ".config/opencode/opencode.json" in line]
            self.assertTrue(refused,
                            f"킷 밖 src 행을 거부 보고하지 않았다:\n{result.stdout}{result.stderr}")

    def test_add_missing_does_not_write_under_symlinked_parent(self):
        """부모 디렉터리가 심링크고 목적지 부모가 아직 없으면, mkdir -p 가 링크를 타고 밖에 만든다.

        재검증 리뷰(silent-failure-hunter, 2026-08-17)가 지적한 폴백이다:
        `parent_is_within_root` 는 부모가 없으면 통과시킨다 — 읽기 전용일 때는 무해하지만
        쓰기(`--add-missing`)가 붙으면 CWE-59 우회로가 된다.
        """
        rows = read_manifest()
        with temporary_directory() as home:
            outside = Path(home).parent / "kit-doctor-outside-config"
            outside.mkdir(exist_ok=True)
            self.addCleanup(shutil.rmtree, outside, True)
            # $HOME/.config 를 HOME 밖으로 향하는 심링크로 만든다 (opencode/ 는 아직 없다).
            (Path(home) / ".config").symlink_to(outside)
            run_doctor(home, "--claude", "--codex", "--add-missing")
            escaped = list(outside.rglob("*"))
            self.assertEqual(escaped, [],
                             f"--add-missing 이 심링크 부모를 타고 HOME 밖에 썼다: {escaped}")

    def test_add_missing_does_not_write_through_dangling_symlink(self):
        """끊어진 심링크는 [ -e ] 가 false 다 — 그대로 복사하면 HOME 밖에 쓴다 (CWE-59).

        ⚠️ "밖에 쓰였는가" 단정만으로는 이 가드를 증명할 수 없다 — GNU coreutils 의 `cp` 가
        `not writing through dangling symlink` 로 자체 거부하기 때문에 가드를 지워도 Linux 에선
        유출이 없다 (2026-08-17 변이 검증에서 실측). macOS `cp` 는 링크를 따라가 쓴다.
        따라서 **심링크 dst 가 WARN 으로 보고되는지**를 하중을 받는 단정으로 삼는다
        (가드를 지우면 `FAIL ... 복사할 수 없다` 가 되어 이 단정이 죽는다).
        """
        rows = read_manifest()
        with temporary_directory() as home:
            outside = Path(home).parent / "kit-doctor-symlink-target.json"
            if outside.exists():
                outside.unlink()
            link = Path(home) / ".config/opencode/opencode.json"
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(outside)
            populate_home(home, [row for row in rows if row[3] != ".config/opencode/opencode.json"])
            result = run_doctor(home, "--claude", "--codex", "--add-missing")
            wrote_outside = outside.exists()
            if wrote_outside:
                outside.unlink()
            self.assertFalse(wrote_outside,
                             "--add-missing 이 심링크를 타고 HOME 밖에 파일을 만들었다")
            # 하중을 받는 단정: 심링크 dst 는 복사 실패(FAIL)가 아니라 WARN 으로 보고돼야 한다.
            warned = [line for line in report_lines(result, "WARN")
                      if ".config/opencode/opencode.json" in line]
            self.assertTrue(
                warned,
                "끊어진 심링크를 WARN 으로 보고하지 않았다 (가드가 없으면 cp 실패 FAIL 이 된다):\n"
                f"{result.stdout}{result.stderr}",
            )


class InstallDoctorDispatchTest(unittest.TestCase):
    def run_install_doctor(self, home, *args, path=None):
        env = os.environ.copy()
        env["HOME"] = str(home)
        if path is not None:
            env["PATH"] = path
        return subprocess.run(
            ["bash", str(KIT / "install.sh"), "--doctor", *args],
            capture_output=True, text=True, input="", env=env, timeout=RUN_TIMEOUT,
        )

    def test_install_doctor_dispatches_to_kit_doctor(self):
        with temporary_directory() as home:
            result = self.run_install_doctor(home, "--claude")
            self.assertIn(SUMMARY_PREFIX, result.stdout + result.stderr,
                          f"install.sh --doctor 가 kit-doctor 리포트를 내지 않았다:\n{result.stdout}{result.stderr}")
            self.assertFalse((Path(home) / ".claude" / "skills").exists(),
                             "--doctor 가 설치 부작용을 냈다 (읽기 전용이어야 한다)")
            self.assertEqual(result.returncode, 1, "누락 자산이 있으면 exit 1 을 물려받아야 한다")

    def test_parse_only_still_reflects_harness_autodetection(self):
        """--doctor dispatch 를 넣느라 자동감지를 파싱 훅 뒤로 밀면 훅이 실제 동작을 반영하지 못한다.

        INSTALL_PARSE_ONLY 는 "실제 실행이 어떤 값으로 돌 것인가"를 보는 훅이다. 자동감지가
        그 뒤로 밀리면 훅은 항상 빈 HARNESSES 를 보고하고, 훅으로 하는 모든 판정이 무의미해진다.
        """
        with temporary_directory() as home:
            path = support_path(home, extra_tools=("git", "curl", "python3", "jq"))
            stub = Path(path) / "claude"
            stub.write_text("#!/bin/bash\nexit 0\n")
            stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env.update({"HOME": str(home), "PATH": path, "INSTALL_PARSE_ONLY": "1"})
            result = subprocess.run(
                ["bash", str(KIT / "install.sh"), "typescript"],
                capture_output=True, text=True, env=env, timeout=RUN_TIMEOUT,
            )
            self.assertIn("HARNESSES=claude", result.stdout,
                          "파싱 훅이 하네스 자동감지 결과를 반영하지 않는다 "
                          f"(자동감지가 훅 뒤로 밀렸다):\n{result.stdout}{result.stderr}")

    def test_install_doctor_forwards_add_missing(self):
        """공식 진입점(install.sh --doctor)에서 --add-missing 을 쓸 수 있어야 한다.

        배선이 없으면 `알 수 없는 옵션` exit 64 로 죽어, 페이즈의 목표(설치를 진단하고 채워준다)에
        사용자가 도달할 방법이 없다 (silent-failure-hunter 지적, 2026-08-17).
        """
        with temporary_directory() as home:
            result = self.run_install_doctor(home, "--claude", "--add-missing")
            self.assertNotEqual(result.returncode, 64,
                                f"install.sh 가 --add-missing 을 모른다:\n{result.stdout}{result.stderr}")
            self.assertTrue(
                (Path(home) / ".config/opencode/opencode.json").exists(),
                f"--add-missing 이 전달되지 않아 자산이 채워지지 않았다:\n{result.stdout}{result.stderr}",
            )

    def test_doctor_rejects_incompatible_install_options(self):
        """--doctor 는 설치 옵션과 함께 쓸 수 없다 — 조용히 무시하면 설치됐다고 오신한다.

        silent-failure-hunter 재현(2026-08-17): `--doctor --containers=browser --providers=openai
        typescript` 가 진단만 하고 exit 1 로 끝났다. 컨테이너·프로바이더·ECC 언어는 파싱만 되고
        아무 경고 없이 버려졌다. 허용 조합은 `--claude`·`--codex`·`--add-missing` 뿐이다.
        """
        with temporary_directory() as home:
            for offending in ("--containers=browser", "--providers=openai", "--plan=pro", "typescript"):
                result = self.run_install_doctor(home, "--claude", offending)
                self.assertEqual(
                    result.returncode, 64,
                    f"--doctor 와 {offending} 조합을 거부하지 않았다:\n{result.stdout}{result.stderr}",
                )
                self.assertNotIn(
                    SUMMARY_PREFIX, result.stdout,
                    f"거부해야 하는데 진단을 수행했다 ({offending}):\n{result.stdout}",
                )

    def test_doctor_runs_without_detected_harness(self):
        """하네스 CLI 가 하나도 없는 호스트에서도 진단이 돌아야 한다 (install.sh:92 exit 64 회피)."""
        with temporary_directory() as home:
            path = support_path(home, extra_tools=("git", "curl", "python3", "jq"))
            result = self.run_install_doctor(home, path=path)
            self.assertNotEqual(result.returncode, 64,
                                f"하네스 미검출로 죽었다 (exit 64):\n{result.stdout}{result.stderr}")
            self.assertIn(SUMMARY_PREFIX, result.stdout + result.stderr,
                          f"리포트가 출력되지 않았다:\n{result.stdout}{result.stderr}")




class DoctorResolveSelftestTest(unittest.TestCase):
    """Phase 12 RED (오케스트레이터 작성·동결 — 위임 수정 금지).

    심링크 해석 실패 경로는 커널이 exec 단계에서 먼저 막아 정상 호출로는
    도달할 수 없다(리뷰어 2인 실측). 따라서 저장소가 이미 쓰는 자가검증 훅
    패턴(`INSTALL_SELFTEST_MENU`)을 따라 주입해 계약을 고정한다.

    계약: `KIT_DOCTOR_SELFTEST_RESOLVE=<경로>` 를 주면 kit-doctor 는
    **본체와 동일한 해석 코드**로 그 경로를 풀고, 그 결과만 출력한 뒤 끝낸다.
      - 성공: stdout 에 `RESOLVE_OK <실경로 디렉터리>`, exit 0
      - 실패: stdout 에 `RESOLVE_FAIL <사유>`, exit 1 (사유: cap|readlink|cd|missing)
    실패를 조용히 통과시키면 안 된다 — 이 페이즈가 고치려던 결함이 그것이다.
    """

    def run_resolve(self, target):
        env = os.environ.copy()
        env["KIT_DOCTOR_SELFTEST_RESOLVE"] = str(target)
        return subprocess.run(
            ["bash", "core/scripts/kit-doctor.sh"],
            capture_output=True, text=True, env=env,
            cwd=str(KIT), timeout=RUN_TIMEOUT,
        )

    def test_selftest_resolves_ordinary_symlink(self):
        """평범한 상대 심링크는 타깃의 실디렉터리로 해석돼야 한다."""
        with temporary_directory() as tmp:
            root = Path(tmp)
            (root / "core" / "scripts").mkdir(parents=True)
            real = root / "core" / "scripts" / "victim.sh"
            real.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (root / "scripts").mkdir()
            link = root / "scripts" / "victim.sh"
            os.symlink("../core/scripts/victim.sh", link)

            result = self.run_resolve(link)

            self.assertEqual(result.returncode, 0, f"{result.stdout}{result.stderr}")
            self.assertIn(
                f"RESOLVE_OK {root / 'core' / 'scripts'}", result.stdout,
                f"실경로 디렉터리로 해석하지 못했다:\n{result.stdout}{result.stderr}",
            )

    def test_selftest_reports_failure_when_cap_exceeded(self):
        """반복 상한을 넘겨도 조용히 진행하면 안 된다 — 사유와 함께 실패해야 한다."""
        with temporary_directory() as tmp:
            root = Path(tmp)
            root_link = root / "hop0"
            # 상한(40)을 넘는 체인. 마지막은 실파일이라 순환이 아니다 —
            # 커널 ELOOP 가 아니라 스크립트 자신의 상한이 걸리는 형태다.
            depth = 45
            (root / f"hop{depth}").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            for i in range(depth - 1, -1, -1):
                os.symlink(f"hop{i + 1}", root / f"hop{i}")

            result = self.run_resolve(root_link)

            self.assertEqual(
                result.returncode, 1,
                f"상한 초과인데 실패로 끝나지 않았다:\n{result.stdout}{result.stderr}",
            )
            self.assertIn(
                "RESOLVE_FAIL", result.stdout,
                f"상한 초과를 보고하지 않았다:\n{result.stdout}{result.stderr}",
            )

    def test_selftest_reports_failure_when_target_missing(self):
        """댕글링 심링크는 존재하지 않는 경로로 조용히 해석되면 안 된다."""
        with temporary_directory() as tmp:
            root = Path(tmp)
            link = root / "dangling.sh"
            os.symlink("no-such-target.sh", link)

            result = self.run_resolve(link)

            self.assertEqual(
                result.returncode, 1,
                f"댕글링인데 실패로 끝나지 않았다:\n{result.stdout}{result.stderr}",
            )
            self.assertIn(
                "RESOLVE_FAIL", result.stdout,
                f"댕글링 타깃을 보고하지 않았다:\n{result.stdout}{result.stderr}",
            )

    # Phase 12 라운드 2 RED (오케스트레이터 작성·동결 — 위임 수정 금지)
    def test_selftest_resolves_target_with_trailing_slash(self):
        """심링크 타깃 문자열의 후행 슬래시가 해석을 조기 종료시키면 안 된다.

        POSIX 에서 `[ -L "path/" ]` 는 대상이 심링크여도 **항상 거짓**이다.
        타깃에 후행 슬래시가 붙어 있으면 루프가 '해석 완료'로 오판하고 멈춰,
        아직 심링크인 경로를 최종 결과로 삼는다 — 오류 없이 exit 0 인 조용한 오답이다.

        실측(수정 전): entry → "mid/" → deep/realdir 에서
          후행 슬래시 있음 → RESOLVE_OK <T>       (틀림)
          후행 슬래시 없음 → RESOLVE_OK <T>/deep  (맞음)
        같은 체인인데 슬래시 하나로 답이 갈렸다.
        """
        with temporary_directory() as tmp:
            root = Path(tmp)
            (root / "deep" / "realdir").mkdir(parents=True)
            os.symlink("deep/realdir", root / "mid")
            os.symlink("mid/", root / "entry")

            result = self.run_resolve(root / "entry")

            self.assertEqual(result.returncode, 0, f"{result.stdout}{result.stderr}")
            self.assertIn(
                f"RESOLVE_OK {root / 'deep'}", result.stdout,
                "후행 슬래시 때문에 심링크를 끝까지 풀지 못했다:\n"
                f"{result.stdout}{result.stderr}",
            )


# Phase 17 task 1a RED (오케스트레이터 작성·동결 — 위임 수정 금지)
SUPERVISOR_PROCEDURE_ROW = (
    "claude", "file", "core/supervisor/PROCEDURE.md", ".claude/supervisor/PROCEDURE.md",
)
SUPERVISOR_COMMANDS_ROW = (
    "claude", "tree", "adapters/claude/global/commands", ".claude/commands",
)


def run_doctor_with_state(home, state_home, *args):
    """감독 상태 디렉터리(XDG_STATE_HOME)까지 격리해 kit-doctor.sh 를 실행한다."""
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_STATE_HOME"] = str(state_home)
    return subprocess.run(
        ["bash", str(DOCTOR), "--home", str(home), "--kit", str(KIT), *args],
        capture_output=True, text=True, env=env, timeout=RUN_TIMEOUT,
    )


class SupervisorManifestTest(unittest.TestCase):
    """감독 시작 계층이 손 설치본이 아니라 매니페스트로 깔린다 (task 1b 계약)."""

    def test_manifest_installs_supervisor_procedure_and_commands(self):
        rows = read_manifest()
        self.assertIn(SUPERVISOR_PROCEDURE_ROW, rows,
                      "매니페스트에 core/supervisor/PROCEDURE.md 행이 없다")
        self.assertIn(SUPERVISOR_COMMANDS_ROW, rows,
                      "매니페스트에 adapters/claude/global/commands 트리 행이 없다")

        procedure = KIT / "core" / "supervisor" / "PROCEDURE.md"
        self.assertTrue(procedure.exists(), f"킷 원본이 없다: {procedure}")
        commands = KIT / "adapters" / "claude" / "global" / "commands"
        self.assertTrue((commands / "supervise.md").exists(),
                        "범용 supervise 커맨드 원본이 없다")
        self.assertTrue((commands / "supervise-PROJECT.md.tpl").exists(),
                        "프로젝트별 supervise 커맨드 템플릿이 없다")

        with temporary_directory() as home:
            result = run_doctor(home, "--claude", "--add-missing")
            installed = Path(home) / ".claude/supervisor/PROCEDURE.md"
            self.assertTrue(installed.exists(),
                            f"--add-missing 이 PROCEDURE.md 를 깔지 않았다:\n"
                            f"{result.stdout}{result.stderr}")
            self.assertEqual(installed.read_bytes(), procedure.read_bytes(),
                             "설치본이 킷 원본과 다르다")
            self.assertTrue((Path(home) / ".claude/commands/supervise.md").exists(),
                            "--add-missing 이 범용 supervise 커맨드를 깔지 않았다")


class SupervisorDriftTest(unittest.TestCase):
    """레지스트리에 있는 프로젝트인데 감독 자산이 없으면 침묵하지 않는다."""

    PROJECT = "regdemo"

    def write_registry(self, state_home, root):
        registry = Path(state_home) / "orchestrate" / "registry" / f"{self.PROJECT}.json"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({
            "project": self.PROJECT,
            "root": str(root),
            "docs_dir": "docs/phases",
            "default_branch": "main",
        }, ensure_ascii=False), encoding="utf-8")
        return registry

    def write_supervisor_assets(self, home, state_home):
        command = Path(home) / ".claude" / "commands" / f"supervise-{self.PROJECT}.md"
        command.parent.mkdir(parents=True, exist_ok=True)
        template = KIT / "adapters/claude/global/commands/supervise-PROJECT.md.tpl"
        body = (template.read_text(encoding="utf-8").replace("__PROJECT__", self.PROJECT)
                if template.exists() else f"# supervise {self.PROJECT}\n")
        command.write_text(body, encoding="utf-8")

        supervisor = Path(state_home) / "orchestrate" / "supervisor"
        supervisor.mkdir(parents=True, exist_ok=True)
        (supervisor / f"{self.PROJECT}.json").write_text(json.dumps({
            "project": self.PROJECT, "root": str(home), "phase": None, "slug": None,
            "worktree": None, "branch": None, "part": None, "status": "idle",
            "child": None, "cost": {"phase_usd": 0, "parts": {}},
            "phases_since_review": 0, "last_review": "2026-09-02", "owner": None,
        }, ensure_ascii=False), encoding="utf-8")
        (supervisor / f"actions-{self.PROJECT}.md").write_text("", encoding="utf-8")

    def project_drift_lines(self, result):
        return [line for line in report_lines(result, "DRIFT") if self.PROJECT in line]

    def test_registry_without_supervisor_assets_reports_drift(self):
        with temporary_directory() as home:
            state_home = Path(home) / ".local" / "state"
            self.write_registry(state_home, home)

            result = run_doctor_with_state(home, state_home, "--claude")

            self.assertTrue(
                self.project_drift_lines(result),
                "레지스트리에 있는 프로젝트의 감독 자산이 없는데 침묵했다:\n"
                f"{result.stdout}{result.stderr}",
            )
            self.assertGreaterEqual(
                summary_counts(result).get("drift", 0), 1,
                f"요약 drift 카운트가 오르지 않았다:\n{result.stdout}{result.stderr}",
            )

    def test_registry_with_supervisor_assets_reports_no_drift(self):
        """반대 방향 — 자산이 갖춰져 있으면 이 프로젝트로 drift 를 내지 않는다."""
        with temporary_directory() as home:
            state_home = Path(home) / ".local" / "state"
            self.write_registry(state_home, home)
            self.write_supervisor_assets(home, state_home)

            result = run_doctor_with_state(home, state_home, "--claude")

            self.assertEqual(
                self.project_drift_lines(result), [],
                "감독 자산이 다 있는데 drift 를 보고했다 (항상 참인 경보):\n"
                f"{result.stdout}{result.stderr}",
            )
            # 침묵으로 통과하는 것과 실제로 점검한 것을 구분한다 —
            # 점검했다면 이 프로젝트 이름이 들어간 OK 보고가 있어야 한다.
            self.assertTrue(
                [line for line in report_lines(result, "OK") if self.PROJECT in line],
                "레지스트리 프로젝트를 점검한 흔적(OK 보고)이 없다:\n"
                f"{result.stdout}{result.stderr}",
            )

    def test_add_missing_creates_supervisor_assets_for_registered_project(self):
        with temporary_directory() as home:
            state_home = Path(home) / ".local" / "state"
            self.write_registry(state_home, home)

            result = run_doctor_with_state(home, state_home, "--claude", "--add-missing")

            command = Path(home) / ".claude" / "commands" / f"supervise-{self.PROJECT}.md"
            state = Path(state_home) / "orchestrate" / "supervisor" / f"{self.PROJECT}.json"
            self.assertTrue(command.exists(),
                            f"--add-missing 이 supervise 커맨드를 만들지 않았다:\n"
                            f"{result.stdout}{result.stderr}")
            self.assertTrue(state.exists(),
                            f"--add-missing 이 감독 상태 파일을 만들지 않았다:\n"
                            f"{result.stdout}{result.stderr}")


if __name__ == "__main__":
    unittest.main()
