"""Generate an SVG of language usage across the user's public, original repos.

Percentages are based on bytes of code reported by GitHub's languages API.
Requires only Python's standard library.
"""

import hashlib
import html
import json
import os
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USERNAME = "tandaianxle"
OUTPUT = Path(__file__).resolve().parent / "languages.svg"

COLORS = {
    "Python": "#F4C542",      # Golden yellow
    "C": "#2F81F7",           # Blue
    "JavaScript": "#F97316",  # Orange
    "HTML": "#E34F26",        # Coral-red
    "CSS": "#8B5CF6",         # Purple
}
FALLBACK_COLORS = (
    "#22C55E", "#06B6D4", "#E879F9", "#FACC15", "#FB7185", "#14B8A6"
)


def api_get(url):
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "GitHub-profile-language-bar",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"GitHub API request failed: {url}: {error}") from error


def fetch_language_totals():
    totals = Counter()
    public_repos = []
    page = 1
    while True:
        repos = api_get(
            f"https://api.github.com/users/{USERNAME}/repos?per_page=100&page={page}&type=owner"
        )
        if not isinstance(repos, list):
            raise RuntimeError(f"Unexpected repository response: {repos}")
        for repo in repos:
            if repo.get("fork") or repo.get("name", "").lower() == USERNAME.lower():
                continue
            public_repos.append(repo)
            # Language API returns a dictionary of code bytes by language.
            languages = api_get(repo["languages_url"])
            totals.update({lang: count for lang, count in languages.items() if count > 0})
        if len(repos) < 100:
            break
        page += 1
    return totals, public_repos


def color_for(language):
    if language in COLORS:
        return COLORS[language]
    index = int(hashlib.sha256(language.encode("utf-8")).hexdigest()[:8], 16)
    return FALLBACK_COLORS[index % len(FALLBACK_COLORS)]


def generate_svg(totals):
    languages = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    total_bytes = sum(totals.values())
    n_rows = (len(languages) + 1) // 2
    height = max(156, 124 + n_rows * 33)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="840" height="{height}" viewBox="0 0 840 {height}" role="img" aria-labelledby="heading description">',
        f'<title id="heading">Languages used in my projects</title>',
        f'<desc id="description">Share of code by language across public, non-fork GitHub repositories, measured by bytes.</desc>',
        f'<rect x="0.5" y="0.5" width="839" height="{height - 1}" rx="14" fill="#0D1117" stroke="#30363D"/>',
        '<text x="24" y="35" fill="#E6EDF3" font-family="Arial, sans-serif" font-size="19" font-weight="bold">Languages in my projects</text>',
        '<text x="24" y="57" fill="#8B949E" font-family="Arial, sans-serif" font-size="12">All public, original repositories · by code bytes</text>',
        '<rect x="24" y="73" width="792" height="22" rx="6" fill="#21262D"/>',
    ]
    if total_bytes == 0:
        parts.append('<text x="24" y="125" fill="#8B949E" font-family="Arial, sans-serif" font-size="14">No public project code detected yet.</text>')
    else:
        clip = '<clipPath id="bar-clip"><rect x="24" y="73" width="792" height="22" rx="6"/></clipPath>'
        parts.append(f'<defs>{clip}</defs><g clip-path="url(#bar-clip)">')
        cursor = 24.0
        for i, (language, count) in enumerate(languages):
            width = 816.0 - cursor if i == len(languages) - 1 else 792 * count / total_bytes
            parts.append(f'<rect x="{cursor:.3f}" y="73" width="{width:.3f}" height="22" fill="{color_for(language)}"/>')
            cursor += width
        parts.append('</g>')
        for i, (language, count) in enumerate(languages):
            column = i % 2
            row = i // 2
            x = 24 + 410 * column
            y = 124 + 33 * row
            safe_language = html.escape(language)
            percent = 100 * count / total_bytes
            parts.append(f'<rect x="{x}" y="{y - 12}" width="13" height="13" rx="3" fill="{color_for(language)}"/>')
            parts.append(f'<text x="{x + 23}" y="{y}" fill="#E6EDF3" font-family="Arial, sans-serif" font-size="14">{safe_language}</text>')
            parts.append(f'<text x="{x + 365}" y="{y}" text-anchor="end" fill="#8B949E" font-family="Arial, sans-serif" font-size="14">{percent:.1f}%</text>')
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'



