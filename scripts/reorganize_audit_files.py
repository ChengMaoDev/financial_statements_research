"""将近期审计成果归入审计研究，保存迁移清单及移动前哈希。

仅移动列明路径，目标存在即拒绝覆盖；原始证据及检索响应不改写。
历史JSON中的旧路径可按迁移清单解析。CSV由原生成脚本重新生成。
--verify 检查所有迁移的PDF、JSON原件字节不变；正文及输出允许重建。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "审计研究"
MANIFEST = BASE / "中间材料/文件整理记录.json"
MOVES = {
    "原始材料/审计报告": "审计研究/中间材料/审计报告",
    "原始材料/审计机构沿革_2006-2025": "审计研究/中间材料/审计机构沿革_2006-2025",
    "原始材料/prompt_collect_audit_reports_2023-2026H1.md": "审计研究/中间材料/任务说明/prompt_collect_audit_reports_2023-2026H1.md",
    **{
        f"原始材料/{name}": f"审计研究/{name}"
        for name in (
            "三家公司近20年审计事务所及变更沿革_2006-2025.md",
            "三家公司审计机构_签字会计师与审计意见汇总_2023-2026H1.md",
            "审计报告收集说明_2023-2026H1.md",
        )
    },
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors = []
    for entry in manifest["files"]:
        path = ROOT / entry["new"]
        if not path.is_file():
            errors.append(f"迁移文件缺失：{path}")
        elif path.suffix.lower() in (".pdf", ".json") and digest(path) != entry["sha256"]:
            errors.append(f"证据字节改变：{path}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.verify or MANIFEST.exists():
        errors = verify()
        if errors:
            raise ValueError("\n".join(errors))
        print("迁移文件完整，PDF与JSON哈希全部一致")
        return
    entries = []
    for old, new in MOVES.items():
        source, target = ROOT / old, ROOT / new
        if not source.exists() or target.exists():
            raise ValueError(f"源缺失或目标已存在：{old} -> {new}")
        for path in sorted(source.rglob("*")) if source.is_dir() else [source]:
            if path.is_file():
                dest = target / path.relative_to(source) if source.is_dir() else target
                entries.append(
                    {
                        "old": path.relative_to(ROOT).as_posix(),
                        "new": dest.relative_to(ROOT).as_posix(),
                        "sha256": digest(path),
                    }
                )
    for old, new in MOVES.items():
        target = ROOT / new
        target.parent.mkdir(parents=True, exist_ok=True)
        (ROOT / old).rename(target)
    MANIFEST.write_text(
        json.dumps({"moves": MOVES, "files": entries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已移动 {len(entries)} 个文件，迁移前哈希已保存")


if __name__ == "__main__":
    main()
