from __future__ import annotations

import importlib.util
import inspect
import sys
import traceback
from pathlib import Path


def discover(paths: list[str]) -> list[Path]:
    roots = [Path(path) for path in paths if not path.startswith("-")] or [Path("tests")]
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.name.startswith("test_") and root.suffix == ".py":
            files.append(root)
        elif root.exists():
            files.extend(sorted(root.rglob("test_*.py")))
    return files


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    sys.path.insert(0, str(Path.cwd()))
    files = discover(sys.argv[1:])
    total = 0
    failed = 0
    for file_path in files:
        module = load_module(file_path)
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            total += 1
            try:
                func()
                print(f"PASS {file_path}:{name}")
            except Exception:
                failed += 1
                print(f"FAIL {file_path}:{name}")
                traceback.print_exc()
    print(f"{total - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
