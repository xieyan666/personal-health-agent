from pypinyin import Style, lazy_pinyin

def name_pinyin(value: str | None) -> str:
    """Full pinyin with an initialism suffix, e.g. 谢妍 -> xieyan xy."""
    if not value:
        return ""
    full = "".join(lazy_pinyin(value, style=Style.NORMAL)).lower()
    initials = "".join(lazy_pinyin(value, style=Style.FIRST_LETTER)).lower()
    return f"{full} {initials}".strip()
