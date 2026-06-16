"""Backward-compatible package alias for the old ``corecoder`` name.

The project was renamed to ``codingagent``, but some tests and user code still
import the old package path. This shim re-exports the public API and registers
module aliases so imports like ``corecoder.session`` keep working.
"""

from __future__ import annotations

import sys as _sys

import codingagent.agent as _agent
import codingagent.config as _config
import codingagent.context as _context
import codingagent.llm as _llm
import codingagent.prompt as _prompt
import codingagent.session as _session
import codingagent.tools as _tools
from codingagent import *

_sys.modules.setdefault(__name__ + ".agent", _agent)
_sys.modules.setdefault(__name__ + ".config", _config)
_sys.modules.setdefault(__name__ + ".context", _context)
_sys.modules.setdefault(__name__ + ".llm", _llm)
_sys.modules.setdefault(__name__ + ".prompt", _prompt)
_sys.modules.setdefault(__name__ + ".session", _session)
_sys.modules.setdefault(__name__ + ".tools", _tools)

agent = _agent
config = _config
context = _context
llm = _llm
prompt = _prompt
session = _session
tools = _tools
