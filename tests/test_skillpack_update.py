"""skillpack-update-check.sh 테스트 — 임시 git 저장소로 외부 의존을 격리한다.

plugin 타입은 gh 네트워크 호출이 필요하므로 여기서는 다루지 않는다.
repo 타입 감지·해제와 설정 파일 처리 경계만 검증한다.
"""
import subprocess
import unittest
from pathlib import Path

from _install_helpers import temporary_directory

KIT = Path(__file__).resolve().parents[1]
SCRIPT = KIT / "core/scripts/skillpack-update-check.sh"


def git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(cwd),
             "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"},
    )


class SkillpackUpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = temporary_directory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.state = self.work / "state"
        self.conf = self.work / "packs.conf"

    def make_repo_pair(self):
        """업스트림과 그 클론을 만들고 (upstream, clone) 경로를 돌려준다."""
        upstream = self.work / "upstream"
        upstream.mkdir()
        git(upstream, "init", "-q", "-b", "main")
        (upstream / "a.txt").write_text("1\n")
        git(upstream, "add", "a.txt")
        git(upstream, "commit", "-q", "-m", "c1")
        clone = self.work / "clone"
        subprocess.run(
            ["git", "clone", "-q", str(upstream), str(clone)],
            capture_output=True, text=True, check=True,
        )
        return upstream, clone

    def run_check(self, home=None):
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(home or self.work),
            "SKILLPACK_CONF": str(self.conf),
            "SKILLPACK_STATE": str(self.state),
        }
        return subprocess.run(
            ["bash", str(SCRIPT)],
            capture_output=True, text=True, env=env, timeout=30,
        )

    def test_behind_repo_writes_notice(self):
        upstream, clone = self.make_repo_pair()
        (upstream / "a.txt").write_text("2\n")
        git(upstream, "commit", "-q", "-am", "c2")
        self.conf.write_text(f"repo\tdemo\t{clone}\torigin/main\n")

        result = self.run_check()

        self.assertEqual(result.returncode, 0, result.stderr)
        notice = self.state / "NOTICE.md"
        self.assertTrue(notice.exists(), result.stderr)
        body = notice.read_text()
        self.assertIn("demo (repo)", body)
        self.assertIn("1커밋 behind", body)

    def test_up_to_date_repo_removes_notice(self):
        _, clone = self.make_repo_pair()
        self.conf.write_text(f"repo\tdemo\t{clone}\torigin/main\n")
        self.state.mkdir(parents=True)
        (self.state / "NOTICE.md").write_text("stale\n")

        result = self.run_check()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.state / "NOTICE.md").exists(), result.stderr)

    def test_tilde_path_expands_against_home(self):
        upstream, clone = self.make_repo_pair()
        (upstream / "a.txt").write_text("2\n")
        git(upstream, "commit", "-q", "-am", "c2")
        home = self.work / "fakehome"
        home.mkdir()
        (home / "clone-link").symlink_to(clone)
        self.conf.write_text("repo\tdemo\t~/clone-link\torigin/main\n")

        result = self.run_check(home=home)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.state / "NOTICE.md").exists(), result.stderr)

    def test_missing_conf_fails(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("설정 파일 없음", result.stderr)

    def test_missing_repo_dir_skipped(self):
        self.conf.write_text(f"repo\tgone\t{self.work}/nope\torigin/main\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("건너뜀", result.stderr)
        self.assertFalse((self.state / "NOTICE.md").exists())

    def test_mirror_copies_identical(self):
        """scripts/ 미러가 core/scripts/ 원본과 갈라지지 않았는지."""
        mirror = KIT / "scripts/skillpack-update-check.sh"
        self.assertEqual(mirror.read_bytes(), SCRIPT.read_bytes())


if __name__ == "__main__":
    unittest.main()
