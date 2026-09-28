"""Development-only localhost server: python -m xiaomang_pattern_lab.web."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("xiaomang_pattern_lab.web.app:create_app", factory=True,
                host="127.0.0.1", port=8765, reload=False)
