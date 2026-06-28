"""LLM fallback normalization for AlgebraicSpecificationDataLayer.metta."""

import re


_SECTION_TO_KIND = {
    "sorts": "sort",
    "operations": "operation",
    "predicates": "predicate",
    "axioms": "axiom",
}

_STV_RE = re.compile(r"\(stv\s+([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\)")


def _name(value):
    return str(value).strip()


def _strip_markdown(text):
    text = str(text).strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        text = "\n".join(lines[1:])
    if "```" in text:
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _unwrap_colon_container(text):
    """Repair (: (: proof ...) (: proof ...)) into ((: proof ...) (: proof ...))."""
    if not text.startswith("(:"):
        return text

    rest = text[2:].strip()
    if not rest.endswith(")"):
        return text

    inner = rest[:-1].strip()
    if inner.startswith("("):
        return f"({inner})"
    return text


def _ensure_list(text):
    text = _unwrap_colon_container(text.strip())
    if text == "()":
        return text

    is_list = text.startswith("(") and text[1:].lstrip().startswith(("(", ")"))
    if is_list:
        return text
    return f"({text})"


def _split_outer_list(text):
    if text == "()":
        return []

    body = text[1:-1].strip()
    entries = []
    start = None
    depth = 0

    for index, char in enumerate(body):
        if char == "(":
            if depth == 0:
                start = index
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and start is not None:
                entries.append(body[start:index + 1])
                start = None

    return entries


def _clamp_stv(entry):
    def replace(match):
        strength = min(max(float(match.group(1)), 0.35), 0.55)
        confidence = min(max(float(match.group(2)), 0.35), 0.55)
        return f"(stv {strength:.3f} {confidence:.3f})"

    return _STV_RE.sub(replace, entry)


def _force_concept_and_perspective(entry, kind, concept, perspective):
    pattern = re.compile(rf"(\(spec-{re.escape(kind)}\s+)([^\s()]+)(\s+)([^\s()]+)")
    return pattern.sub(
        lambda match: f"{match.group(1)}{concept}{match.group(3)}{perspective}",
        entry,
        count=1,
    )


def normalize_metta_list_text(text, concept=None, perspective=None, part=None):
    """Return one parseable MeTTa list of fallback proof atoms.

    This is intentionally conservative. It fixes common LLM formatting errors,
    forces the requested concept/perspective into returned spec atoms, and drops
    entries that do not match the requested section shape.
    """
    concept = _name(concept) if concept is not None else None
    perspective = _name(perspective) if perspective is not None else None
    part = _name(part) if part is not None else None
    kind = _SECTION_TO_KIND.get(part)

    text = _strip_markdown(text)
    if not text:
        return "()"

    entries = _split_outer_list(_ensure_list(text))
    if not entries:
        return "()"

    normalized = []
    required_token = f"(spec-{kind}" if kind else None

    for entry in entries:
        if required_token and required_token not in entry:
            continue

        if kind and concept and perspective:
            entry = _force_concept_and_perspective(entry, kind, concept, perspective)

        if kind == "operation":
            if "(operation " not in entry or "(->" not in entry:
                continue

        normalized.append(_clamp_stv(entry))

    return f"({' '.join(normalized[:5])})" if normalized else "()"
