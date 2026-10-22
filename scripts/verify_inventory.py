"""全库 CSV 清单与结构核验；--write 登记一次经审阅的数据快照。

清单保存精确表头、行数、SHA256 与原始重复行数；文件缺失、意外新增、重复列、
错列、非有限数值以及已登记快照的内容变化均返回失败。哈希只证明快照未变，
不证明数据真实；具体一手覆盖范围见原文交叉核验.csv 与 README.md。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import TypedDict

from research_scope import DATE_FIELDS, in_scope

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "数据清单.json"
FOLDERS = ("财务数据", "市场数据", "定期报告")


class Snapshot(TypedDict):
    columns: list[str]
    rows: int
    sha256: str
    duplicate_rows: int


def snapshot(path: Path) -> Snapshot:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        empty_header: list[str] = []
        header = next(reader, empty_header)
        if not header or any(not name for name in header) or len(set(header)) != len(header):
            raise ValueError(f"{path.name} 表头为空或含重复字段")
        date_column = next((header.index(field) for field in DATE_FIELDS if field in header), None)
        seen: set[tuple[str, ...]] = set()
        count = duplicates = 0
        for line, row in enumerate(reader, 2):
            if len(row) != len(header):
                raise ValueError(f"{path.name}:{line} 列数 {len(row)} ≠ {len(header)}")
            if date_column is not None and not in_scope(row[date_column]):
                raise ValueError(f"{path.name}:{line} 超出2023—2026范围：{row[date_column]}")
            for field in row:
                try:
                    value = float(field)
                except ValueError:
                    continue
                if not math.isfinite(value):
                    raise ValueError(f"{path.name}:{line} 含非有限数值 {field}")
            identity = tuple(row)
            duplicates += identity in seen
            seen.add(identity)
            count += 1
    if not count:
        raise ValueError(f"{path.name} 没有数据行")
    return Snapshot(
        columns=header,
        rows=count,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        duplicate_rows=duplicates,
    )


def collect(root: Path) -> dict[str, Snapshot]:
    return {
        path.relative_to(root).as_posix(): snapshot(path)
        for folder in FOLDERS
        for path in sorted((root / folder).rglob("*.csv"))
    }


def verify(root: Path = ROOT) -> tuple[int, int]:
    path = root / MANIFEST.name
    try:
        expected = json.loads(path.read_text(encoding="utf-8"))
        actual = collect(root)
    except (OSError, ValueError, csv.Error) as exc:
        print(f"全库清单失败：{exc}")
        return 0, 1
    passed = failed = 0
    for name in sorted(expected.keys() | actual.keys()):
        ok = expected.get(name) == actual.get(name)
        passed += ok
        failed += not ok
        if not ok:
            print(f"    清单不符：{name}（缺失、新增或内容变化；不得自动覆盖清单以绕过审阅）")
    print(
        f"全库 CSV：{len(actual)} 张，{sum(item['rows'] for item in actual.values())} 行；通过 {passed}，失败 {failed}"
    )
    return passed, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="经审阅后重新登记数据快照")
    args = parser.parse_args()
    if args.write:
        MANIFEST.write_text(
            json.dumps(collect(ROOT), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"写入 {MANIFEST.name}")
    return int(verify()[1] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
