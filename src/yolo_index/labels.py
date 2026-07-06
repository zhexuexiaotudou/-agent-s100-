from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LabelAlias:
    alias: str
    label: str
    language: str = "zh-CN"


LABEL_ZH: dict[str, str] = {
    "person": "人",
    "cat": "猫咪",
    "dog": "狗狗",
    "car": "汽车",
    "bus": "公交车",
    "truck": "卡车",
    "bicycle": "自行车",
    "motorcycle": "摩托车",
    "laptop": "笔记本电脑",
    "keyboard": "键盘",
    "mouse": "鼠标",
    "tv": "电视",
    "cell phone": "手机",
    "chair": "椅子",
    "book": "书",
    "cup": "杯子",
    "bottle": "瓶子",
    "backpack": "背包",
    "stop sign": "停止标志",
    "kite": "风筝",
}


ALIASES: tuple[LabelAlias, ...] = (
    LabelAlias("人", "person"),
    LabelAlias("人物", "person"),
    LabelAlias("行人", "person"),
    LabelAlias("出现人", "person"),
    LabelAlias("person", "person", "en"),
    LabelAlias("people", "person", "en"),
    LabelAlias("猫", "cat"),
    LabelAlias("猫咪", "cat"),
    LabelAlias("cat", "cat", "en"),
    LabelAlias("狗", "dog"),
    LabelAlias("狗狗", "dog"),
    LabelAlias("dog", "dog", "en"),
    LabelAlias("车", "car"),
    LabelAlias("汽车", "car"),
    LabelAlias("轿车", "car"),
    LabelAlias("小汽车", "car"),
    LabelAlias("car", "car", "en"),
    LabelAlias("公交", "bus"),
    LabelAlias("公交车", "bus"),
    LabelAlias("巴士", "bus"),
    LabelAlias("bus", "bus", "en"),
    LabelAlias("卡车", "truck"),
    LabelAlias("货车", "truck"),
    LabelAlias("truck", "truck", "en"),
    LabelAlias("自行车", "bicycle"),
    LabelAlias("单车", "bicycle"),
    LabelAlias("bicycle", "bicycle", "en"),
    LabelAlias("摩托", "motorcycle"),
    LabelAlias("摩托车", "motorcycle"),
    LabelAlias("motorcycle", "motorcycle", "en"),
    LabelAlias("笔记本", "laptop"),
    LabelAlias("笔记本电脑", "laptop"),
    LabelAlias("电脑", "laptop"),
    LabelAlias("手提电脑", "laptop"),
    LabelAlias("laptop", "laptop", "en"),
    LabelAlias("computer", "laptop", "en"),
    LabelAlias("键盘", "keyboard"),
    LabelAlias("keyboard", "keyboard", "en"),
    LabelAlias("鼠标", "mouse"),
    LabelAlias("mouse", "mouse", "en"),
    LabelAlias("电视", "tv"),
    LabelAlias("显示器", "tv"),
    LabelAlias("tv", "tv", "en"),
    LabelAlias("手机", "cell phone"),
    LabelAlias("电话", "cell phone"),
    LabelAlias("cell phone", "cell phone", "en"),
    LabelAlias("phone", "cell phone", "en"),
    LabelAlias("椅子", "chair"),
    LabelAlias("座椅", "chair"),
    LabelAlias("chair", "chair", "en"),
    LabelAlias("书", "book"),
    LabelAlias("本子", "book"),
    LabelAlias("书本", "book"),
    LabelAlias("book", "book", "en"),
    LabelAlias("杯子", "cup"),
    LabelAlias("水杯", "cup"),
    LabelAlias("cup", "cup", "en"),
    LabelAlias("瓶子", "bottle"),
    LabelAlias("水瓶", "bottle"),
    LabelAlias("bottle", "bottle", "en"),
    LabelAlias("背包", "backpack"),
    LabelAlias("包", "backpack"),
    LabelAlias("backpack", "backpack", "en"),
    LabelAlias("停止标志", "stop sign"),
    LabelAlias("stop sign", "stop sign", "en"),
    LabelAlias("风筝", "kite"),
    LabelAlias("kite", "kite", "en"),
)


def alias_rows() -> list[dict[str, str]]:
    return [{"alias": item.alias, "label": item.label, "language": item.language} for item in ALIASES]


def label_zh(label: str) -> str:
    return LABEL_ZH.get(label, label)


def labels_from_query(query: str) -> list[str]:
    text = (query or "").strip().lower()
    if not text:
        return []
    labels: list[str] = []
    for item in ALIASES:
        alias = item.alias.lower()
        if alias and alias in text and item.label not in labels:
            labels.append(item.label)
    return labels
