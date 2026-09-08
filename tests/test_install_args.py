"""install.sh 인자 파싱 테스트 — INSTALL_PARSE_ONLY=1 로 부작용 없이 파싱 결과만 확인."""
import unittest

from _install_helpers import KIT, parse_only


class InstallArgsTest(unittest.TestCase):
    def test_explicit_harness_flags(self):
        r = parse_only("--claude", "--codex")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("HARNESSES=claude codex", r.stdout)

    def test_providers_csv_parsed(self):
        r = parse_only("--claude", "--providers=qwen,openai")
        self.assertIn("PROVIDERS=qwen,openai", r.stdout)

    def test_containers_parsed(self):
        r = parse_only("--claude", "--containers=browser")
        self.assertIn("CONTAINERS=browser", r.stdout)

    def test_ecc_languages_collected(self):
        r = parse_only("--claude", "typescript", "python")
        self.assertIn("ECC_LANGS=typescript python", r.stdout)

    def test_ecc_language_arguments_are_preserved_as_array(self):
        source = (KIT / "install.sh").read_text()
        self.assertIn('ECC_LANGS[${#ECC_LANGS[@]}]="$_ecc_lang_arg"', source)
        self.assertIn('./install.sh "${ECC_LANGS[@]}"', source)

    def test_noninteractive_provider_prompt_is_skipped(self):
        source = (KIT / "install.sh").read_text()
        self.assertIn('if [ -t 0 ]; then', source)
        self.assertIn('비대화형 실행 — --providers= 로 명시하거나 나중에 gen-policy.sh 를 직접 실행할 것', source)

    def test_plan_option_is_accepted(self):
        r = parse_only("--claude", "--plan=max20", "typescript")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("PLAN=max20", r.stdout)

    def test_unknown_flag_exits_64(self):
        r = parse_only("--nosuchflag")
        self.assertEqual(r.returncode, 64)

    def test_doctor_flag_is_parsed(self):
        # 파싱만 확인한다. 실제 dispatch·리포트는 tests/test_kit_doctor.py 가 실행으로 검증한다
        # (INSTALL_PARSE_ONLY 로 동작을 검증하면 항상 참인 테스트가 된다 — PITFALLS 1).
        r = parse_only("--claude", "--doctor")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("DOCTOR=1", r.stdout)

    def test_doctor_flag_defaults_to_off(self):
        r = parse_only("--claude")
        self.assertIn("DOCTOR=0", r.stdout)


if __name__ == "__main__":
    unittest.main()
