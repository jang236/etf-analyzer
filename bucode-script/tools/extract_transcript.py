#!/usr/bin/env python3
"""유튜브 영상 자막을 텍스트로 뽑는다. 대본 추출기가 쓴다.

사용:
  python tools/extract_transcript.py <url 또는 video_id> [...] --out <dir>

의존: pip install youtube-transcript-api
자막이 없거나 접근이 막힌 영상은 건너뛰고 사유를 출력한다.
"""
import argparse
import re
import sys
from pathlib import Path

VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})")


def video_id(s: str) -> str:
    m = VIDEO_ID_RE.search(s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    raise ValueError(f"영상 ID를 찾을 수 없음: {s}")


def fetch(vid: str, langs):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        sys.exit("youtube-transcript-api가 없습니다. pip install youtube-transcript-api")
    api = YouTubeTranscriptApi()
    transcript = api.fetch(vid, languages=list(langs))
    lines = []
    for item in transcript:
        start = getattr(item, "start", None)
        text = getattr(item, "text", None)
        if start is None and isinstance(item, dict):
            start, text = item.get("start"), item.get("text")
        m, s = divmod(int(start or 0), 60)
        lines.append(f"[{m:02d}:{s:02d}] {text}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("videos", nargs="+")
    p.add_argument("--out", default=".", help="저장 폴더")
    p.add_argument("--lang", default="ko,en", help="우선 언어, 쉼표 구분")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    langs = [x.strip() for x in a.lang.split(",") if x.strip()]
    ok = 0
    for v in a.videos:
        try:
            vid = video_id(v)
            text = fetch(vid, langs)
            path = out / f"{vid}.txt"
            path.write_text(f"# source: https://www.youtube.com/watch?v={vid}\n\n{text}\n", encoding="utf-8")
            print(f"저장: {path}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"건너뜀: {v} ({e})", file=sys.stderr)
    print(f"{ok}/{len(a.videos)} 완료")


if __name__ == "__main__":
    main()
