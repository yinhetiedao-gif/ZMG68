"""Regression for complete MCP bridge output over a subprocess pipe."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "external" / "imagetosvg_bridge.cjs"


class BridgeOutputTests(unittest.TestCase):
    def test_large_result_is_complete_json(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node.js is unavailable")

        with tempfile.TemporaryDirectory() as directory:
            server_root = Path(directory)
            dist = server_root / "dist"
            dist.mkdir()
            (dist / "index.js").write_text(
                "const readline = require('node:readline');\n"
                "const rl = readline.createInterface({ input: process.stdin });\n"
                "rl.on('line', line => {\n"
                "  const request = JSON.parse(line);\n"
                "  if (request.method === 'initialize') {\n"
                "    process.stdout.write(JSON.stringify({jsonrpc:'2.0', id:request.id, result:{}}) + '\\n');\n"
                "  } else if (request.method === 'tools/call') {\n"
                "    const content = 'x'.repeat(500000);\n"
                "    process.stdout.write(JSON.stringify({jsonrpc:'2.0', id:request.id, result:{content}}) + '\\n');\n"
                "  }\n"
                "});\n",
                encoding="utf-8",
            )
            completed = subprocess.run(
                [node, str(BRIDGE), str(server_root)],
                input=json.dumps({"tool": "test", "arguments": {}}),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(len(result["content"]), 500000)


if __name__ == "__main__":
    unittest.main()
