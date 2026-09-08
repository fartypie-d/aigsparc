"""model-doctor.sh 테스트 — 임시 가짜 opencode 바이너리로 외부 호출을 격리한다."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
DOCTOR = KIT / "core/opencode/model-doctor.sh"

REGISTERED = "qwencloud/qwen3.7-plus\nqwencloud/qwen3.7-max\nopenai/gpt-5.6-luna\n"


class DoctorHarness(unittest.TestCase):
    """공용 픽스처 — 가짜 opencode·curl 로 외부 호출을 격리한다. 테스트는 하위 클래스에."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.policy = self.work / "policy.json"
        self.secrets = self.work / "secrets.env"
        self.opencode = self.work / "opencode"
        self.opencode.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$1\" in\n"
            "  models) printf '%s' \"${FAKE_MODELS_OUT-}\"; exit \"${FAKE_MODELS_EXIT-0}\" ;;\n"
            "  auth) printf '%s' \"${FAKE_AUTH_OUT-}\"; exit \"${FAKE_AUTH_EXIT-0}\" ;;\n"
            "  run) printf '%s' \"${FAKE_RUN_OUT-}\"; exit \"${FAKE_RUN_EXIT-0}\" ;;\n"
            "  *) exit 64 ;;\n"
            "esac\n"
        )
        self.opencode.chmod(0o755)
        # serve 대조는 실제 `$HOME/.config/opencode/serve.env` 를 기본값으로 쓴다. 테스트는
        # 반드시 --serve-env 로 임시 경로를 주입해 개발 머신의 상주 serve 에 붙지 않게 한다.
        self.serve_env = self.work / "serve.env"
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.curl_argv = self.work / "curl-argv.txt"
        self.curl_stdin = self.work / "curl-stdin.txt"
        curl = self.bin / "curl"
        curl.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$*\" > \"$FAKE_CURL_ARGV\"\n"
            "cat > \"$FAKE_CURL_STDIN\"\n"
            "printf '%s\\n%s' \"${FAKE_CURL_BODY-}\" \"${FAKE_CURL_CODE-200}\"\n"
            "exit \"${FAKE_CURL_EXIT-0}\"\n"
        )
        curl.chmod(0o755)

    def write_serve_env(self, password="serve-secret-pw", port="4096"):
        self.serve_env.write_text(
            "OPENCODE_SERVE_PORT=%s\nOPENCODE_SERVER_PASSWORD=%s\n" % (port, password)
        )

    @staticmethod
    def providers_json(*models):
        by_provider = {}
        for model in models:
            provider, name = model.split("/", 1)
            by_provider.setdefault(provider, {})[name] = {}
        return json.dumps(
            {"providers": [{"id": p, "models": m} for p, m in by_provider.items()]}
        )

    def write_policy(self, default, heavy):
        self.policy.write_text(json.dumps({"tiers": {"default": default, "heavy": heavy}}))

    def run_doctor(self, *args, env=None):
        command = [
            "bash", str(DOCTOR), "--policy", str(self.policy),
            "--opencode-bin", str(self.opencode), "--secrets", str(self.secrets),
            "--serve-env", str(self.serve_env),
            *args,
        ]
        run_env = os.environ.copy()
        run_env.update({
            "FAKE_MODELS_OUT": REGISTERED, "FAKE_AUTH_OUT": "OpenAI oauth\n",
            "FAKE_CURL_ARGV": str(self.curl_argv), "FAKE_CURL_STDIN": str(self.curl_stdin),
            "PATH": "%s:%s" % (self.bin, run_env.get("PATH", "")),
        })
        if env:
            run_env.update(env)
        # stdin 을 막아 둔다 — 가짜 curl 이 `--config -` 없이 호출되면(가드 변이) 입력을
        # 기다리며 행에 빠진다. 행이 아니라 실패로 드러나야 변이 검증이 성립한다.
        return subprocess.run(command, capture_output=True, text=True, env=run_env,
                              stdin=subprocess.DEVNULL)

