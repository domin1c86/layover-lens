from __future__ import annotations

import argparse
import json

from app.services.route_training import build_route_training_artifacts, ensure_route_training_dirs, select_route_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Layover Lens route training artifacts.")
    parser.add_argument("command", choices=["init", "build", "status"])
    args = parser.parse_args()

    if args.command == "init":
        paths = ensure_route_training_dirs()
        print(json.dumps({
            "root": str(paths.root),
            "raw_csv": str(paths.raw_csv),
            "artifacts": str(paths.artifacts),
            "models": str(paths.models),
        }, ensure_ascii=False, indent=2))
        return

    if args.command == "status":
        selection = select_route_dataset()
        print(json.dumps({
            "mode": selection.mode,
            "has_csv": selection.has_csv,
            "artifact_path": str(selection.artifact_path) if selection.artifact_path else None,
            "model_path": str(selection.model_path) if selection.model_path else None,
            "dataset_version": selection.dataset_version,
            "model_version": selection.model_version,
            "warning": selection.warning,
        }, ensure_ascii=False, indent=2))
        return

    result = build_route_training_artifacts()
    print(json.dumps({
        "dataset_version": result.dataset_version,
        "model_version": result.model_version,
        "source_rows": result.source_rows,
        "accepted_rows": result.accepted_rows,
        "rejected_rows": result.rejected_rows,
        "edge_count": result.edge_count,
        "artifact_path": str(result.artifact_path),
        "model_path": str(result.model_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
