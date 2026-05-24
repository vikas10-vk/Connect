"""Strip emojis and fancy Unicode from user-visible UI strings in app/ and src/."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = [ROOT / "app", ROOT / "src"]

# Leading emoji/symbol prefixes in quoted UI strings
PREFIX_RE = re.compile(
    r"^[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\s]+"
)

# Emoji icon fields in data constants (string emoji only)
ICON_FIELD_RE = re.compile(r"icon: '[^']*'", re.UNICODE)

REPLACEMENTS = [
    ("\u2014", " - "),  # em dash
    ("\u2013", "-"),    # en dash
    ("\u2026", "..."),  # ellipsis
    ("\u00b7", " | "),   # middle dot
]

CODE_REPLACEMENTS = [
    (", emoji: '[^']*'", ""),
    (', emoji: "[^"]*"', ""),
    (r"\{urgency\.emoji\} \{urgency\.label\}", "{urgency.label}"),
    (r"\{u\.emoji\} \{u\.label\}", "{u.label}"),
    (r"` · \$\{u\.emoji\}", "` | "),
    (r"\{isNewState \? '\u26a1 ' : ''\}", ""),
    (r"\{isNewState \? '\u26a1 ' : ''\}\{s\.label\}", "{s.label}"),
]

STRING_FIXES = [
    ("'✅  Yes, it's resolved'", "'Yes, it\\'s resolved'"),
    ("'❌  Still not right'", "'Still not right'"),
    ("'✓ Accepted'", "'Accepted'"),
    ("'✕ Declined'", "'Declined'"),
    ("'✕ Cancelled'", "'Cancelled'"),
    ("'⏳ Awaiting decision'", "'Awaiting decision'"),
    ("'⏳ Pending'", "'Pending'"),
    ("'✓ Verified'", "'Verified'"),
    ("'✗ Rejected'", "'Rejected'"),
    ("'⏳ Pending'", "'Pending'"),
    ("'✓ Selected'", "'Selected'"),
    ("'● {s.label}'", "'{s.label}'"),
    ("'● Open'", "'Open'"),
    ("'⚡ '", "''"),
    ("'⭐ Review needed'", "'Review needed'"),
    ("'✓ Completed'", "'Completed'"),
    ("'Review published ✓'", "'Review published'"),
    ("'Review submitted ✓'", "'Review submitted'"),
    ("'⛔ Work stopped mid-job'", "'Work stopped mid-job'"),
    ("'⚠️ Dispute under review'", "'Dispute under review'"),
    ("'⚠ '", "''"),
    ("'✓ Waiting for homeowner confirmation'", "'Waiting for homeowner confirmation'"),
    ("'✅  I've fixed it — notify homeowner'", "'I've fixed it - notify homeowner'"),
    ("'✅  I\\'ve fixed it — notify homeowner'", "'I\\'ve fixed it - notify homeowner'"),
    ("'🏠 Residential'", "'Residential'"),
    ("'🏢 Commercial'", "'Commercial'"),
    ("'● Online'", "'Online'"),
    ("Good day, {firstName} 👋", "Good day, {firstName}"),
    ("Hi {user?.name?.split(\" \")[0] || \"there\"} 👋", "Hi {user?.name?.split(\" \")[0] || \"there\"}"),
    ("🏠 Home health chart coming soon", "Home health chart coming soon"),
]

CHIP_EMOJI_RE = re.compile(
    r"\['(?:[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]+\s*)+([^']+)',\s*"
)


def strip_emoji_icon_fields(text: str, path: Path) -> str:
    if path.name in ("categories.ts", "problems.ts"):
        text = ICON_FIELD_RE.sub("icon: ''", text)
    return text


def fix_chip_array(text: str) -> str:
    """Remove emoji prefixes from onboarding chip strings."""
    def repl(m: re.Match) -> str:
        inner = m.group(0)
        items = re.findall(r"'([^']*)'", inner)
        cleaned = []
        for item in items:
            item = PREFIX_RE.sub("", item).strip()
            cleaned.append(f"'{item}'")
        return "[" + ", ".join(cleaned) + "]"
    return re.sub(
        r"\[(?:'[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u200D\s]+[^']*',?\s*)+\]",
        repl,
        text,
        count=1,
    )


def fix_content(text: str, path: Path) -> str:
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)

    for old, new in STRING_FIXES:
        text = text.replace(old, new)

    text = re.sub(r", emoji: '[^']*'", "", text)
    text = re.sub(r'\{urgency\.emoji\} \{urgency\.label\}', '{urgency.label}', text)
    text = re.sub(r'\{u\.emoji\} \{u\.label\}', '{u.label}', text)
    text = re.sub(r'` · \$\{u\.emoji\} ', '` | ', text)
    text = re.sub(r"\{isNewState \? '⚡ ' : ''\}", "", text)
    text = re.sub(
        r"<span style=\{\{ fontSize: 10, fontWeight: 700, padding: '4px 10px', borderRadius: 20, color: s\.color, background: s\.bg \}\}>● \{s\.label\}</span>",
        "<span style={{ fontSize: 10, fontWeight: 700, padding: '4px 10px', borderRadius: 20, color: s.color, background: s.bg }}>{s.label}</span>",
        text,
    )
    text = re.sub(r"🔧 \{SERVICE_TYPE_LABELS", "{SERVICE_TYPE_LABELS", text)
    text = text.replace("icon: '🔧'", "icon: ''")
    text = text.replace("toast(", "toast(")  # noop anchor
    text = re.sub(r"icon: '⚠️'", "icon: undefined", text)
    text = re.sub(r"\$\{nw \? '!' : '✓'\}", "${nw ? '!' : ''}", text)

    text = strip_emoji_icon_fields(text, path)

    if path.name == "onboarding/page.tsx" or str(path).endswith("onboarding/page.tsx"):
        # Fix bio chips array on onboarding
        text = re.sub(
            r"\['🔧 10\+ years experience', '✅ Licensed & insured',[^\]]+\]",
            lambda m: "[" + ", ".join(
                f"'{PREFIX_RE.sub('', x).strip()}'"
                for x in re.findall(r"'([^']*)'", m.group(0))
            ) + "]",
            text,
        )

    # Record type: remove emoji from URGENCY type
    text = text.replace(
        "Record<string, { label: string; emoji: string }>",
        "Record<string, { label: string }>",
    )
    text = text.replace(
        "Record<string, { label: string; emoji: string; color: string }>",
        "Record<string, { label: string; color: string }>",
    )

    return text


def main() -> None:
    changed = []
    for base in DIRS:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in {".tsx", ".ts"}:
                continue
            if ".fuse_hidden" in path.name:
                continue
            try:
                original = path.read_text(encoding="utf-8")
            except OSError:
                continue
            fixed = fix_content(original, path)
            if fixed != original:
                path.write_text(fixed, encoding="utf-8", newline="\n")
                changed.append(str(path.relative_to(ROOT)))

    (ROOT / "scripts" / "plain_text_result.txt").write_text(
        "\n".join(changed), encoding="utf-8"
    )
    print(len(changed))


if __name__ == "__main__":
    main()
