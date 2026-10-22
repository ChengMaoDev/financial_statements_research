"""从现有商品标题与 ID 补充可追溯字段，不估计缺失规格和真实销量。

容量、匹数、能效只保留标题原文匹配；多个值全部保留，不挑选最低规格。
商品状态和样本类型是标题规则标记，不能代替商品详情确认。
"""

from __future__ import annotations

import re

FIELDS = ["商品链接", "匹数_标题", "容量_标题", "能效_标题", "商品状态_标题", "样本类型_标题"]


def matches(pattern: str, title: str) -> str:
    return ";".join(dict.fromkeys(re.findall(pattern, title, re.IGNORECASE)))


def enrich(platform: str, item_id: str, title: str) -> list[str]:
    links = {
        "jd": f"https://item.jd.com/{item_id}.html",
        "taobao": f"https://item.taobao.com/item.htm?id={item_id}",
        "pdd": f"https://mobile.yangkeduo.com/goods.html?goods_id={item_id}",
    }
    state = matches(r"二手|箱损|尾货|样机|瑕疵|99新|9成新|九成新", title)
    sample = (
        "配件/耗材"
        if re.search(
            r"专属配件|外罩|布罩配件|洗碗粉|洗碗块|洗碗盐|洗涤剂|漂洗剂|光亮剂|排水管|滤芯", title
        )
        else "布罩/便携烘干"
        if re.search(r"布罩|暖风干衣|干衣衣柜|折叠烘干|便携干衣", title)
        else "套装"
        if re.search(r"套装|套系|洗烘套|烟灶套", title)
        else "未判定"
    )
    return [
        links[platform] if item_id else "",
        matches(r"大?(?:\d+(?:\.\d+)?|[一二三四五两])\s*匹", title),
        matches(r"\d+(?:\.\d+)?(?:\s*[/+]\s*\d+(?:\.\d+)?)*\s*(?:升|公斤|kg|L)(?![A-Za-z])", title),
        matches(r"[一二三四五12345]级能效", title),
        state,
        sample,
    ]
