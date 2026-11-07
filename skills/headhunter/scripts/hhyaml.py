"""Read and write the YAML subset used by headhunter Data folder files.

Python's standard library has no YAML module, so the skill ships this one.
Supported: block mappings and sequences, flow sequences and mappings on one
line, plain and quoted scalars, `|` and `>` block scalars, and comments.
Scalars resolve to null (`null`, `~`, empty), true / false, integers, or
strings. Anchors, aliases, tags, multi-line plain scalars and multiple
documents are rejected with the line number.
"""

from __future__ import annotations

import json
import re

__all__ = ["YamlError", "loads", "dumps", "load", "dump"]

_INT = re.compile(r"^[-+]?[0-9]+$")
_FLOAT = re.compile(r"^[-+]?(?:[0-9]+\.[0-9]*|\.[0-9]+)$")
_RESERVED_PLAIN = {"null", "~", "true", "false", "yes", "no", "on", "off", "y", "n"}


class YamlError(ValueError):
    def __init__(self, message: str, line: int | None = None):
        self.line = line
        super().__init__(f"line {line}: {message}" if line else message)


def load(path):
    with open(path, encoding="utf-8") as handle:
        return loads(handle.read())


def dump(obj, path) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(dumps(obj))


# ---------------------------------------------------------------- reading


def loads(text: str):
    return _Parser(text).parse()


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _strip_comment(text: str) -> str:
    quote = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\" and quote == '"':
                i += 2
                continue
            if ch == quote:
                if quote == "'" and i + 1 < len(text) and text[i + 1] == "'":
                    i += 2
                    continue
                quote = None
        elif ch in "\"'" and (i == 0 or text[i - 1] in " \t[{,:"):
            quote = ch
        elif ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i].rstrip()
        i += 1
    return text.rstrip()


def _is_seq_item(content: str) -> bool:
    return content == "-" or content.startswith("- ")


def _split_key(content: str):
    """Return (key, rest) when content is `key: value` or `key:`, else None."""
    if not content or content[0] in "[{&*!|>%@`#":
        return None
    if content[0] in "\"'":
        quote = content[0]
        i = 1
        while i < len(content):
            if content[i] == "\\" and quote == '"':
                i += 2
                continue
            if content[i] == quote:
                if quote == "'" and i + 1 < len(content) and content[i + 1] == "'":
                    i += 2
                    continue
                break
            i += 1
        else:
            return None
        after = content[i + 1 :]
        if after == ":" or after.startswith(": "):
            return _parse_quoted(content[: i + 1], None), after[1:]
        return None
    for i, ch in enumerate(content):
        if ch == ":" and (i + 1 == len(content) or content[i + 1] == " "):
            key = content[:i].rstrip()
            if not key:
                return None
            return key, content[i + 1 :]
        if ch == " " and i + 1 < len(content) and content[i + 1] == "#":
            return None
    return None


def _parse_quoted(text: str, line: int | None) -> str:
    quote = text[0]
    if len(text) < 2 or text[-1] != quote:
        raise YamlError("unterminated quoted string", line)
    body = text[1:-1]
    if quote == "'":
        if re.search(r"(?<!')'(?!')", body.replace("''", "")):
            raise YamlError("unescaped single quote", line)
        return body.replace("''", "'")
    try:
        return json.loads('"' + body.replace("\t", "\\t") + '"')
    except json.JSONDecodeError as exc:
        raise YamlError(f"bad escape in double-quoted string: {exc.msg}", line) from None


def _resolve_plain(text: str, line: int | None):
    if text in ("", "~", "null", "Null", "NULL"):
        return None
    if text in ("true", "True", "TRUE"):
        return True
    if text in ("false", "False", "FALSE"):
        return False
    if _INT.match(text):
        return int(text)
    if _FLOAT.match(text):
        return float(text)
    if text[0] in "&*!|>%@`":
        raise YamlError(f"unsupported YAML syntax at {text[:20]!r}", line)
    if text.startswith("- ") or text == "-":
        raise YamlError("a sequence cannot start after a key on the same line", line)
    if ": " in text or text.endswith(":"):
        raise YamlError("plain value contains ': '; quote the value", line)
    return text


