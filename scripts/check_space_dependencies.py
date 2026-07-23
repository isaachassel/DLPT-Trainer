#!/usr/bin/env python3
"""Validate repository pins against the Gradio Space extras dependency metadata."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, requires
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"


def pinned_versions(path: Path = REQUIREMENTS) -> dict[str, Version]:
    pins: dict[str, Version] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-r "):
            continue
        requirement = Requirement(line)
        exact = [spec.version for spec in requirement.specifier if spec.operator == "=="]
        if len(exact) != 1:
            raise RuntimeError(f"{requirement.name} must have one exact == pin in requirements.txt")
        pins[requirement.name.lower().replace("_", "-")] = Version(exact[0])
    return pins


def applicable_gradio_requirements(extra: str) -> list[Requirement]:
    try:
        raw_requirements = requires("gradio") or []
    except PackageNotFoundError as exc:
        raise RuntimeError("Gradio must be installed to verify its dependency metadata") from exc

    environment = default_environment()
    environment["extra"] = extra
    parsed: list[Requirement] = []
    for raw in raw_requirements:
        requirement = Requirement(raw)
        if requirement.marker is None or requirement.marker.evaluate(environment):
            parsed.append(requirement)
    return parsed


def validate() -> list[str]:
    pins = pinned_versions()
    errors: list[str] = []

    for extra in ("", "oauth", "mcp"):
        label = extra or "base"
        for requirement in applicable_gradio_requirements(extra):
            normalized = requirement.name.lower().replace("_", "-")
            version = pins.get(normalized)
            if version is None or not requirement.specifier:
                continue
            if version not in requirement.specifier:
                errors.append(
                    f"{normalized}=={version} conflicts with gradio[{label}] "
                    f"requirement {requirement.specifier}"
                )

    pydantic_version = pins.get("pydantic")
    if pydantic_version != Version("2.12.5"):
        errors.append(
            "Gradio 6.5.1's MCP extra requires Pydantic 2.11.10 through 2.12.5; "
            f"repository pins {pydantic_version or 'nothing'}"
        )
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("SPACE DEPENDENCY VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    pins = pinned_versions()
    print("SPACE DEPENDENCY VALIDATION PASSED")
    print(f"- Gradio: {pins['gradio']}")
    print(f"- Pydantic: {pins['pydantic']} (compatible with gradio[mcp,oauth])")
    print(f"- Hugging Face Hub: {pins['huggingface-hub']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
