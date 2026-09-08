#!/usr/bin/env python3
"""세션 비용 집계 — ~/.claude/projects/<프로젝트 슬러그>/*.jsonl 의 usage 합산.

사용: python3 scripts/session-cost.py [--project 경로] [--session 세션ID] [--json] [세션ID]
  인자 없음: 오늘(mtime) 수정된 세션 전부 / 세션ID: 해당 세션만.
단가 미등록 모델은 토큰만 출력하고 비용은 '?' (추정하지 않는다 — ECC 교훈:
자동 기록은 원자료까지만 신뢰).
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# USD per 1M tokens: (input, output, cache_write(1.25x), cache_read(0.1x))
# 출처: claude-api 스킬 단가표 2026-07-28. 미등록 모델은 추정하지 말고 표에 추가할 것.
PRICES = {
    "claude-opus-5": (5.0, 25.0, 6.25, 0.50),
    "claude-opus-4-8": (5.0, 25.0, 6.25, 0.50),
    "claude-sonnet-5": (3.0, 15.0, 3.75, 0.30),
    "claude-haiku-4-5": (1.0, 5.0, 1.25, 0.10),
    "claude-haiku-4-5-20251001": (1.0, 5.0, 1.25, 0.10),
    "claude-fable-5": (10.0, 50.0, 12.50, 1.00),
}


def main_checkout(start: Path) -> Path:
    """start 가 속한 저장소의 메인 체크아웃. git 밖이면 start 그대로."""
    start = start.resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        return start
    if result.returncode != 0 or not result.stdout.strip():
        return start
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = (start / common).resolve()
    return common.parent


def project_dir(project: Path | None) -> Path:
    """세션 디렉터리. project 가 None 이면 main_checkout(Path.cwd())."""
    base = project.resolve() if project is not None else main_checkout(Path.cwd())
    slug = str(base.resolve()).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug


def collect(files):
    # message.id 기준 마지막 usage만 (스트리밍 중복 방지)
    by_msg = {}
    fallback = 0
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") != "assistant":
                    continue
                msg = rec.get("message") or {}
                usage = msg.get("usage")
                if not usage:
                    continue
                key = msg.get("id")
                if key is None:
                    fallback += 1
                    key = f"_no_id_{fallback}"
                by_msg[key] = (msg.get("model", "?"), usage)
    totals = {}
    for model, u in by_msg.values():
        t = totals.setdefault(model, [0, 0, 0, 0])
        t[0] += u.get("input_tokens", 0)
        t[1] += u.get("output_tokens", 0)
        t[2] += u.get("cache_creation_input_tokens", 0)
        t[3] += u.get("cache_read_input_tokens", 0)
    return totals


def main():
    parser = argparse.ArgumentParser(description="Claude 세션 비용을 집계합니다.")
    parser.add_argument("--project", type=Path, help="세션 디렉터리 슬러그의 기준 경로")
    parser.add_argument("--session", action="append", dest="sessions",
                        help="집계할 세션 ID (여러 번 지정 가능)")
    parser.add_argument("--json", action="store_true", help="JSON 한 줄로 출력")
    parser.add_argument("session_id", nargs="?", help="하위 호환용 세션 ID")
    args = parser.parse_args()

    pdir = project_dir(args.project)
    if not pdir.is_dir():
        sys.exit(f"세션 디렉터리 없음: {pdir}")
    sessions = args.sessions or []
    if args.session_id is not None:
        sessions.append(args.session_id)
    if sessions:
        for session in sessions:
            if "/" in session or ".." in session:
                sys.exit(f"잘못된 세션 ID: {session}")
        files = [pdir / f"{session}.jsonl" for session in sessions]
        for file in files:
            if not file.is_file():
                sys.exit(f"세션 파일 없음: {file}")
    else:
        now = time.localtime()
        midnight = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, 0, 0, 0, 0, 0, -1))
        files = [f for f in pdir.glob("*.jsonl") if f.stat().st_mtime >= midnight]
        if not files:
            sys.exit("오늘 수정된 세션 없음")
    totals = collect(files)
    if not totals:
        sys.exit("집계할 usage 레코드 없음")
    grand = 0.0
    unknown = False
    unknown_models = []
    by_model = {}
    if not args.json:
        print(f"집계 대상 디렉터리: {pdir}", file=sys.stderr)
        print(f"{'model':<24} {'in':>10} {'out':>10} {'c_write':>10} {'c_read':>11} {'USD':>8}")
    for model, (i, o, cw, cr) in sorted(totals.items()):
        if i + o + cw + cr == 0:
            continue
        p = PRICES.get(model)
        if p:
            cost = (i * p[0] + o * p[1] + cw * p[2] + cr * p[3]) / 1e6
            grand += cost
            if args.json:
                by_model[model] = cost
            else:
                cost_s = f"{cost:8.2f}"
        else:
            unknown = True
            if args.json:
                unknown_models.append(model)
            else:
                cost_s = "       ?"
        if not args.json:
            print(f"{model:<24} {i:>10} {o:>10} {cw:>10} {cr:>11} {cost_s}")
    if args.json:
        print(json.dumps({"files": len(files), "project_dir": str(pdir), "usd": grand,
                           "usd_complete": not unknown_models,
                           "unknown_models": unknown_models, "by_model": by_model},
                         ensure_ascii=False))
        return
    print(f"합계: ${grand:.2f}" + (" + ? (단가 미등록 모델 있음)" if unknown else "")
          + f"  (파일 {len(files)}개)")


if __name__ == "__main__":
    main()
