"""Keep the suite hermetic: a developer's `.env` must not change what the tests prove.

`Settings` reads `backend/.env`, which is where a local run keeps its API keys. The
integration tests are written against the rule reviewer, whose verdicts the file list
decides deterministically. A key in that file would quietly send every verdict to the
model instead, so a machine that is merely configured — not broken — would see the
suite fail on a network response it never meant to depend on.

The GitHub App is the same shape and worse: `build_github` returns a live `GitHubApp`
as soon as the id and the key are both set, so a configured machine would read a real
repository, and a publisher-shaped test would open a real issue on GitHub.

The environment wins over the `.env` file, and this module is imported before any test
module, so clearing both here keeps the network out of the run. Tests that want the
model, or the App, construct one themselves.
"""

from __future__ import annotations

import os

os.environ["MISTHOS_ANTHROPIC_API_KEY"] = ""
os.environ["MISTHOS_GITHUB_APP_ID"] = ""
os.environ["MISTHOS_GITHUB_APP_PRIVATE_KEY"] = ""
