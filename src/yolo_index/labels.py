from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LabelAlias:
    alias: str
    label: str
    language: str = "zh-CN"


LABEL_ZH: dict[str, str] = {
    "person": "\u4eba",
    "cat": "\u732b",
    "dog": "\u72d7",
    "car": "\u6c7d\u8f66",
    "bus": "\u516c\u4ea4\u8f66",
    "truck": "\u5361\u8f66",
    "bicycle": "\u81ea\u884c\u8f66",
    "motorcycle": "\u6469\u6258\u8f66",
    "laptop": "\u7b14\u8bb0\u672c\u7535\u8111",
    "keyboard": "\u952e\u76d8",
    "mouse": "\u9f20\u6807",
    "tv": "\u7535\u89c6",
    "cell phone": "\u624b\u673a",
    "chair": "\u6905\u5b50",
    "book": "\u4e66",
    "cup": "\u676f\u5b50",
    "bottle": "\u74f6\u5b50",
    "backpack": "\u80cc\u5305",
    "stop sign": "\u505c\u6b62\u6807\u5fd7",
    "kite": "\u98ce\u7b5d",
}


ALIASES: tuple[LabelAlias, ...] = (
    LabelAlias("\u4eba", "person"),
    LabelAlias("\u4eba\u7269", "person"),
    LabelAlias("\u4eba\u50cf", "person"),
    LabelAlias("\u884c\u4eba", "person"),
    LabelAlias("\u6709\u4eba", "person"),
    LabelAlias("\u6709\u4eba\u7684", "person"),
    LabelAlias("\u6709\u4eba\u7269", "person"),
    LabelAlias("\u4eba\u7684\u7167\u7247", "person"),
    LabelAlias("\u4eba\u7269\u7167\u7247", "person"),
    LabelAlias("person", "person", "en"),
    LabelAlias("people", "person", "en"),
    LabelAlias("human", "person", "en"),
    LabelAlias("portrait", "person", "en"),
    LabelAlias("\u732b", "cat"),
    LabelAlias("\u732b\u54aa", "cat"),
    LabelAlias("cat", "cat", "en"),
    LabelAlias("\u72d7", "dog"),
    LabelAlias("\u72d7\u72d7", "dog"),
    LabelAlias("dog", "dog", "en"),
    LabelAlias("\u8f66", "car"),
    LabelAlias("\u6c7d\u8f66", "car"),
    LabelAlias("\u8f7f\u8f66", "car"),
    LabelAlias("\u5c0f\u6c7d\u8f66", "car"),
    LabelAlias("car", "car", "en"),
    LabelAlias("\u516c\u4ea4", "bus"),
    LabelAlias("\u516c\u4ea4\u8f66", "bus"),
    LabelAlias("\u5df4\u58eb", "bus"),
    LabelAlias("bus", "bus", "en"),
    LabelAlias("\u5361\u8f66", "truck"),
    LabelAlias("\u8d27\u8f66", "truck"),
    LabelAlias("truck", "truck", "en"),
    LabelAlias("\u81ea\u884c\u8f66", "bicycle"),
    LabelAlias("\u5355\u8f66", "bicycle"),
    LabelAlias("bicycle", "bicycle", "en"),
    LabelAlias("\u6469\u6258", "motorcycle"),
    LabelAlias("\u6469\u6258\u8f66", "motorcycle"),
    LabelAlias("motorcycle", "motorcycle", "en"),
    LabelAlias("\u7b14\u8bb0\u672c", "laptop"),
    LabelAlias("\u7b14\u8bb0\u672c\u7535\u8111", "laptop"),
    LabelAlias("\u7535\u8111", "laptop"),
    LabelAlias("\u624b\u63d0\u7535\u8111", "laptop"),
    LabelAlias("laptop", "laptop", "en"),
    LabelAlias("computer", "laptop", "en"),
    LabelAlias("\u952e\u76d8", "keyboard"),
    LabelAlias("keyboard", "keyboard", "en"),
    LabelAlias("\u9f20\u6807", "mouse"),
    LabelAlias("mouse", "mouse", "en"),
    LabelAlias("\u7535\u89c6", "tv"),
    LabelAlias("\u663e\u793a\u5668", "tv"),
    LabelAlias("tv", "tv", "en"),
    LabelAlias("\u624b\u673a", "cell phone"),
    LabelAlias("\u7535\u8bdd", "cell phone"),
    LabelAlias("cell phone", "cell phone", "en"),
    LabelAlias("phone", "cell phone", "en"),
    LabelAlias("\u6905\u5b50", "chair"),
    LabelAlias("\u5ea7\u6905", "chair"),
    LabelAlias("chair", "chair", "en"),
    LabelAlias("\u4e66", "book"),
    LabelAlias("\u672c\u5b50", "book"),
    LabelAlias("\u4e66\u672c", "book"),
    LabelAlias("book", "book", "en"),
    LabelAlias("\u676f\u5b50", "cup"),
    LabelAlias("\u6c34\u676f", "cup"),
    LabelAlias("cup", "cup", "en"),
    LabelAlias("\u74f6\u5b50", "bottle"),
    LabelAlias("\u6c34\u74f6", "bottle"),
    LabelAlias("bottle", "bottle", "en"),
    LabelAlias("\u80cc\u5305", "backpack"),
    LabelAlias("\u5305", "backpack"),
    LabelAlias("backpack", "backpack", "en"),
    LabelAlias("\u505c\u6b62\u6807\u5fd7", "stop sign"),
    LabelAlias("stop sign", "stop sign", "en"),
    LabelAlias("\u98ce\u7b5d", "kite"),
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
