#!/usr/bin/env python3
"""projects/<slug>/ 폴더를 템플릿으로 만든다. /script-new 스킬이 호출한다.

사용: python tools/new_project.py <slug>
"""
import datetime as dt
import re
import sys
from pathlib import Path

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,49}$")

ROOT = Path(__file__).resolve().parents[1]
STAGES = [
    "01-topic.md",
    "02-thumbnail.md",
    "03-sources.md",
    "04-candidates.md",
    "06-outline.md",
    "07-intro.md",
    "08-body.md",
    "09-review.md",
    "script-final.md",
]


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        sys.exit("사용: new_project.py <slug>\n  slug: 영문 소문자, 숫자, 하이픈. 예: gemini-stock-usage")
    slug = sys.argv[1]
    if not SLUG_RE.match(slug):
        sys.exit(f"잘못된 slug: {slug!r}. 영문 소문자, 숫자, 하이픈만 쓰고 하이픈으로 시작하지 않는다.")
    proj = ROOT / "projects" / slug
    if proj.exists():
        sys.exit(f"이미 있음: {proj}")
    (proj / "05-demo-cards").mkdir(parents=True)
    (proj / "transcripts").mkdir()
    today = dt.date.today().isoformat()
    brief = (ROOT / "templates" / "brief.md").read_text(encoding="utf-8")
    (proj / "brief.md").write_text(brief.replace("{{slug}}", slug).replace("{{date}}", today), encoding="utf-8")
    for s in STAGES:
        (proj / s).write_text(f"# {s[:-3]} — {slug}\n\n(아직 비어 있음)\n", encoding="utf-8")
    print(f"생성: {proj}")
    print("다음: brief.md의 역할, 전환 목적, 마무리 유형을 채운 뒤 /script-pipeline", slug)


if __name__ == "__main__":
    main()