class _Flow:
    def __init__(self, text: str, line: int):
        self.text = text
        self.i = 0
        self.line = line

    def parse(self):
        value = self.value()
        self.space()
        if self.i != len(self.text):
            raise YamlError(f"unexpected text after value: {self.text[self.i:]!r}", self.line)
        return value

    def space(self):
        while self.i < len(self.text) and self.text[self.i] == " ":
            self.i += 1

    def value(self, stops=",]}"):
        self.space()
        if self.i >= len(self.text):
            raise YamlError("missing value in flow collection", self.line)
        ch = self.text[self.i]
        if ch == "[":
            return self.sequence()
        if ch == "{":
            return self.mapping()
        if ch in "\"'":
            return self.quoted()
        start = self.i
        while self.i < len(self.text) and self.text[self.i] not in stops:
            self.i += 1
        return _resolve_plain(self.text[start : self.i].strip(), self.line)

    def quoted(self):
        quote = self.text[self.i]
        j = self.i + 1
        while j < len(self.text):
            if self.text[j] == "\\" and quote == '"':
                j += 2
                continue
            if self.text[j] == quote:
                if quote == "'" and j + 1 < len(self.text) and self.text[j + 1] == "'":
                    j += 2
                    continue
                break
            j += 1
        else:
            raise YamlError("unterminated quoted string", self.line)
        value = _parse_quoted(self.text[self.i : j + 1], self.line)
        self.i = j + 1
        return value

    def sequence(self):
        self.i += 1
        items = []
        self.space()
        if self.i < len(self.text) and self.text[self.i] == "]":
            self.i += 1
            return items
        while True:
            items.append(self.value())
            self.space()
            if self.i >= len(self.text):
                raise YamlError("unterminated flow sequence", self.line)
            if self.text[self.i] == ",":
                self.i += 1
                continue
            if self.text[self.i] == "]":
                self.i += 1
                return items
            raise YamlError(f"expected ',' or ']' at {self.text[self.i:]!r}", self.line)

    def mapping(self):
        self.i += 1
        result = {}
        self.space()
        if self.i < len(self.text) and self.text[self.i] == "}":
            self.i += 1
            return result
        while True:
            key = self.value(stops=":,}")
            self.space()
            if self.i >= len(self.text) or self.text[self.i] != ":":
                raise YamlError("expected ':' in flow mapping; quote values that contain commas", self.line)
            self.i += 1
            if key in result:
                raise YamlError(f"duplicate key {key!r}", self.line)
            result[key] = self.value()
            self.space()
            if self.i >= len(self.text):
                raise YamlError("unterminated flow mapping", self.line)
            if self.text[self.i] == ",":
                self.i += 1
                self.space()
                continue
            if self.text[self.i] == "}":
                self.i += 1
                return result
            raise YamlError(f"expected ',' or '}}' at {self.text[self.i:]!r}", self.line)


class _Parser:
    def __init__(self, text: str):
        self.lines = text.splitlines()
        for n, line in enumerate(self.lines, 1):
            if "\t" in line[: len(line) - len(line.lstrip())]:
                raise YamlError("tabs are not allowed for indentation", n)
        self.pos = 0

    def parse(self):
        i = self.next_line()
        if i is None:
            return None
        content = self.lines[i].strip()
        if content.startswith("---") or content.startswith("%"):
            raise YamlError("document markers and directives are not supported", i + 1)
        value = self.block(_indent_of(self.lines[i]))
        rest = self.next_line()
        if rest is not None:
            raise YamlError("unexpected content; check indentation", rest + 1)
        return value

    def next_line(self):
        i = self.pos
        while i < len(self.lines):
            stripped = self.lines[i].strip()
            if stripped and not stripped.startswith("#"):
                return i
            i += 1
        return None

    def block(self, indent: int):
        i = self.next_line()
        assert i is not None, "block() is only called before a significant line"
        content = self.lines[i][indent:]
        if _is_seq_item(content):
            return self.sequence(indent)
        if _split_key(_strip_comment(content)) is not None:
            return self.mapping(indent)
        self.pos = i + 1
        text = _strip_comment(content).strip()
        if text[0] in "[{":
            return _Flow(text, i + 1).parse()
        if text[0] in "\"'":
            return _parse_quoted(text, i + 1)
        return _resolve_plain(text, i + 1)

    def value_after(self, rest: str, indent: int, line: int, allow_same_indent_seq: bool):
        text = _strip_comment(rest).strip()
        if text == "":
            j = self.next_line()
            if j is None:
                return None
            nindent = _indent_of(self.lines[j])
            ncontent = self.lines[j][nindent:]
            if nindent > indent:
                return self.block(nindent)
            if allow_same_indent_seq and nindent == indent and _is_seq_item(ncontent):
                return self.sequence(indent)
            return None
        if text[0] in "|>":
            return self.block_scalar(text, indent, line)
        if text[0] in "[{":
            return _Flow(text, line).parse()
        if text[0] in "\"'":
            return _parse_quoted(text, line)
        return _resolve_plain(text, line)

    def mapping(self, indent: int):
        result = {}
        while True:
            i = self.next_line()
            if i is None:
                break
            line = self.lines[i]
            ind = _indent_of(line)
            if ind < indent:
                break
            if ind > indent:
                raise YamlError("unexpected indentation", i + 1)
            content = line[ind:]
            if _is_seq_item(content):
                break
            split = _split_key(_strip_comment(content))
            if split is None:
                raise YamlError("expected 'key: value'", i + 1)
            key, rest = split
            if key in result:
                raise YamlError(f"duplicate key {key!r}", i + 1)
            self.pos = i + 1
            result[key] = self.value_after(rest, indent, i + 1, allow_same_indent_seq=True)
        return result

    def sequence(self, indent: int):
        items = []
        while True:
            i = self.next_line()
            if i is None:
                break
            line = self.lines[i]
            ind = _indent_of(line)
            content = line[ind:]
            if ind < indent or (ind == indent and not _is_seq_item(content)):
                break
            if ind > indent:
                raise YamlError("unexpected indentation", i + 1)
            rest = content[1:]
            inner = rest.lstrip(" ")
            if inner and not inner.startswith("#") and _split_key(_strip_comment(inner)) is not None:
                column = ind + 1 + (len(rest) - len(inner))
                self.lines[i] = " " * column + inner
                self.pos = i
                items.append(self.mapping(column))
                continue
            self.pos = i + 1
            items.append(self.value_after(rest, indent, i + 1, allow_same_indent_seq=False))
        return items

    def block_scalar(self, header: str, indent: int, line: int) -> str:
        match = re.match(r"^([|>])([-+]?)$", header)
        if not match:
            raise YamlError(f"unsupported block scalar header {header!r}", line)
        style, chomp = match.groups()
        body = []
        content_indent = None
        i = self.pos
        while i < len(self.lines):
            raw = self.lines[i]
            if raw.strip() == "":
                body.append("")
                i += 1
                continue
            ind = _indent_of(raw)
            if content_indent is None:
                if ind <= indent:
                    break
                content_indent = ind
            if ind < content_indent:
                break
            body.append(raw[content_indent:])
            i += 1
        trailing = 0
        while body and body[-1] == "":
            body.pop()
            trailing += 1
        self.pos = i
        if style == "|":
            text = "\n".join(body)
        else:
            parts = []
            for row in body:
                if row == "":
                    parts.append("\n")
                elif parts and not parts[-1].endswith("\n"):
                    parts.append(" " + row)
                else:
                    parts.append(row)
            text = "".join(parts)
        if not body:
            return ""
        if chomp == "-":
            return text
        if chomp == "+":
            return text + "\n" * (trailing + 1)
        return text + "\n"


