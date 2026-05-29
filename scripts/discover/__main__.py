"""使 `python -m scripts.discover` 可直接运行发现 CLI。

实际逻辑在 scripts/discover_popular.py，这里只是包级入口转发。
"""

from __future__ import annotations

from ..discover_popular import main

if __name__ == "__main__":
    raise SystemExit(main())
