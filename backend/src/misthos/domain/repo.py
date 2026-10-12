"""Reading `owner/name` out of whatever a publisher pasted.

A publisher has the issue open in a browser, so what they have to hand is the address
bar, not the two fields a form used to ask for. The link and the name carry the same
fact, so it is read once here rather than in every caller.

GitHub reports a repository as `owner/name`, and that is what connections, webhooks
and the loop compare — case-insensitively. A pasted URL therefore has to become that
same string before it is stored, or nothing downstream would ever match it.
"""

from __future__ import annotations

import re

# Alphanumeric, or `-`, `_`, `.`. Deliberately looser than GitHub's own rules so a
# valid repository is never refused here; GitHub is the arbiter of what exists.
_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")
# `git@github.com:owner/name`, which is what `git remote -v` prints.
_SCP = re.compile(r"^git@github\.com:", re.IGNORECASE)
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")
_HOST = re.compile(r"^(?P<host>[A-Za-z0-9.\-]+)/")
_KNOWN_HOSTS = {"github.com", "www.github.com"}
# The path segments a link carries a number under.
_NUMBER_SEGMENTS = {"issues", "pull"}


def parse_repo_link(value: str) -> tuple[str, int | None]:
    """The `owner/name` in `value`, and the issue or pull number a link carries.

    Accepts `owner/name`, a `github.com` URL (with or without a scheme), a `git@`
    remote, and a `.git` suffix, dropping anything after the repository — a branch, a
    file, an issue. Anything that names no repository on GitHub gives `("", None)`,
    including a URL for another host, so a wrong paste is refused rather than stored
    as a repository that cannot exist.
    """
    text = _SCP.sub("", value.strip())
    text = _SCHEME.sub("", text)
    text = text.split("#", 1)[0].split("?", 1)[0]

    host = _HOST.match(text)
    if host is not None and "." in host.group("host"):
        if host.group("host").lower() not in _KNOWN_HOSTS:
            return "", None
        text = text[host.end() :]

    parts = [part for part in text.split("/") if part]
    if len(parts) < 2:
        return "", None
    owner, name = parts[0], parts[1]
    if not _SEGMENT.match(owner) or not _SEGMENT.match(name):
        return "", None
    if name.lower().endswith(".git"):
        name = name[: -len(".git")]
    # A name of dots alone is a path artefact, not a repository.
    if not name or not _SEGMENT.match(name) or set(name) <= {"."}:
        return "", None

    number: int | None = None
    if len(parts) >= 4 and parts[2].lower() in _NUMBER_SEGMENTS and parts[3].isdigit():
        number = int(parts[3])
    return f"{owner}/{name}", number


def normalize_repo(value: str) -> str:
    """`owner/name` for whatever was pasted, or `""` when it names no repository."""
    return parse_repo_link(value)[0]