def generate_png_cards(totals, public_repos):
    """Build local PNG cards so the README never depends on external stats hosts."""
    from PIL import Image, ImageDraw, ImageFont

    folder = Path(__file__).resolve().parent
    colors = {
        "background": "#0D1117",
        "panel": "#161B22",
        "border": "#30363D",
        "text": "#E6EDF3",
        "muted": "#8B949E",
        "track": "#21262D",
    }
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    def font(size, bold=False):
        path = font_path.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf") if bold else font_path
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            return ImageFont.load_default()

    def canvas(width, height, heading, subtitle):
        im = Image.new("RGB", (width, height), colors["background"])
        draw = ImageDraw.Draw(im)
        draw.rounded_rectangle((1, 1, width-2, height-2), radius=14, outline=colors["border"], width=2)
        draw.text((24, 16), heading, font=font(19, True), fill=colors["text"])
        draw.text((24, 46), subtitle, font=font(12), fill=colors["muted"])
        return im, draw

    entries = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    total_bytes = sum(totals.values())

    # Wide language percentage bar (mirrors the SVG, but displays more reliably).
    num_rows = (len(entries) + 1) // 2
    height = max(160, 124 + 33 * num_rows)
    bar, draw = canvas(840, height, "Languages in my projects", "All public, original repositories · by code bytes")
    draw.rounded_rectangle((24, 73, 816, 95), radius=6, fill=colors["track"])
    if total_bytes:
        x = 24
        for index, (language, count) in enumerate(entries):
            right = 816 if index == len(entries) - 1 else round(x + (792 * count / total_bytes))
            draw.rectangle((x, 73, right, 95), fill=color_for(language))
            x = right
        for index, (language, count) in enumerate(entries):
            column, row = index % 2, index // 2
            x, y = 24 + column * 410, 112 + row * 33
            draw.rounded_rectangle((x, y, x + 13, y + 13), radius=3, fill=color_for(language))
            draw.text((x + 23, y - 3), language[:25], font=font(14), fill=colors["text"])
            draw.text((x + 290, y - 3), f"{100 * count / total_bytes:.1f}%", font=font(14), fill=colors["muted"])
    else:
        draw.text((24, 111), "No public project code detected yet.", font=font(14), fill=colors["muted"])
    bar.save(folder / "languages.png", format="PNG", optimize=True)

    # Vertical list of the most-used languages.
    top, draw = canvas(440, 316, "Most Used Languages", "Measured by bytes of code · public projects")
    for index, (language, count) in enumerate(entries[:5]):
        y = 82 + 45 * index
        percentage = 100 * count / total_bytes
        draw.text((24, y), language[:22], font=font(14), fill=colors["text"])
        draw.text((357, y), f"{percentage:.1f}%", font=font(13), fill=colors["muted"])
        draw.rounded_rectangle((24, y + 23, 415, y + 31), radius=4, fill=colors["track"])
        width = max(2, round(391 * count / total_bytes))
        draw.rounded_rectangle((24, y + 23, 24 + width, y + 31), radius=4, fill=color_for(language))
    if not entries:
        draw.text((24, 100), "No public languages found yet.", font=font(14), fill=colors["muted"])
    top.save(folder / "top_languages.png", format="PNG", optimize=True)

    # Public repo summary. Avoid unverifiable contribution/commit/streak claims.
    stats, draw = canvas(440, 316, "GitHub Stats", "Public, original repositories")
    metrics = [
        ("Public projects", len(public_repos)),
        ("Stars received", sum(repo.get("stargazers_count", 0) for repo in public_repos)),
        ("Forks received", sum(repo.get("forks_count", 0) for repo in public_repos)),
        ("Languages used", len(totals)),
    ]
    for index, (label, value) in enumerate(metrics):
        x, y = 24 + (index % 2) * 202, 82 + (index // 2) * 104
        draw.rounded_rectangle((x, y, x+188, y+88), radius=10, fill=colors["panel"], outline=colors["border"])
        draw.text((x+15, y+12), str(value), font=font(29, True), fill="#E6EDF3")
        draw.text((x+15, y+56), label, font=font(12), fill=colors["muted"])
    stats.save(folder / "github_stats.png", format="PNG", optimize=True)
    print("Generated languages.png, top_languages.png, github_stats.png")


def refresh_full_profile(totals, public_repos):
    """Update the embedded language percentages and repository metrics."""
    import re

    path = Path(__file__).resolve().parent / "profile.svg"
    content = path.read_text(encoding="utf-8")
    items = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    total = sum(totals.values())
    # Keep the legend within the allotted space.
    display = items[:9]
    if len(items) > 9:
        display = items[:8] + [("Other", sum(value for _, value in items[8:]))]

    def xml_text(value):
        return html.escape(str(value), quote=True)

    def svg_text(x, y, value, size=16, color="#F0F6FC", weight=400):
        return (
            f'<text x="{x}" y="{y}" fill="{color}" '
            f'font-family="Verdana,Arial,sans-serif" font-size="{size}" '
            f'font-weight="{weight}">{xml_text(value)}</text>'
        )

    pieces = ['<g clip-path="url(#barclip)">']
    position = 52.0
    if total:
        for index, (language, amount) in enumerate(display):
            width = 908.0 - position if index == len(display) - 1 else 856.0 * amount / total
            fill = "#484F58" if language == "Other" else color_for(language)
            pieces.append(
                f'<rect x="{position:.3f}" y="978" width="{width:.3f}" '
                f'height="22" fill="{fill}"/>'
            )
            position += width
    pieces.append("</g>")
    if total:
        for index, (language, amount) in enumerate(display):
            x, y = 52 + index % 3 * 288, 1032 + index // 3 * 36
            fill = "#484F58" if language == "Other" else color_for(language)
            pieces.append(
                f'<rect x="{x}" y="{y-12}" width="13" height="13" rx="3" fill="{fill}"/>'
            )
            pieces.append(svg_text(x+23, y, f"{language} {amount/total*100:.1f}%"))
    else:
        pieces.append(svg_text(52, 1032, "No public project code detected yet.", 14, "#8B949E"))

    stats_data = [
        ("PUBLIC PROJECTS", len(public_repos)),
        ("STARS RECEIVED", sum(r.get("stargazers_count", 0) for r in public_repos)),
        ("FORKS RECEIVED", sum(r.get("forks_count", 0) for r in public_repos)),
        ("LANGUAGES USED", len(items)),
    ]
    stats = []
    for index, (label, value) in enumerate(stats_data):
        x = 52 + index * 217
        stats.append(
            f'<rect x="{x}" y="1165" width="204" height="106" '
            'rx="12" fill="#161B22" stroke="#30363D"/>'
        )
        stats.append(svg_text(x+18, 1215, value, 34, "#F0F6FC", 700))
        stats.append(svg_text(x+18, 1244, label, 11, "#8B949E", 700))

    replacements = [
        (r'<!-- GENERATED_LANGUAGE_START -->.*?<!-- GENERATED_LANGUAGE_END -->',
         '<!-- GENERATED_LANGUAGE_START -->\n' + '\n'.join(pieces) + '\n<!-- GENERATED_LANGUAGE_END -->'),
        (r'<!-- GENERATED_STATS_START -->.*?<!-- GENERATED_STATS_END -->',
         '<!-- GENERATED_STATS_START -->\n' + '\n'.join(stats) + '\n<!-- GENERATED_STATS_END -->'),
    ]
    for pattern, replacement in replacements:
        content, matches = re.subn(pattern, lambda _: replacement, content, count=1, flags=re.DOTALL)
        if matches != 1:
            raise RuntimeError(f"Profile SVG update marker missing: {pattern}")

    path.write_text(content, encoding="utf-8")

    # GitHub's image proxy can cache old SVGs long after their content changes.
    # Refresh the URL only when the SVG bytes change, preserving the README design.
    readme_path = Path(__file__).resolve().parent / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    revision = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    image_url = (
        f"https://raw.githubusercontent.com/TandaiAnxle/TandaiAnxle/main/profile.svg?v={revision}"
    )
    updated_readme, count = re.subn(
        r'src="(?:\./profile\.svg|https://raw\.githubusercontent\.com/TandaiAnxle/TandaiAnxle/main/profile\.svg(?:\?v=[^"]*)?)"',
        f'src="{image_url}"',
        readme,
        count=1,
    )
    if count != 1:
        raise RuntimeError("README profile.svg image reference missing")
    if updated_readme != readme:
        readme_path.write_text(updated_readme, encoding="utf-8")


def main():
    totals, public_repos = fetch_language_totals()
    OUTPUT.write_text(generate_svg(totals), encoding="utf-8")
    generate_png_cards(totals, public_repos)
    refresh_full_profile(totals, public_repos)
    print(f"Updated {OUTPUT} using {sum(totals.values())} bytes across {len(totals)} languages")


if __name__ == "__main__":
    main()
