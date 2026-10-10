"""Keep the suite hermetic: a developer's `.env` must not change what the tests prove.

`Settings` reads `backend/.env`, which is where a local run keeps its API keys. The
integration tests are written against the rule reviewer, whose verdicts the file list
decides deterministically. A key in that file would quietly send every verdict to the
model instead, so a machine that is merely configured — not broken — would see the
suite fail on a network response it never meant to depend on.

The environment wins over the `.env` file, and this module is imported before any test
module, so clearing the key here keeps a live model out of the run. Tests that want
the model say so themselves.
"""

from __future__ import annotations

import os

os.environ["MISTHOS_ANTHROPIC_API_KEY"] = ""
