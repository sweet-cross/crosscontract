import ast
from pathlib import Path

import crosscontract.exceptions


def test_imports_nothing_from_the_rest_of_the_package():
    package_dir = Path(crosscontract.exceptions.__file__).parent
    for path in package_dir.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                assert node.level <= 1, path.name
                modules = [node.module or ""]
            else:
                continue
            assert not any(m.startswith("crosscontract") for m in modules), path.name
