#!/usr/bin/env python3
"""여러 저장소에 복제된 스캐폴드 파일이 서로 얼마나 갈라졌는지 보여 준다 (읽기 전용 · 표준 라이브러리만 · 외부 전송 없음).

왜: 2026-09-19~20 에 `phase-tools.py` 의 같은 결함(위치 해석 앵커)을 여러 저장소가 각자 다른 페이즈로 따로 고쳤고,
마지막 저장소는 아무도 모르는 채 열려 있었다. 복제본은 조용히 갈라진다 — 이 표가 그 「조용히」를 없앤다.

대상 저장소: 기본은 오케스트레이션 레지스트리(`<state>/registry/*.json` 의 `root`, `<state>` 는 phase-tools 의
`state_dir()` 과 같은 규칙 — `ORCH_STATE_DIR` 이 있으면 그것, 없으면 `~/.local/state/orchestrate`)에 등록된 git 저장소 전부다.
`--repos <이름|절대경로>...` 를 주면 레지스트리 대신 그것만 본다(이름은 `--home` 아래 디렉터리).

보는 것:
  1) min(3, 저장소 수) 곳 이상에 같은 이름으로 있는 스캐폴드 파일의 판 수와 최저 유사도
  2) 파이썬 파일은 최상위 함수 단위로: 전부 동일 / 갈라짐 / **일부 저장소에만 있음 또는 혼자만 다름**(= 수선이 안 옮겨간 자리 후보)

exit: 0 = 돌았다 · 2 = 저장소를 못 읽었다(레지스트리 없음 · 비교할 저장소 2개 미만 포함). 가드가 아니다 — 출력은 사람이 읽는다.
"""
# 출처: 호스트 감독 도구 ~/.claude/supervisor/tools/scaffold-drift.py (2026-09-20) 를 Phase 19 에서 키트 자산으로 들여왔다.
#       호스트 고정 저장소 목록(DEFAULT_REPOS)은 레지스트리 스캔으로 바꿨고 `--repos` 는 그대로 둔다.
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

SCOPES = ("scripts", ".claude", ".opencode")
SKIP_PARTS = (".claude/worktrees/", ".claude/rules/", "/fixtures/", "/__pycache__/")
MIN_REPOS = 3
MIN_COMPARABLE = 2


def registry_dir() -> Path:
    """phase-tools 의 state_dir() 과 같은 규칙: ORCH_STATE_DIR 이 있으면 그것, 없으면 ~/.local/state/orchestrate.

    XDG_STATE_HOME 은 보지 않는다 — phase-tools 가 안 보므로 여기서 보면 둘이 다른 레지스트리를 읽는다
    (PR #21 리뷰 MEDIUM, 2026-09-23). 디렉터리를 만들지는 않는다(읽기 전용 도구).
    """
    base = Path(os.environ.get("ORCH_STATE_DIR", str(Path.home() / ".local/state/orchestrate")))
    return base / "registry"


