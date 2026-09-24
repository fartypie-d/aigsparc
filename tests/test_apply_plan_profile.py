"""apply-plan-profile.sh 테스트 — 가짜 agents 디렉터리·settings 로 프로파일 적용을 검증."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


KIT = Path(__file__).resolve().parents[1]
APPLY = KIT / "adapters/claude/global/apply-plan-profile.sh"

AGENTS = {
    "planner.md": "opus",
    "code-reviewer.md": "claude-sonnet-5",
    "security-reviewer.md": "claude-sonnet-5",
    "task-orchestrator.md": "sonnet",
    "doc-updater.md": "haiku",
    "build-error-resolver.md": "claude-sonnet-5",
    "brand-new-agent.md": "claude-sonnet-5",
}


class ApplyPlanProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.agents = Path(self.tmp.name) / "agents"
        self.agents.mkdir()
        for name, model in AGENTS.items():
            (self.agents / name).write_text(
                f"---\nname: {name[:-3]}\nmodel: {model}\ndescription: t\n---\n\n본문\n"
            )
        self.settings = Path(self.tmp.name) / "settings.json"
        self.settings.write_text(json.dumps({"model": "claude-fable-5[1m]", "theme": "auto"}))

    def apply(self, profile, extra_env=None):
        env = None
        if extra_env:
            env = {**os.environ, **extra_env}
        return subprocess.run(
            ["bash", str(APPLY), profile, "--agents-dir", str(self.agents), "--settings", str(self.settings)],
            capture_output=True,
            text=True,
            env=env,
        )

    def model_of(self, name):
        for line in (self.agents / name).read_text().splitlines():
            if line.startswith("model:"):
                return line.split(":", 1)[1].strip()
        return None

    def settings_json(self):
        return json.loads(self.settings.read_text())

    def test_pro_downgrades_workers_but_not_reviewers(self):
        result = self.apply("pro")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.model_of("doc-updater.md"), "claude-haiku-4-5-20251001")
        self.assertEqual(self.model_of("build-error-resolver.md"), "claude-haiku-4-5-20251001")
        self.assertEqual(self.model_of("code-reviewer.md"), "claude-sonnet-5")
        self.assertEqual(self.model_of("security-reviewer.md"), "claude-sonnet-5")

    def test_pro_keeps_design_on_opus(self):
        self.apply("pro")
        self.assertEqual(self.model_of("planner.md"), "claude-opus-5")

    def test_task_orchestrator_is_quality_class(self):
        self.apply("pro")
        self.assertEqual(self.model_of("task-orchestrator.md"), "claude-sonnet-5")

    def test_unlisted_agent_defaults_to_worker(self):
        self.apply("pro")
        self.assertEqual(self.model_of("brand-new-agent.md"), "claude-haiku-4-5-20251001")

    def test_pro_sets_token_env(self):
        self.apply("pro")
        env = self.settings_json()["env"]
        self.assertEqual(env["MAX_THINKING_TOKENS"], "10000")
        self.assertEqual(env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"], "75")

    def test_pro_sets_main_model_to_sonnet(self):
        self.apply("pro")
        self.assertEqual(self.settings_json()["model"], "sonnet")

    def test_token_env_is_identical_across_all_profiles(self):
        for profile in ("pro", "max5", "max20"):
            result = self.apply(profile)
            self.assertEqual(result.returncode, 0, result.stderr)
            env = self.settings_json()["env"]
            self.assertEqual(env["MAX_THINKING_TOKENS"], "10000", profile)
            self.assertEqual(env["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"], "75", profile)

    def test_max20_does_not_touch_main_model(self):
        self.apply("pro")
        result = self.apply("max20")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.settings_json()["model"], "sonnet")

    def test_max20_restores_workers_to_sonnet(self):
        self.apply("pro")
        self.apply("max20")
        self.assertEqual(self.model_of("doc-updater.md"), "claude-sonnet-5")
        self.assertEqual(self.model_of("code-reviewer.md"), "claude-sonnet-5")

    def test_never_writes_subagent_model_env(self):
        for profile in ("pro", "max5", "max20"):
            self.apply(profile)
            self.assertNotIn("CLAUDE_CODE_SUBAGENT_MODEL", json.dumps(self.settings_json()))

    def test_is_idempotent(self):
        self.apply("pro")
        first = (self.agents / "doc-updater.md").read_text()
        self.apply("pro")
        self.assertEqual((self.agents / "doc-updater.md").read_text(), first)

    def test_profile_table_uses_explicit_model_ids(self):
        """별칭(`sonnet`)은 이전 세대로 해석돼 서브에이전트만 조용히 강등된다 — 표에 다시 들어오지 못하게 막는다."""
        table = json.loads((KIT / "adapters/claude/global/plan-profiles.json").read_text())
        for profile, spec in table["profiles"].items():
            for role, model in spec["agents"].items():
                self.assertTrue(
                    model.startswith("claude-"),
                    f"{profile}.{role} 이 별칭 '{model}' 을 쓴다 — 명시 모델 ID 를 쓸 것",
                )

    def test_unknown_profile_exits_64(self):
        result = self.apply("nosuchplan")
        self.assertEqual(result.returncode, 64)

    def test_corrupt_roles_exits_66(self):
        roles = Path(self.tmp.name) / "agent-roles.json"
        roles.write_text('{"design": [')

        result = self.apply("pro", {"APPLY_PLAN_PROFILE_ROLES": str(roles)})

        self.assertEqual(result.returncode, 66)
        self.assertIn(f"역할표 JSON 손상: {roles}", result.stderr)

    def test_corrupt_profiles_exits_66(self):
        profiles = Path(self.tmp.name) / "plan-profiles.json"
        profiles.write_text('{"profiles": [')

        result = self.apply("pro", {"APPLY_PLAN_PROFILE_PROFILES": str(profiles)})

        self.assertEqual(result.returncode, 66)
        self.assertIn(f"프로파일표 JSON 손상: {profiles}", result.stderr)

    def test_agent_without_model_is_skipped_without_backup(self):
        self.assertEqual(self.apply("pro").returncode, 0)
        agent = self.agents / "no-model.md"
        original = "---\nname: no-model\ndescription: t\n---\n\n본문\n"
        agent.write_text(original)

        first = self.apply("pro")
        second = self.apply("pro")

        for result in (first, second):
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("에이전트: 0 개 변경", result.stdout)
            self.assertIn(f"주의: {agent} 에 model: 필드 없음 — 건너뜀", result.stderr)
        self.assertEqual(agent.read_text(), original)
        self.assertEqual(list(self.agents.glob("no-model.md.bak-*")), [])

    def test_other_settings_keys_preserved(self):
        self.apply("pro")
        self.assertEqual(self.settings_json()["theme"], "auto")


if __name__ == "__main__":
    unittest.main()
