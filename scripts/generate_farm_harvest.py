from __future__ import annotations

import base64
import calendar
import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib import request


ROOT = Path(__file__).resolve().parents[1]
FARM_ASSETS = ROOT / "assets" / "commit-farm"
OUT_DIR = ROOT / "dist"
OUT_FILE = OUT_DIR / "github-commit-farm.svg"

MONTHS = list(calendar.month_abbr)[1:]
FARM_MAP = FARM_ASSETS / "map.png"
FARMER_WALK_DIR = FARM_ASSETS / "farmer" / "walk-south"
FALLBACK_COUNTS = [0] * 12


def image_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def xml_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def graphql_monthly_counts(user: str, year: int, token: str) -> list[int]:
    aliases = []
    for month in range(1, 13):
        start = dt.datetime(year, month, 1, tzinfo=dt.timezone.utc)
        if month == 12:
            end = dt.datetime(year + 1, 1, 1, tzinfo=dt.timezone.utc)
        else:
            end = dt.datetime(year, month + 1, 1, tzinfo=dt.timezone.utc)
        aliases.append(
            f'm{month}: user(login: "{user}") {{ '
            f'contributionsCollection(from: "{start.isoformat()}", to: "{end.isoformat()}") '
            "{ contributionCalendar { totalContributions } } }"
        )

    payload = json.dumps({"query": "query MonthlyFarm { " + " ".join(aliases) + " }"}).encode("utf-8")
    req = request.Request(
        "https://api.github.com/graphql",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "commit-farm-readme",
        },
    )
    with request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    if "errors" in data:
        raise RuntimeError(json.dumps(data["errors"], indent=2))
    return [
        int(data["data"][f"m{month}"]["contributionsCollection"]["contributionCalendar"]["totalContributions"])
        for month in range(1, 13)
    ]


def public_monthly_counts(user: str, year: int) -> list[int]:
    url = f"https://github.com/users/{user}/contributions?from={year}-01-01&to={year}-12-31"
    req = request.Request(url, headers={"User-Agent": "commit-farm-readme"})
    with request.urlopen(req, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")

    counts = [0] * 12
    seen_dates = set()
    month_lookup = {name: index for index, name in enumerate(calendar.month_name) if name}
    pattern = re.compile(r"(\d+) contributions? on ([A-Z][a-z]+) (\d+)(?:st|nd|rd|th)")
    for amount, month_name, day in pattern.findall(html):
        month = month_lookup.get(month_name)
        if not month:
            continue
        key = (month, int(day))
        if key in seen_dates:
            continue
        seen_dates.add(key)
        counts[month - 1] += int(amount)
    return counts


def monthly_counts() -> tuple[list[int], str, int]:
    user = os.getenv("GITHUB_USER") or os.getenv("GITHUB_REPOSITORY_OWNER") or "andersonaraf"
    year = int(os.getenv("FARM_YEAR") or dt.datetime.now(dt.timezone.utc).year)
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if token:
        try:
            return graphql_monthly_counts(user, year, token), user, year
        except Exception as exc:
            print(f"Using public contribution data: {exc}")
    try:
        return public_monthly_counts(user, year), user, year
    except Exception as exc:
        print(f"Using empty contribution data: {exc}")
        return FALLBACK_COUNTS, user, year


def farmer_frames() -> str:
    frames = [image_data_uri(FARMER_WALK_DIR / f"frame-{index}.png") for index in range(4)]
    parts = []
    for index, href in enumerate(frames):
        values = ["0"] * len(frames)
        values[index] = "1"
        values.append(values[0])
        parts.append(
            f'<image width="44" height="44" href="{href}" opacity="{1 if index == 0 else 0}">'
            f'<animate attributeName="opacity" values="{";".join(values)}" dur="0.82s" repeatCount="indefinite"/>'
            "</image>"
        )
    return "".join(parts)


def speech_bubbles(counts: list[int]) -> str:
    bubbles = []
    for index, (month, count) in enumerate(zip(MONTHS, counts)):
        values = ["0"] * 13
        values[index] = "1"
        values.append("0")
        bubbles.append(
            '<g opacity="0">'
            '<rect x="-14" y="-76" width="86" height="38" rx="7" fill="#111827" opacity=".92"/>'
            '<rect x="0" y="-65" width="7" height="7" fill="#22c55e"/>'
            f'<text x="12" y="-58" class="bubble-month">{month}</text>'
            f'<text x="12" y="-44" class="bubble-count">{count} commits</text>'
            f'<animate attributeName="opacity" values="{";".join(values)}" dur="30s" repeatCount="indefinite"/>'
            "</g>"
        )
    return "".join(bubbles)


def render_svg(counts: list[int], user: str, year: int) -> str:
    total = sum(counts)
    max_count = max(counts) if counts else 0
    best_index = counts.index(max_count) if counts else 0
    positions = [
        (250, 232),
        (338, 246),
        (422, 240),
        (545, 245),
        (140, 302),
        (260, 335),
        (380, 408),
        (465, 385),
        (534, 438),
        (610, 372),
        (508, 245),
        (590, 302),
    ]
    key_times = ";".join(f"{index / 12:.3f}" for index in range(13))
    transform_values = ";".join(f"{x} {y}" for x, y in positions + [positions[0]])

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="768" height="512" viewBox="0 0 768 512" role="img" aria-labelledby="title desc">
  <title id="title">{xml_escape(user)} commit harvest farm</title>
  <desc id="desc">A pixel art farm where a farmer walks through monthly crop fields and harvests GitHub commits for {xml_escape(year)}.</desc>
  <style>
    .title {{ font: 700 18px Arial, sans-serif; fill: #f8edc0; }}
    .subtitle {{ font: 600 12px Arial, sans-serif; fill: #d6c891; }}
    .small {{ font: 700 10px Arial, sans-serif; fill: #f7e7a8; }}
    .bubble-month {{ font: 800 12px Arial, sans-serif; fill: #ffffff; }}
    .bubble-count {{ font: 500 10px Arial, sans-serif; fill: #cbd5e1; }}
  </style>
  <rect width="768" height="512" fill="#172033"/>
  <image width="768" height="512" href="{image_data_uri(FARM_MAP)}" preserveAspectRatio="xMidYMid slice"/>
  <rect x="18" y="16" width="270" height="50" rx="10" fill="#111827" opacity=".72"/>
  <text x="36" y="38" class="title">Commit Harvest Farm</text>
  <text x="36" y="56" class="subtitle">{xml_escape(user)} - {year} - {total} public contributions</text>
  <rect x="540" y="456" width="200" height="28" rx="7" fill="#111827" opacity=".72"/>
  <text x="640" y="475" text-anchor="middle" class="small">Best harvest: {MONTHS[best_index]} - {max_count} commits</text>
  <g id="farmer" transform="translate({positions[0][0]} {positions[0][1]})">
    {speech_bubbles(counts)}
    <g transform="translate(-22 -36)">{farmer_frames()}</g>
    <animateTransform attributeName="transform" type="translate" dur="30s" repeatCount="indefinite" calcMode="linear" keyTimes="{key_times}" values="{transform_values}"/>
  </g>
</svg>
'''


def main() -> None:
    counts, user, year = monthly_counts()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(render_svg(counts, user, year), encoding="utf-8")
    print(f"Wrote {OUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