# ---------------------------------------------------------------- writing


def _plain_ok(text: str, flow: bool) -> bool:
    if text == "" or text != text.strip() or "\n" in text or "\t" in text:
        return False
    if text.lower() in _RESERVED_PLAIN or _INT.match(text) or _FLOAT.match(text):
        return False
    if text[0] in "-?:,[]{}#&*!|>'\"%@`" or ": " in text or " #" in text or text.endswith(":"):
        return False
    if '"' in text or " '" in text:
        return False
    if flow and any(ch in text for ch in ",[]{}"):
        return False
    return True


def _scalar(value, flow: bool = False) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return repr(value)
    text = str(value)
    if _plain_ok(text, flow):
        return text
    return json.dumps(text, ensure_ascii=False)


def _is_scalar(value) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _flow(value) -> str:
    if isinstance(value, list):
        return "[" + ", ".join(_flow(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_scalar(k, True)}: {_flow(v)}" for k, v in value.items()) + "}"
    return _scalar(value, flow=True)


def _small_dict(value) -> bool:
    return isinstance(value, dict) and len(value) <= 3 and all(_is_scalar(v) for v in value.values())


def _inline(value, depth: int) -> str | None:
    """Return a one-line form for value, or None when it needs a block."""
    if _is_scalar(value):
        return _scalar(value)
    if value == [] or value == {}:
        return _flow(value)
    if isinstance(value, list) and depth > 0:
        if all(_is_scalar(v) for v in value) or all(_small_dict(v) for v in value):
            text = _flow(value)
            if len(text) <= 100:
                return text
    return None


def _emit(value, indent: int, depth: int, out: list) -> None:
    pad = " " * indent
    if isinstance(value, dict):
        for key, item in value.items():
            inline = _inline(item, depth + 1)
            if inline is not None:
                out.append(f"{pad}{_scalar(key)}: {inline}")
            else:
                out.append(f"{pad}{_scalar(key)}:")
                _emit(item, indent + 2, depth + 1, out)
    elif isinstance(value, list):
        for item in value:
            inline = _inline(item, depth + 1)
            if inline is not None:
                out.append(f"{pad}- {inline}")
            elif isinstance(item, dict):
                lines: list = []
                _emit(item, indent + 2, depth + 1, lines)
                lines[0] = f"{pad}- " + lines[0][indent + 2 :]
                out.extend(lines)
            else:
                out.append(f"{pad}-")
                _emit(item, indent + 2, depth + 1, out)
    else:
        out.append(pad + _scalar(value))


def dumps(obj) -> str:
    inline = _inline(obj, 0)
    if inline is not None:
        return inline + "\n"
    out: list = []
    _emit(obj, 0, 0, out)
    return "\n".join(out) + "\n"
