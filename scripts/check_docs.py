"""Check local Markdown links/anchors in repository documentation, without network calls."""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+['\"][^\n]*?['\"])?\s*\)")


def prose(text):
    """Ignore fenced examples, which are not rendered as documentation links."""
    lines = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            lines.append("")
        else:
            lines.append(line if fence is None else "")
    return "\n".join(lines)


def anchors(text):
    found, counts = set(), {}
    for line in prose(text).splitlines():
        heading = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not heading:
            continue
        label = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading.group(1))
        slug = re.sub(r"[^\w\- ]", "", label.lower()).replace(" ", "-")
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        found.add(f"{slug}-{number}" if number else slug)
    found.update(re.findall(r'<a\s+(?:id|name)=[\'"]([^\'\"]+)', text))
    return found


def check(root=ROOT):
    files = [root / name for name in ("README.md", "AGENTS.md", "CONTRIBUTING.md")]
    files.extend(sorted((root / "docs").rglob("*.md")))
    errors, checked, cache = [], 0, {}
    for path in files:
        if not path.is_file():
            errors.append(f"Missing entrypoint: {path.relative_to(root)}")
            continue
        for number, line in enumerate(prose(path.read_text()).splitlines(), 1):
            for match in LINK.finditer(line):
                raw = match.group(1).strip("<>")
                url = urlsplit(raw)
                if url.scheme or url.netloc:
                    continue
                target = (path.parent / unquote(url.path)).resolve() if url.path else path
                checked += 1
                location = f"{path.relative_to(root)}:{number}"
                if not target.exists():
                    errors.append(f"{location}: missing target {raw}")
                elif url.fragment and target.suffix == ".md":
                    if target not in cache:
                        cache[target] = anchors(target.read_text())
                    if unquote(url.fragment) not in cache[target]:
                        errors.append(f"{location}: missing anchor {raw}")
    return checked, errors


if __name__ == "__main__":
    checked, errors = check()
    if errors:
        print("\n".join(errors))
    else:
        print(f"Documentation links passed: {checked} local links/anchors")
    raise SystemExit(bool(errors))
