from __future__ import annotations

import json
from pathlib import Path


class I18N:
    def __init__(self, language: str = "zh_CN"):
        path = Path(__file__).with_name("locales") / (language + ".json")
        self.strings = json.loads(path.read_text(encoding="utf-8"))

    def t(self, key: str, **kwargs) -> str:
        return self.strings.get(key, key).format(**kwargs)
