# Task 5: README·WORKFLOW 문서 반영

- **에이전트**: `kit-docs`
- **모델**: (생략 = default)
- **대상 파일**: `README.md`, `README.ko.md`, `docs/WORKFLOW.md`, `docs/WORKFLOW.ko.md`
- **선행**: Task 2, Task 3, Task 4 (구현 확정 후 문서화 — 먼저 쓰면 실제 플래그와 어긋난다)
- **목표**: 사용자가 "설치가 온전한지 어떻게 확인하나"·"킷을 업데이트했는데 뭘 다시 돌려야 하나"에
  문서만 보고 답할 수 있게 한다.
- **재사용**: 개선 후 재사용 `README.md`·`README.ko.md` 의 기존 `model-doctor.sh` 언급 절
  (README.md:108·147, README.ko.md:94·129 — 호출부 4곳). **새 절을 중복 신설하지 말고**
  기존 진단 서술 근처에 편입해 "무엇을 어느 도구가 보는가"를 한 표로 정리할 것.
- **실패 테스트**: 작성 불가 — 문서(markdown) 단독 수정.
  **대체 검증**(로스터 "대체 검증" 표): ① 문서에 등장하는 모든 경로·플래그가 실재하는지
  `ls`·`grep` 으로 확인 ② 영/국문 문서의 서술 항목 수·순서가 일치하는지 대조.
- **필독 스킬**: `karpathy-guidelines`
- **필수 규칙**
  - 실제 구현된 플래그만 쓴다 — 문서 작성 전 `bash core/scripts/kit-doctor.sh --help` 또는
    스크립트 헤더를 읽어 **실측한 플래그명**만 기재할 것 (추측 금지).
  - 진단 도구 3종의 **역할 경계**를 명시한다: `kit-doctor.sh`(도구·전역 자산 존재·drift) /
    `model-doctor.sh`(모델 정책·체인·인증) / `hook-selfcheck.sh`(프로젝트 훅 생존).
  - `--add-missing` 은 **누락만 채우고 기존 파일을 덮지 않는다**는 점, drift 갱신은
    `./install.sh` 재실행이라는 점을 명시한다 (오해 시 사용자가 데이터 손실을 기대한다).
  - 영문·국문을 **동시에** 갱신한다 (한쪽만 고치면 리뷰 반려).
  - 국문은 조사 띄어쓰기를 확인할 것 (Phase 9 리뷰 🟡 재발 방지).
  - 이력 문서(`docs/phases/`·`docs/specs/`·`docs/plans/`)는 수정 금지.
  - 대상 파일 외 수정 금지, `git commit` 금지.
- **완료 조건**
  1. `grep -n "kit-doctor" README.md README.ko.md docs/WORKFLOW.md docs/WORKFLOW.ko.md` — 4파일 모두 언급.
  2. 문서에 기재한 모든 플래그가 `core/scripts/kit-doctor.sh` 에 실재함을 `grep` 출력으로 첨부.
  3. `python3 -m unittest discover -s tests -v` 회귀 0건 (문서 변경이지만 `test_rebrand.py` 가
     README 어서션을 갖고 있다 — 반드시 실행).
