from __future__ import annotations

import argparse
import json

from .models import Document2D


def main() -> None:
    parser = argparse.ArgumentParser(description="独立进程 Document2D 恢复检查")
    parser.add_argument("project", help="editable_geometry_project.json")
    args = parser.parse_args()
    document = Document2D.load(args.project)
    print(
        json.dumps(
            {
                "geometry_count": len(document.geometry_layer.dots),
                "reference_visible": document.reference_layer.visible,
                "selected_object_id": document.selected_object_id,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
