# Task 4: kit-doctor.sh --add-missing (누락만 복사, 기존 파일 불변)

- **에이전트**: `kit-scripts`
- **모델**: heavy (🔴 근접 — 사용자 홈에 **쓰는** 유일한 경로. 덮어쓰면 데이터 손실)
- **대상 파일**: `core/scripts/kit-doctor.sh` (Task 2 산출물에 모드 추가)
- **선행**: Task 2, Task 3
- **목표**: `kit-doctor.sh --add-missing` 이 매니페스트 항목 중 **부재한 것만** 복사해 채우고,
  이미 존재하는 파일은 내용이 다르더라도 **절대 건드리지 않는다**. drift 는 보고만 하고
  갱신 방법(`./install.sh` 재실행)을 안내한다.
- **재사용**
  - 그대로 재사용 Task 2 의 매니페스트 순회 로직 — **복사용 두 번째 순회를 새로 만들지 말 것**
    (같은 파서를 함수로 공유한다).
  - 그대로 재사용 `lib/stamp.sh` 의 **정책**: "기존 파일은 절대 덮지 않는다"(`lib/stamp.sh:18`).
    같은 시맨틱을 따르되 `stamp_copy` 자체는 프로젝트 스캐폴드용이라 호출하지 않는다
    (대상 트리가 `$HOME` 전역 자산이라 다르다) — 이 판단 근거를 스크립트 주석에 한 줄로 남길 것.
  - 없음 — `grep -rn "add-missing" .` 결과 부재.
- **실패 테스트**: `tests/test_kit_doctor.py::test_add_missing_creates_absent_assets`,
  `::test_add_missing_never_overwrites_existing`, `::test_add_missing_does_not_touch_drifted_files`,
  그리고 **경로 봉쇄 3건** `DoctorPathContainmentTest::test_traversal_in_manifest_dst_is_refused`,
  `::test_traversal_in_manifest_src_is_refused`,
  `::test_add_missing_does_not_write_through_dangling_symlink`
  → **먼저 실행해 실패를 확인한 뒤** 구현할 것.

## 보안 선행 조건 (Task 2 리뷰에서 security-reviewer 가 재현·지정 — 미충족 시 반려)

**복사 기능을 붙이기 전에** 이걸 먼저 고쳐야 한다. 그러지 않으면 지금의 읽기 전용
정보 노출(🟠)이 **임의 파일 쓰기(🔴)** 로 승격된다.

| 지적 | 재현된 현상 | 요구 |
|---|---|---|
| 경로 이탈 (CWE-22) | 매니페스트 `dst=../<파일>` 이 `$HOME` 밖 파일을 열어 `DRIFT` 로 판정됐다. `src` 도 동일 | `src`·`dst` 의 `..` 세그먼트와 절대경로를 **거부**하고 그 행을 `FAIL` 로 보고. 해석된 경로가 `KIT_DIR`/`HOME_DIR` 아래인지 봉쇄 확인 |
| 심링크 추종 (CWE-59) | `[ -L ]` 검사가 없다. **끊어진 심링크**는 `[ -e ]` 가 false 라서 복사가 심링크를 타고 홈 밖에 쓴다 | 복사 전 `[ -L "$dst" ]` 를 확인하고, 심링크면 **쓰지 않고** `WARN` 으로 보고 |

이 조건은 프로즈가 아니라 위 동결 테스트 3건으로 강제된다 (현재 전부 RED, 재현 증거 있음).
- **필독 스킬**: `karpathy-guidelines`
- **필수 규칙**
  - **덮어쓰기 절대 금지.** `cp` 전에 반드시 `[ -e "$dst" ]` 로 존재를 확인하고, 존재하면 skip 후
    `DRIFT` 또는 `OK` 로만 보고한다. `cp -f`·`rm -rf` 를 쓰지 말 것.
  - `seed` 모드 항목(`secrets.env`)은 부재 시 `secrets.env.example` 을 복사하고 **`chmod 600`** 을
    적용한다 (`install.sh:1569` 와 동일 — 권한 누락은 자격증명 노출이다).
  - `tree` 모드는 dst 하위 **부재한 최상위 항목만** 복사한다 (기존 항목 통째 삭제·재복사 금지).
  - `--add-missing` 없이 실행하면 여전히 **읽기 전용**이어야 한다 (기본 동작 불변).
  - 복사한 항목은 `ADDED <범주>: <대상>` 줄로 보고하고 요약에 `added=<n>` 을 추가한다.
  - 복사 실패(권한 등)는 조용히 넘기지 말고 `FAIL` 로 보고하고 exit 1 에 반영한다.
  - bash 3.2 호환. `tests/` 수정 금지. 대상 파일 외 수정 금지, `git commit` 금지.
- **완료 조건**
  1. `python3 -m unittest discover -s tests -v` — 전부 통과.
  2. `bash -n core/scripts/kit-doctor.sh` 통과.
  3. **변이 검증 2종** (`.orchestrate/mut10-4/` 에 **저장소 전체**를 복사한 뒤 그 사본에서 수행.
     `/tmp` 금지 — PITFALLS 15. 스크립트만 복사하면 테스트가 원본을 참조해 변이가 무효다):
     - 변이 A: "존재 확인 분기 제거"(=덮어쓰게 만듦) → `test_add_missing_never_overwrites_existing`
       이 **실패**해야 한다.
     - 변이 B: "경로 봉쇄·심링크 검사 제거" → `test_add_missing_does_not_write_under_symlinked_parent`
       또는 `test_add_missing_does_not_write_through_dangling_symlink` 가 **실패**해야 한다.
       (이 두 테스트는 복사 기능이 없던 시점에는 공허하게 통과했다 — 변이로 살아 있음을 증명할 것.)
     - 변이 전/후 출력을 모두 보고에 첨부한다.

## 재검증 리뷰에서 이관된 항목 2건 (2026-08-17, silent-failure-hunter — SIGN OFF 조건)

1. **🟠 `--add-missing` 조용한 no-op 제거** — 지금 이 플래그는 파싱만 되고 아무 일도 하지 않으며
   사용자에게 그 사실도 알리지 않는다. 이 task 가 실제 복사를 구현하면 해소된다.
   **안내 문구만 붙여 갈음하지 말 것** — 동결 테스트가 실제 복사를 요구한다.
2. **🟡 `parent_is_within_root` 의 "부모 없으면 통과" 폴백 강화** — 읽기 전용일 때는 무해하다
   (부모가 없으면 자식도 없다). 그러나 `mkdir -p` 로 부모를 **만들면서** 쓰는 순간
   심링크 우회로가 된다. 복사 경로에서는 **생성될 물리 경로를 미리 계산해** 봉쇄 범위 안인지
   확인할 것 (`$HOME/.config` 자체가 홈 밖을 향하는 심링크인 경우가 재현 시나리오다).
