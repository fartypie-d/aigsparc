#!/usr/bin/env python3
"""task 지시서를 위임 전에 저장소 실물과 대조한다 (읽기 전용 · 표준 라이브러리만).

겨냥하는 것은 한 프로젝트의 5페이즈 위임 기록 재생(2026-09-19)에서 실제로 나온 세 부류뿐이다:
  CMD   지시서가 시키는 명령이 파트 허용 목록(.claude/part-allowed-tools.txt)에 없다      (파트가 거부당해 헛도는 자리)
  PATH  지시서가 가리키는 경로가 없다 · `파일:줄` 의 줄이 파일 길이를 넘는다                (낡은 참조)
  XREF  (--xref) 대상의 짝 테스트·참조 파일이 지시서에 없다                                 (시끄러워 옵션)

못 잡는 것(그래서 「이상 없음」은 「지시서가 옳다」가 아니다): 거짓 전제 · 설계 누락 · 빠진 열거값 —
재생에서 지시서↔코드 불일치 13건 중 10건이 이쪽이고, 코드를 읽고 추론해야 한다. 이 도구는 조언용이며 가드가 아니다.

exit: 0 = 돌았다(발견 유무와 무관) · 2 = 입력을 못 읽었다(「발견 없음」과 구분)
"""
# 출처: 호스트 감독 도구 ~/.claude/supervisor/tools/instruction-check.py (2026-09-19) 를 Phase 19 에서 키트 자산으로 들여왔다.
from __future__ import annotations

import argparse
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ALLOW_FILE = ".claude/part-allowed-tools.txt"
FENCE = re.compile(r"```(?:bash|sh|shell|console)?\n(.*?)```", re.S)
INLINE = re.compile(r"`([^`\n]+)`")
PATH_LIKE = re.compile(r"^(?:\.{0,2}/)?[\w@.\-]+(?:/[\w@.\-\[\]]+)+/?(?::\d+(?:[-,·]\d+)*)?$")
LINE_REF = re.compile(r":(\d+)")
COMMAND_HEADS = ("npm ", "npx ", "node ", "bash ", "sh ", "python3 ", "python ", "git ", "docker ", "make ",
                 "pnpm ", "yarn ", "terraform ", "aws ", "gh ", "curl ", "psql ", "VITEST", "DATABASE", "NODE_")
PROHIBITION = re.compile(r"금지|말 것|마라|하지 않|않는다|쓰지|돌리지|부르지")
ENV_PREFIX = re.compile(r"^(?:[A-Z_][A-Z0-9_]*=\S*\s+)+")
XREF_MAX_LISTED = 8
XREF_MAX_FANOUT = 10
XREF_SKIP_DIRS = ("node_modules/", "dist/", ".next/", "coverage/", "docs/", ".orchestrate/", ".claude/worktrees/")


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    return done.stdout if done.returncode == 0 else ""


def load_allow_patterns(repo: Path) -> list[str] | None:
    path = repo / ALLOW_FILE
    if not path.exists():
        return None
    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"Bash\((.+)\)", line.strip())
        if match:
            patterns.append(match.group(1))
    return patterns


