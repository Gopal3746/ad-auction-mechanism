from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    raw: Path
    staging: Path
    warehouse: Path
    artifacts: Path
    sql: Path

    @classmethod
    def from_root(cls, root: Path | str) -> "ProjectPaths":
        root_path = Path(root).resolve()
        return cls(
            root=root_path,
            raw=root_path / "data" / "raw",
            staging=root_path / "data" / "staging",
            warehouse=root_path / "data" / "warehouse",
            artifacts=root_path / "artifacts",
            sql=root_path / "sql",
        )

    def ensure(self) -> None:
        for path in (self.raw, self.staging, self.warehouse, self.artifacts):
            path.mkdir(parents=True, exist_ok=True)
