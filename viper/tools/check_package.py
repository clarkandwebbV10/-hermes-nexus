#!/usr/bin/env python3
"""Build and test a local wheel without contacting an index or publishing it.

Run with Python 3.11+ and the project's build requirements installed.
All build and installation output lives in a temporary directory.
"""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
import venv


def main() -> None:
    package = Path(__file__).resolve().parents[1]
    with (package / "pyproject.toml").open("rb") as metadata_file:
        project = tomllib.load(metadata_file)["project"]
    expected_version = project["version"]
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    with tempfile.TemporaryDirectory(prefix="hidden-viper-package-check-") as td:
        work = Path(td)

        def run(command: list[str], expected_code: int | None = 0) -> subprocess.CompletedProcess:
            print("+", shlex.join(command), flush=True)
            result = subprocess.run(
                command, cwd=work, env=environment, capture_output=True, text=True, timeout=120
            )
            print(result.stdout, end="", flush=True)
            print(result.stderr, end="", flush=True)
            if expected_code is not None and result.returncode != expected_code:
                raise RuntimeError(f"expected exit {expected_code}, received {result.returncode}")
            return result

        copied_source = work / "source"
        shutil.copytree(
            package,
            copied_source,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", "venv", "__pycache__", "build", "dist",
                "*.egg-info", ".pytest_cache", ".mypy_cache",
            ),
        )
        wheels = work / "wheels"
        run([
            sys.executable, "-m", "pip", "wheel", "--no-index", "--no-build-isolation",
            "--no-deps", "--wheel-dir", str(wheels), str(copied_source),
        ])
        wheel_files = list(wheels.glob("*.whl"))
        if len(wheel_files) != 1:
            raise RuntimeError(f"expected one built wheel, received {len(wheel_files)}")

        installed_environment = work / "installed"
        venv.EnvBuilder(with_pip=True).create(installed_environment)
        executable_dir = installed_environment / ("Scripts" if os.name == "nt" else "bin")
        installed_python = executable_dir / ("python.exe" if os.name == "nt" else "python")
        run([
            str(installed_python), "-m", "pip", "install", "--no-index", "--no-deps",
            str(wheel_files[0]),
        ])
        probe = (
            "import importlib.metadata, json, viper; "
            "print(json.dumps({'metadata': importlib.metadata.version("
            + repr(project["name"])
            + "), 'runtime': viper.VERSION, 'module': viper.__file__}))"
        )
        installed = json.loads(run([str(installed_python), "-I", "-c", probe]).stdout)
        if installed["metadata"] != expected_version or installed["runtime"] != expected_version:
            raise RuntimeError(f"installed version disagreement: {installed!r}")
        if not Path(installed["module"]).resolve().is_relative_to(installed_environment.resolve()):
            raise RuntimeError(f"imported module outside isolated installation: {installed!r}")

        target = work / "existing.txt"
        target.write_text("package check\n", encoding="utf-8")
        for alias in ("hidden-viper", "viper"):
            executable = executable_dir / (alias + (".exe" if os.name == "nt" else ""))
            if run([str(executable), "--version"]).stdout.strip() != expected_version:
                raise RuntimeError(f"{alias} version does not match package metadata")
            for expected, status in (("false", "UNVERIFIED"), (True, "VERIFIED")):
                claim_file = work / "claim.json"
                claim_file.write_text(json.dumps({
                    "kind": "file_exists", "target": str(target), "expected": expected,
                }), encoding="utf-8")
                result = run([str(executable), "verify", str(claim_file)], expected_code=None)
                receipt = json.loads(result.stdout)
                if receipt["status"] != status or receipt["hiddenViperVersion"] != expected_version:
                    raise RuntimeError(f"{alias} returned unexpected receipt: {receipt!r}")
                if (result.returncode == 0) != (status == "VERIFIED"):
                    raise RuntimeError(f"{alias} returned unexpected exit {result.returncode} for {status}")

        print(f"PASS: installed {expected_version} metadata, runtime, both aliases and boolean regression.")


if __name__ == "__main__":
    main()