def registry_repos(registry: Path) -> list[str]:
    """레지스트리 항목 중 `root` 가 실재하는 git 저장소인 것만 절대 경로로 돌려준다 (이름순)."""
    roots = []
    for path in sorted(registry.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        root = data.get("root") if isinstance(data, dict) else None
        if isinstance(root, str) and root and (Path(root) / ".git").exists():
            roots.append(root)
    return roots


def tracked(repo: Path) -> list[str]:
    done = subprocess.run(["git", "-C", str(repo), "ls-files", *SCOPES], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise SystemExit(f"저장소를 못 읽었다: {repo} — {done.stderr.strip()[:120]}")
    return [name for name in done.stdout.split("\n") if name and not any(part in name for part in SKIP_PARTS)]


def digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def lowest_similarity(texts: list[str]) -> float:
    pairs = [(a, b) for i, a in enumerate(texts) for b in texts[i + 1:]]
    return min(difflib.SequenceMatcher(None, a.splitlines(), b.splitlines()).ratio() for a, b in pairs) if pairs else 1.0


def top_level_functions(source: str) -> dict[str, str]:
    lines = source.splitlines()
    tree = ast.parse(source)
    return {
        node.name: "\n".join(lines[node.lineno - 1: node.end_lineno])
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def file_table(home: Path, repos: list[str]) -> dict[str, dict[str, str]]:
    """repo 항목이 절대 경로면 그대로, 이름이면 home 아래로 본다 (pathlib 결합 규칙)."""
    by_name: dict[str, dict[str, str]] = defaultdict(dict)
    for repo in repos:
        for name in tracked(home / repo):
            by_name[Path(name).name][repo] = name
    threshold = min(MIN_REPOS, len(repos))
    return {name: locs for name, locs in by_name.items() if len(locs) >= threshold}


def report_files(home: Path, shared: dict[str, dict[str, str]]) -> list[str]:
    rows = []
    for name, locs in shared.items():
        texts = [(home / repo / rel).read_text(encoding="utf-8", errors="replace") for repo, rel in locs.items()]
        versions = len({digest(text) for text in texts})
        rows.append((lowest_similarity(texts), name, len(locs), versions, max(text.count("\n") for text in texts)))
    lines = [f"{'파일':34} 저장소  판   최대줄  최저 유사도"]
    for similarity, name, count, versions, longest in sorted(rows):
        flag = "" if versions == 1 else "  ← 갈라짐"
        lines.append(f"{name:34} {count:4} {versions:4} {longest:7}    {similarity:.2f}{flag}")
    identical = sum(1 for row in rows if row[3] == 1)
    lines.append(f"(공유 파일 {len(rows)}개 · 전부 동일 {identical} · 갈라진 것 {len(rows) - identical})")
    return lines


def report_functions(home: Path, name: str, locs: dict[str, str]) -> list[str]:
    per_repo = {}
    for repo, rel in locs.items():
        try:
            per_repo[repo] = top_level_functions((home / repo / rel).read_text(encoding="utf-8"))
        except SyntaxError as err:
            return [f"  {repo}/{rel}: 구문 오류로 함수 단위 비교 불가 — {err}"]
    names = sorted(set().union(*[set(funcs) for funcs in per_repo.values()]))
    short = {repo: Path(repo).name for repo in per_repo}
    same = drifted = 0
    suspects = []
    for func in names:
        have = [repo for repo in per_repo if func in per_repo[repo]]
        if len(have) < len(per_repo):
            suspects.append(f"  {func:30} 일부에만 있음: {', '.join(short[r] for r in have)}")
            continue
        groups: dict[str, list[str]] = defaultdict(list)
        for repo in per_repo:
            groups[digest(per_repo[repo][func])].append(repo)
        if len(groups) == 1:
            same += 1
            continue
        drifted += 1
        loners = [members[0] for members in groups.values() if len(members) == 1]
        majority = max(groups.values(), key=len)
        if len(majority) >= len(per_repo) - 1 and len(loners) == 1:
            suspects.append(f"  {func:30} {short[loners[0]]} 만 다르다 (나머지 {len(majority)}곳은 동일)")
    lines = [f"\n[{name}] 최상위 함수 {len(names)} · 전부 동일 {same} · 갈라짐 {drifted} · 수선이 안 옮겨간 자리 후보 {len(suspects)}"]
    return lines + suspects


def select_repos(args: argparse.Namespace) -> list[str]:
    """--repos 가 있으면 그대로, 없으면 레지스트리를 스캔한다. 못 읽거나 2개 미만이면 LookupError."""
    if args.repos:
        missing = [repo for repo in args.repos if not (args.home / repo / ".git").exists()]
        if missing:
            raise LookupError(f"저장소를 못 읽었다: {missing}")
        repos = list(args.repos)
        origin = "--repos"
    else:
        registry = registry_dir()
        if not registry.is_dir():
            raise LookupError(f"레지스트리가 없다: {registry} — 비교할 저장소를 `--repos` 로 주거나 phase-tools init 으로 등록하라")
        repos = registry_repos(registry)
        origin = f"레지스트리 {registry}"
    if len(repos) < MIN_COMPARABLE:
        raise LookupError(f"비교할 저장소가 {MIN_COMPARABLE}개 미만이다 ({origin}: {repos}) — 드리프트는 둘 이상이어야 잴 수 있다")
    return repos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", type=Path, default=Path.home(), help="--repos 이름을 찾을 상위 디렉터리")
    parser.add_argument("--repos", nargs="+", default=None, help="비교할 저장소 이름(또는 절대 경로). 생략하면 레지스트리 스캔")
    args = parser.parse_args()

    try:
        repos = select_repos(args)
    except LookupError as unreadable:
        print(unreadable, file=sys.stderr)
        return 2
    print(f"저장소 {len(repos)}: {', '.join(Path(repo).name for repo in repos)}")
    shared = file_table(args.home, repos)
    print("\n".join(report_files(args.home, shared)))
    for name, locs in sorted(shared.items()):
        if name.endswith(".py"):
            print("\n".join(report_functions(args.home, name, locs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