class DoctorTest(DoctorHarness):
    def test_all_entries_registered_passes(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)

    def test_unregistered_entry_is_reported(self):
        self.write_policy(["qwencloud/qwen3.7-plus", "qwencloud/typo-model"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("qwencloud/typo-model", result.stdout)
        self.assertIn("MISSING", result.stdout)

    def test_tier_with_no_valid_entry_fails(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["xai/not-registered"])
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 1)
        self.assertIn("heavy", result.stdout)

    def test_missing_policy_file_exits_66(self):
        result = subprocess.run(
            ["bash", str(DOCTOR), "--policy", str(self.policy) + ".nope",
             "--opencode-bin", str(self.opencode), "--skip-smoke"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 66)

    def test_empty_tiers_object_fails(self):
        self.policy.write_text('{"tiers": {}}')
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 1)
        self.assertIn("정책에 tier 가 하나도 없다", result.stderr)

    def test_missing_tiers_fails(self):
        self.policy.write_text("{}")
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 1)
        self.assertIn("정책에 tier 가 하나도 없다", result.stderr)

    def test_scalar_tiers_exits_66(self):
        for tiers in ("oops", 5):
            with self.subTest(tiers=tiers):
                self.policy.write_text(json.dumps({"tiers": tiers}))
                result = self.run_doctor("--skip-smoke")
                self.assertEqual(result.returncode, 66, result.stdout + result.stderr)
                self.assertIn("객체가 아니다", result.stderr)

    def test_invalid_policy_json_exits_66(self):
        self.policy.write_text("{")
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 66)
        self.assertIn("정책 JSON 손상", result.stderr)

    def test_models_command_failure_rejects_partial_output(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke", env={"FAKE_MODELS_EXIT": "1"})
        self.assertEqual(result.returncode, 1)
        self.assertIn("opencode models 실패 (exit 1)", result.stderr)

    def test_auth_command_failure_is_reported_separately(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke", env={"FAKE_AUTH_EXIT": "7"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("auth list 실행 실패 (exit 7)", result.stderr)

    def test_missing_key_credential_is_reported(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke")
        self.assertIn("인증 누락: qwen (QWEN_API_KEY 미설정)", result.stdout)

    def test_skip_smoke_reports_that_real_calls_were_not_verified(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("스모크 생략됨 (--skip-smoke)", result.stdout)
        self.assertIn("스모크 생략", result.stdout)

    def test_secret_values_are_never_reported(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        self.secrets.write_text("QWEN_API_KEY=sk-FAKE123\nEMPTY_KEY=\n")
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("인증 OK: qwen (key)", result.stdout)
        self.assertNotIn("sk-FAKE123", result.stdout + result.stderr)

    def test_smoke_success_is_reported(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("스모크 통과", result.stdout)

    def test_smoke_failure_includes_exit_code(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor(env={"FAKE_RUN_EXIT": "9"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("스모크 실패 (exit 9)", result.stdout)


class ServeDriftTest(DoctorHarness):
    """상주 serve 대조 — 설정 파일이 맞아도 낡은 serve 가 위임을 죽이는 경우를 잡는다."""

    def test_missing_serve_env_is_skipped(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("건너뜀 — serve.env 없음", result.stdout)

    def test_serve_agreement_reports_ok(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        self.write_serve_env()
        body = self.providers_json("qwencloud/qwen3.7-plus", "qwencloud/qwen3.7-max")
        result = self.run_doctor("--skip-smoke", env={"FAKE_CURL_BODY": body})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("모든 tier 가 상주 serve 에서도 유효하다", result.stdout)

    def test_model_unknown_to_serve_is_reported_stale(self):
        """파일에는 있고 serve 는 모르는 모델 — tier 가 살아 있어도 경고해야 한다."""
        self.write_policy(["qwencloud/qwen3.7-plus", "openai/gpt-5.6-luna"], ["qwencloud/qwen3.7-max"])
        self.write_serve_env()
        body = self.providers_json("qwencloud/qwen3.7-plus", "qwencloud/qwen3.7-max")
        result = self.run_doctor("--skip-smoke", env={"FAKE_CURL_BODY": body})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("STALE   openai/gpt-5.6-luna", result.stdout)
        self.assertIn("폴백 후보에서 사실상 빠져 있다", result.stdout)

    def test_tier_invalid_on_serve_exits_1_with_restart_hint(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["openai/gpt-5.6-luna"])
        self.write_serve_env()
        body = self.providers_json("qwencloud/qwen3.7-plus")
        result = self.run_doctor("--skip-smoke", env={"FAKE_CURL_BODY": body})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("상주 serve 기준 사용 불가 tier: heavy", result.stdout)
        self.assertIn("opencode-serve-ctl.sh stop", result.stdout)

    def test_serve_not_running_is_skipped_not_failed(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        self.write_serve_env()
        result = self.run_doctor("--skip-smoke", env={"FAKE_CURL_EXIT": "7"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("serve 미기동", result.stdout)

    def test_auth_mismatch_is_not_reported_as_not_running(self):
        """401 을 '미기동' 으로 뭉뚱그리면 이 진단이 노리는 드리프트를 스스로 감춘다."""
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        self.write_serve_env()
        result = self.run_doctor("--skip-smoke", env={"FAKE_CURL_CODE": "401", "FAKE_CURL_BODY": ""})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("serve 인증 불일치 (HTTP 401)", result.stdout)
        self.assertNotIn("serve 미기동", result.stdout)

    def test_unexpected_response_shape_is_reported(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        self.write_serve_env()
        result = self.run_doctor("--skip-smoke", env={"FAKE_CURL_BODY": '{"providers":[]}'})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("모델을 하나도 보고하지 않았다", result.stdout)

    def test_server_password_never_reaches_the_command_line(self):
        """비밀번호는 stdin 설정으로만 간다 — 인자로 실으면 ps 로 읽힌다 (공용 머신)."""
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        self.write_serve_env(password="serve-secret-pw")
        body = self.providers_json("qwencloud/qwen3.7-plus", "qwencloud/qwen3.7-max")
        result = self.run_doctor("--skip-smoke", env={"FAKE_CURL_BODY": body})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("serve-secret-pw", self.curl_argv.read_text())
        self.assertIn("serve-secret-pw", self.curl_stdin.read_text())
        self.assertNotIn("serve-secret-pw", result.stdout + result.stderr)

    def test_password_with_quote_is_refused_without_printing_it(self):
        self.write_policy(["qwencloud/qwen3.7-plus"], ["qwencloud/qwen3.7-max"])
        self.write_serve_env(password='bad"pw')
        result = self.run_doctor("--skip-smoke")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("따옴표·역슬래시·개행", result.stdout)
        self.assertNotIn('bad"pw', result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