def is_allowed(command: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if pattern.endswith(":*"):
            head = pattern[:-2]
            if command == head or command.startswith(head + " "):
                return True
        elif fnmatch.fnmatchcase(command, pattern):
            return True
    return False


def extract_commands(text: str) -> list[str]:
    fenced = [line.strip() for block in FENCE.findall(text) for line in block.splitlines()]
    inline = [
        span.strip()
        for line in FENCE.sub("", text).splitlines()
        if not PROHIBITION.search(line)  # 「`git stash` 금지」는 시키는 명령이 아니다
        for span in INLINE.findall(line)
        if " " in span.strip()  # 인자 없는 토막(`DATABASE_URL`)은 명령이 아니라 이름이다
    ]
    commands = []
    for candidate in fenced + inline:
        candidate = candidate.lstrip("$ ").strip()
        if any(mark in candidate for mark in ("…", "...", "<", ">")) or candidate.endswith("/"):
            continue  # 자리표시자·줄임표가 든 토막은 실행할 명령이 아니라 설명이다
        if candidate and not candidate.startswith("#") and candidate.startswith(COMMAND_HEADS):
            commands.append(candidate)
    return list(dict.fromkeys(commands))


def check_commands(text: str, patterns: list[str]) -> list[str]:
    findings = []
    for command in extract_commands(text):
        first = re.split(r"\s*(?:&&|\|\||;|\|)\s*", command)[0]
        if is_allowed(first, patterns):
            if first != command:
                findings.append(f"CMD   `{command}` — 첫 명령은 허용되지만 `&&`·파이프로 이은 뒷부분은 따로 판정된다")
            continue
        bare = ENV_PREFIX.sub("", first)
        reason = "환경변수 접두(`VAR=…`) 때문에 접두 매칭이 실패한다" if bare != first and is_allowed(bare, patterns) else "허용 목록에 없다"
        findings.append(f"CMD   `{command}` — {reason}")
    return findings


def extract_paths(text: str) -> list[str]:
    spans = [span.strip() for span in INLINE.findall(text)]
    return list(dict.fromkeys(span for span in spans if PATH_LIKE.match(span) and not span.startswith(("http", "//"))))


def resolve(path_part: str, tracked: set[str]) -> list[str]:
    """지시서는 `admin/startup.ts` 처럼 줄여 쓴다 — 추적 파일의 접미와 맞춰 본다."""
    clean = path_part.lstrip("./")
    if clean in tracked:
        return [clean]
    return sorted(name for name in tracked if name.endswith("/" + clean))


def check_paths(text: str, repo: Path, tracked: set[str]) -> tuple[list[str], list[str]]:
    findings, existing = [], []
    for span in extract_paths(text):
        path_part = span.split(":")[0].rstrip("/")
        if "*" in path_part or "<" in path_part or not Path(path_part).suffix:
            continue  # 글롭·자리표시자·확장자 없는 것(URL 경로·디렉터리)은 보지 않는다
        matches = resolve(path_part, tracked)
        if not matches and (repo / path_part).exists():
            continue  # 추적되지 않지만 디스크에 있다(.claude/skills 등)
        if not matches:
            findings.append(f"PATH  `{span}` — 저장소에 없다 (새로 만들 파일이면 정상 · 기존 파일을 가리킨 것이면 오기)")
            continue
        if len(matches) > 1:
            findings.append(f"PATH  `{span}` — 줄여 쓴 경로가 {len(matches)}개 파일에 맞는다: {', '.join(matches[:4])}")
            continue
        target = repo / matches[0]
        if target.is_file():
            if matches[0] not in existing:
                existing.append(matches[0])
            lines = sum(1 for _ in target.open(encoding="utf-8", errors="replace"))
            beyond = [int(n) for n in LINE_REF.findall(span[len(path_part):]) if int(n) > lines]
            if beyond:
                findings.append(f"PATH  `{span}` — 줄 {beyond} 이 파일 길이({lines}줄)를 넘는다 · 낡은 줄 참조")
    return findings, existing


def sibling_tests(target: str, tracked: set[str]) -> list[str]:
    path = Path(target)
    base = path.name.split(".")[0]
    if ".spec." in path.name or ".test." in path.name:
        return []
    return sorted(
        name for name in tracked
        if Path(name).parent == path.parent and Path(name).name.startswith(base + ".")
        and (".spec." in name or ".test." in name)
    )


def check_cross_references(text: str, repo: Path, targets: list[str], tracked: set[str]) -> list[str]:
    findings = []
    for target in targets:
        missing = [name for name in sibling_tests(target, tracked) if Path(name).name not in text]
        if missing:
            findings.append(f"XREF  `{target}` 의 짝 테스트가 지시서에 없다: {', '.join(missing)} — 대상이 바뀌면 같이 깨질 수 있다")
    for target in targets:
        stem = Path(target).name
        if Path(target).suffix in (".md", ".json", ".txt", ".yml", ".yaml") and "migrations" not in target:
            continue
        needle = Path(target).stem if Path(target).suffix in (".ts", ".tsx", ".js", ".py") else stem
        if len(needle) < 6:
            continue
        hits = [name for name in git(repo, "grep", "-l", "-F", "--", needle).split()
                if name != target and not name.startswith(XREF_SKIP_DIRS)]
        unmentioned = [name for name in hits if Path(name).name not in text and name not in text]
        if len(hits) > XREF_MAX_FANOUT:
            continue  # 허브 파일(schema.ts 류)은 참조가 수십 개라 목록이 신호가 아니다
        if unmentioned:
            shown = ", ".join(unmentioned[:XREF_MAX_LISTED]) + (f" 외 {len(unmentioned) - XREF_MAX_LISTED}" if len(unmentioned) > XREF_MAX_LISTED else "")
            findings.append(f"XREF  `{target}` 을(를) 참조하지만 지시서에 없는 파일 {len(unmentioned)}: {shown}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("instruction", type=Path, help="task 지시서 파일")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="대조할 체크아웃(워크트리) 루트")
    parser.add_argument("--xref", action="store_true",
                        help="대상 파일의 짝 테스트·참조 파일 중 지시서에 없는 것도 나열한다(재생 실측: 9 task 에 25줄, 실제 사건 1건 — 시끄럽다)")
    args = parser.parse_args()

    if not args.instruction.is_file() or not (args.repo / ".git").exists():
        print(f"입력을 못 읽었다: 지시서={args.instruction} 저장소={args.repo}", file=sys.stderr)
        return 2
    text = args.instruction.read_text(encoding="utf-8")
    tracked = set(git(args.repo, "ls-files").split())
    if not tracked:
        print(f"입력을 못 읽었다: `git ls-files` 가 비었다 ({args.repo})", file=sys.stderr)
        return 2

    patterns = load_allow_patterns(args.repo)
    command_findings = check_commands(text, patterns) if patterns is not None else [f"CMD   (건너뜀) {ALLOW_FILE} 이 없다"]
    path_findings, existing = check_paths(text, args.repo, tracked)
    xref_findings = check_cross_references(text, args.repo, existing, tracked) if args.xref else []

    print(f"instruction-check: 명령 {len(extract_commands(text))} · 경로 {len(extract_paths(text))} · 실재 대상 {len(existing)} 개를 대조했다")
    for finding in command_findings + path_findings + xref_findings:
        print("  " + finding)
    if not (command_findings or path_findings or xref_findings):
        print("  발견 없음 — 이 도구가 보는 세 부류(CMD·PATH·XREF)에 한해서다. 전제의 참·거짓은 보지 않는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
