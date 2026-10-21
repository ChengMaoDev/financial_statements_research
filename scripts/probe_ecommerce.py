"""探测电商平台公开页面可抓取性，不做长期采集。

仅用于验证哪些平台能在无登录、无反爬绕过的条件下取到公开销量展示值。
结果写入探测报告，不写入任何销量数据——平台展示值口径不可靠，不能当真实销量。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

TARGETS = [
    ("京东搜索", "https://search.jd.com/Search?keyword=%E7%A9%BA%E8%B0%83"),
    ("京东商品页", "https://item.jd.com/100012043978.html"),
    ("天猫搜索", "https://list.tmall.com/search_product.htm?q=%E7%A9%BA%E8%B0%83"),
    ("苏宁搜索", "https://search.suning.com/%E7%A9%BA%E8%B0%83/"),
    ("拼多多", "https://mobile.yangkeduo.com/search_result.html?search_key=%E7%A9%BA%E8%B0%83"),
]


def probe(name: str, url: str) -> dict[str, object]:
    try:
        response = requests.get(url, headers=UA, timeout=15, allow_redirects=True)
        body = response.text
        markers = {
            "登录拦截": any(k in body for k in ("请登录", "passport", "login")),
            "验证码": any(k in body for k in ("验证码", "captcha", "安全验证")),
            "风控": any(k in body for k in ("安全检测", "风控", "访问受限")),
        }
        return {
            "平台": name,
            "状态码": response.status_code,
            "字节": len(body),
            "跳转": response.url != url,
            "拦截特征": [k for k, v in markers.items() if v],
            "可抓取": response.ok and len(body) > 50_000 and not any(markers.values()),
        }
    except Exception as error:  # 探测失败需记录
        return {"平台": name, "错误": str(error)[:100], "可抓取": False}


def main() -> int:
    results = [probe(name, url) for name, url in TARGETS]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    output = ROOT / "市场数据" / "电商可抓取性探测.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
