from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


IGNORED_DIRECTORIES = {
    ".git", ".idea", ".next", ".pytest_cache", ".tox", ".venv", ".vscode",
    "build", "coverage", "dist", "node_modules", "out", "target", "venv",
}

MANIFEST_TECHNOLOGIES = {
    "pom.xml": "Maven / Java",
    "build.gradle": "Gradle / Java",
    "build.gradle.kts": "Gradle / Kotlin",
    "package.json": "Node.js / JavaScript",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
    "docker-compose.yaml": "Docker Compose",
}


@dataclass(frozen=True)
class RepositoryReport:
    root: Path
    file_count: int
    directory_count: int
    extensions: dict[str, int]
    technologies: tuple[str, ...]
    manifests: tuple[str, ...]
    components: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "file_count": self.file_count,
            "directory_count": self.directory_count,
            "extensions": self.extensions,
            "technologies": list(self.technologies),
            "manifests": list(self.manifests),
            "components": list(self.components),
        }

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2) + "\n"

    def as_markdown(self) -> str:
        technology_lines = "\n".join(f"- {item}" for item in self.technologies) or "- Not detected"
        manifest_lines = "\n".join(f"- `{item}`" for item in self.manifests) or "- None detected"
        component_lines = "\n".join(f"- `{item}`" for item in self.components) or "- Single root component"
        extension_lines = "\n".join(
            f"| `{extension}` | {count} |" for extension, count in self.extensions.items()
        ) or "| (no extension) | 0 |"
        return (
            "# Repository Breakdown\n\n"
            f"Root: `{self.root}`\n\n"
            f"Files: **{self.file_count}**  \nDirectories: **{self.directory_count}**\n\n"
            "## Detected technologies\n\n"
            f"{technology_lines}\n\n"
            "## Manifests\n\n"
            f"{manifest_lines}\n\n"
            "## Top-level components\n\n"
            f"{component_lines}\n\n"
            "## File types\n\n"
            "| Extension | Files |\n|---|---:|\n"
            f"{extension_lines}\n"
        )


class RepositoryAnalyzer:
    """Create a deterministic, bounded structural inventory without parsing source contents."""

    def __init__(self, max_files: int = 100_000) -> None:
        if max_files < 1:
            raise ValueError("max_files must be positive")
        self.max_files = max_files

    def analyze(self, root: Path) -> RepositoryReport:
        root = root.resolve()
        if not root.is_dir():
            raise NotADirectoryError(root)

        files: list[Path] = []
        directories: set[Path] = set()
        for candidate in sorted(root.rglob("*")):
            relative = candidate.relative_to(root)
            if any(part in IGNORED_DIRECTORIES for part in relative.parts):
                continue
            if candidate.is_dir():
                directories.add(relative)
                continue
            if candidate.is_file():
                files.append(relative)
                if len(files) > self.max_files:
                    raise ValueError(f"repository exceeds max_files={self.max_files}")

        manifests = tuple(str(path) for path in files if path.name in MANIFEST_TECHNOLOGIES)
        technologies = tuple(sorted({MANIFEST_TECHNOLOGIES[Path(path).name] for path in manifests}))
        extensions = Counter(path.suffix.lower() or "[none]" for path in files)
        components = tuple(sorted({path.parts[0] for path in files if len(path.parts) > 1}))
        return RepositoryReport(
            root=root,
            file_count=len(files),
            directory_count=len(directories),
            extensions=dict(sorted(extensions.items(), key=lambda item: (-item[1], item[0]))[:25]),
            technologies=technologies,
            manifests=manifests,
            components=components,
        )
