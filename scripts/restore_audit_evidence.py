"""恢复Git换行转换过的审计证据，严格匹配已有SHA-256才允许写入。

迁移JSON和经济导报网页原为CRLF；国卫网页原为混合换行，其中24行CRLF，
位置已通过官网响应核对。只改变换行字节，不改内容或记录的哈希。
默认只检查；--apply恢复文件。未知内容变化、未知换行形式一律报错。
恢复完成后，.gitattributes的-text确保后续Git检出不再转换这些原件。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reorganize_audit_files import MANIFEST, ROOT

AFRC_CRLF_LINES = frozenset((*range(89, 96), *range(820, 837)))


def original_bytes(data: bytes, expected: str, *, afrc: bool = False) -> bytes:
    if hashlib.sha256(data).hexdigest() == expected:
        return data
    lf = data.replace(b"\r\n", b"\n")
    if afrc:
        candidate = b"".join(
            line[:-1] + b"\r\n" if i in AFRC_CRLF_LINES and line.endswith(b"\n") else line
            for i, line in enumerate(lf.splitlines(keepends=True), 1)
        )
    else:
        candidate = lf.replace(b"\n", b"\r\n")
    if hashlib.sha256(candidate).hexdigest() != expected:
        raise ValueError("内容或换行布局与原始SHA-256不符，拒绝恢复")
    return candidate


def restore(*, apply: bool = False) -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    targets = [
        (ROOT / entry["new"], entry["sha256"], False)
        for entry in manifest["files"]
        if Path(entry["new"]).suffix.lower() in {".json", ".pdf"}
    ]
    folder = ROOT / "审计研究/中间材料/审计报告/事务所评价来源"
    for name in ("和信青岛中程处罚经济导报报道.html", "国卫20260903香港会财局处分.html"):
        path = folder / name
        meta = json.loads(path.with_suffix(".html.json").read_text(encoding="utf-8"))
        targets.append((path, meta["sha256"], name.startswith("国卫")))
    pending: list[tuple[Path, bytes]] = []
    for path, expected, afrc in targets:
        data = path.read_bytes()
        try:
            restored = original_bytes(data, expected, afrc=afrc)
        except ValueError as exc:
            raise ValueError(f"{path.relative_to(ROOT)}：{exc}") from exc
        if restored != data:
            pending.append((path, restored))
    if apply:
        for path, restored in pending:
            path.write_bytes(restored)
    print(f"原始哈希核对 {len(targets)} 份；{'已恢复' if apply else '待恢复'} {len(pending)} 份")
    return len(pending)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    restore(apply=parser.parse_args().apply)
