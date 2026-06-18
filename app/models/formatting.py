"""
Text formatting helpers for translation models.
"""
import json
import re
from typing import Callable, Optional, Tuple


LINE_PATTERN = re.compile(r"([^\r\n]*)(\r\n|\n|\r|$)")
EDGE_SPACE_PATTERN = re.compile(r"^(\s*)(.*?)(\s*)$", re.DOTALL)
FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")
HTML_TAG_PATTERN = re.compile(r"(<[^>]+>)")
INLINE_CODE_PATTERN = re.compile(r"(`+[^`]*`+)")
MARKDOWN_LIST_PATTERN = re.compile(r"^(\s*(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?)(.+)$")
YAML_KEY_VALUE_PATTERN = re.compile(r"^(\s*[^:#][^:\r\n]*:\s*)(.+?)(\s*)$")


def _translate_piece(
    text: str,
    translate_segment: Callable[[str], Optional[str]]
) -> Tuple[Optional[str], bool]:
    if text.strip() == "":
        return text, False

    edge_match = EDGE_SPACE_PATTERN.match(text)
    leading, content, trailing = edge_match.groups()

    if not content:
        return text, False

    translated = translate_segment(content)
    if translated is None:
        return None, False

    return f"{leading}{translated}{trailing}", True


def _translate_split_by_pattern(
    text: str,
    pattern: re.Pattern,
    translate_segment: Callable[[str], Optional[str]]
) -> Tuple[Optional[str], bool]:
    parts = []
    translated_any = False
    last = 0

    for match in pattern.finditer(text):
        before = text[last:match.start()]
        translated, changed = _translate_piece(before, translate_segment)
        if translated is None:
            return None, False
        parts.append(translated)
        translated_any = translated_any or changed
        parts.append(match.group(0))
        last = match.end()

    tail = text[last:]
    translated, changed = _translate_piece(tail, translate_segment)
    if translated is None:
        return None, False
    parts.append(translated)
    translated_any = translated_any or changed

    return "".join(parts), translated_any


def _translate_inline_text(
    text: str,
    translate_segment: Callable[[str], Optional[str]]
) -> Tuple[Optional[str], bool]:
    """Translate text while preserving inline code and HTML/XML tags."""
    html_translated, html_changed = _translate_split_by_pattern(
        text,
        HTML_TAG_PATTERN,
        lambda part: _translate_split_by_pattern(part, INLINE_CODE_PATTERN, translate_segment)[0]
    )
    return html_translated, html_changed


def _is_markdown_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def _translate_markdown_table_row(
    line: str,
    translate_segment: Callable[[str], Optional[str]]
) -> Tuple[Optional[str], bool]:
    if "|" not in line or _is_markdown_table_separator(line):
        return line, False

    cells = line.split("|")
    translated_any = False

    for index, cell in enumerate(cells):
        if index == 0 and cell == "":
            continue
        if index == len(cells) - 1 and cell == "":
            continue

        translated, changed = _translate_inline_text(cell, translate_segment)
        if translated is None:
            return None, False
        cells[index] = translated
        translated_any = translated_any or changed

    return "|".join(cells), translated_any


def _translate_json_string_values(
    line: str,
    translate_segment: Callable[[str], Optional[str]]
) -> Tuple[Optional[str], bool]:
    """Translate JSON string values on a line while keeping object keys intact."""
    result = []
    translated_any = False
    index = 0
    length = len(line)

    while index < length:
        if line[index] != '"':
            result.append(line[index])
            index += 1
            continue

        start = index
        index += 1
        escaped = False

        while index < length:
            char = line[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                index += 1
                break
            index += 1

        token = line[start:index]
        lookahead = index
        while lookahead < length and line[lookahead].isspace():
            lookahead += 1

        is_key = lookahead < length and line[lookahead] == ":"
        if is_key:
            result.append(token)
            continue

        try:
            value = json.loads(token)
        except json.JSONDecodeError:
            result.append(token)
            continue

        if not isinstance(value, str) or value.strip() == "":
            result.append(token)
            continue

        translated = translate_segment(value)
        if translated is None:
            return None, False

        result.append(json.dumps(translated, ensure_ascii=False))
        translated_any = True

    return "".join(result), translated_any


def _translate_yaml_value(
    line: str,
    translate_segment: Callable[[str], Optional[str]]
) -> Tuple[Optional[str], bool]:
    match = YAML_KEY_VALUE_PATTERN.match(line)
    if not match:
        return line, False

    prefix, value, trailing = match.groups()
    stripped = value.strip()

    if (
        not stripped
        or stripped in {"|", ">"}
        or stripped.startswith(("{", "[", "&", "*", "!"))
        or stripped.lower() in {"true", "false", "null", "none"}
        or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", stripped)
    ):
        return line, False

    comment = ""
    value_part = value
    comment_match = re.search(r"\s+#", value)
    if comment_match:
        value_part = value[:comment_match.start()]
        comment = value[comment_match.start():]

    translated, changed = _translate_inline_text(value_part, translate_segment)
    if translated is None:
        return None, False

    return f"{prefix}{translated}{comment}{trailing}", changed


def _translate_line(
    line: str,
    translate_segment: Callable[[str], Optional[str]]
) -> Tuple[Optional[str], bool]:
    stripped = line.strip()

    json_translated, json_changed = _translate_json_string_values(line, translate_segment)
    if json_translated is None:
        return None, False
    if json_changed or stripped.startswith(("{", "[")):
        return json_translated, True

    if YAML_KEY_VALUE_PATTERN.match(line):
        yaml_translated, yaml_changed = _translate_yaml_value(line, translate_segment)
        if yaml_translated is None:
            return None, False
        return yaml_translated, yaml_changed

    if "|" in line and (stripped.startswith("|") or stripped.endswith("|")):
        table_translated, table_changed = _translate_markdown_table_row(line, translate_segment)
        if table_translated is None:
            return None, False
        return table_translated, table_changed

    list_match = MARKDOWN_LIST_PATTERN.match(line)
    if list_match:
        prefix, content = list_match.groups()
        translated, changed = _translate_inline_text(content, translate_segment)
        if translated is None:
            return None, False
        return f"{prefix}{translated}", changed

    return _translate_inline_text(line, translate_segment)


def translate_preserving_line_format(
    text: str,
    translate_segment: Callable[[str], Optional[str]]
) -> Optional[str]:
    """Translate non-empty line content while preserving line breaks and edge spaces."""
    parts = []
    translated_any = False
    in_code_fence = False

    for match in LINE_PATTERN.finditer(text):
        line, newline = match.groups()

        if line == "" and newline == "":
            break

        if FENCE_PATTERN.match(line):
            in_code_fence = not in_code_fence
            parts.append(line + newline)
            continue

        if in_code_fence or line.strip() == "":
            parts.append(line + newline)
            continue

        translated, changed = _translate_line(line, translate_segment)
        if translated is None:
            return None

        parts.append(f"{translated}{newline}")
        translated_any = translated_any or changed

    if not translated_any and text.strip():
        return None

    return "".join(parts)
