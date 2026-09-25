"""Interactive checks for individual AI pipeline components."""

import sys


# Local model responses and knowledge-base content may contain Unicode symbols.
# Force UTF-8 when these checks are launched as ``python -m tests.manual...``
# so Windows PowerShell does not fail while printing a valid model response.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
