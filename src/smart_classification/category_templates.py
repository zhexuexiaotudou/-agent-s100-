from __future__ import annotations

from typing import Any


DEFAULT_CATEGORIES: list[tuple[str, str, str, str, dict[str, Any]]] = [
    ("cat_person_photos", "人物照片", "Person Photos", "user", {"modalities": ["image", "video"], "person_attrs": {"person_present": True}, "object_labels_any": ["person"], "title_terms_any": ["person", "people", "人物", "人像"]}),
    ("cat_white_upper", "白色上衣", "White Upper Clothing", "shirt", {"modalities": ["image", "video"], "person_attrs": {"person_present": True, "upper_color": "white"}, "title_terms_any": ["white_shirt", "white shirt", "白色上衣", "白衣"]}),
    ("cat_red_clothing", "红色衣服", "Red Clothing", "shirt", {"modalities": ["image", "video"], "person_attrs": {"upper_color": "red"}, "title_terms_any": ["red_shirt", "red shirt", "红色衣服", "红衣"]}),
    ("cat_black_clothing", "黑色衣服", "Black Clothing", "shirt", {"modalities": ["image", "video"], "person_attrs": {"upper_color": "black"}, "title_terms_any": ["black_shirt", "black shirt", "黑色衣服", "黑衣"]}),
    ("cat_pet_animal", "宠物动物", "Pets and Animals", "paw", {"modalities": ["image", "video"], "object_labels_any": ["cat", "dog"], "title_terms_any": ["cat", "dog", "pet", "猫", "狗", "宠物"]}),
    ("cat_cat_photos", "猫咪照片", "Cat Photos", "cat", {"modalities": ["image", "video"], "object_labels_any": ["cat"], "title_terms_any": ["cat", "kitten", "猫", "猫咪"]}),
    ("cat_dog_photos", "狗狗照片", "Dog Photos", "dog", {"modalities": ["image", "video"], "object_labels_any": ["dog"], "title_terms_any": ["dog", "puppy", "狗", "狗狗"]}),
    ("cat_landscape_travel", "风景旅行", "Landscape and Travel", "mountain", {"modalities": ["image", "video"], "object_labels_any": ["kite"], "title_terms_any": ["mountain", "grass", "travel", "trip", "outdoor", "风景", "旅行", "草地", "山"]}),
    ("cat_vehicle_traffic", "车辆交通", "Vehicles and Traffic", "car", {"modalities": ["image", "video"], "object_labels_any": ["car", "bus", "truck", "bicycle", "motorcycle"], "title_terms_any": ["car", "street", "vehicle", "traffic", "汽车", "车辆", "街道"]}),
    ("cat_electronics", "电子设备", "Electronics", "laptop", {"modalities": ["image", "video"], "object_labels_any": ["laptop", "keyboard", "mouse", "tv", "cell phone"], "title_terms_any": ["laptop", "desk", "computer", "phone", "电脑", "笔记本", "桌面"]}),
    ("cat_books_stationery", "书本文具", "Books and Stationery", "book", {"modalities": ["image", "document"], "object_labels_any": ["book"], "title_terms_any": ["book", "note", "paper", "stationery", "书", "笔记"]}),
    ("cat_food_party", "食物聚会", "Food and Gathering", "utensils", {"modalities": ["image", "video"], "object_labels_any": ["cup", "bottle"], "title_terms_any": ["food", "meal", "party", "dinner", "食物", "聚会", "餐"]}),
    ("cat_invoice_receipt", "票据发票", "Invoices and Receipts", "receipt", {"modalities": ["image", "document"], "title_terms_any": ["invoice", "receipt", "bill", "发票", "票据"], "ocr_terms_any": ["发票", "金额", "invoice", "amount"]}),
    ("cat_contract_docs", "合同资料", "Contracts", "file-text", {"modalities": ["document", "image"], "title_terms_any": ["contract", "agreement", "合同"], "ocr_terms_any": ["合同", "agreement"]}),
    ("cat_course_docs", "课程资料", "Course Materials", "graduation-cap", {"modalities": ["document", "video", "image"], "title_terms_any": ["course", "lesson", "assignment", "课程", "作业", "课件"]}),
    ("cat_screenshot", "截图资料", "Screenshots", "monitor", {"modalities": ["image"], "title_terms_any": ["screenshot", "screen", "截图"]}),
    ("cat_movie_video", "电影视频", "Movies and Videos", "film", {"modalities": ["video"], "title_terms_any": ["movie", "film", "show", "电影", "视频"]}),
    ("cat_music_audio", "音乐音频", "Music and Audio", "music", {"modalities": ["audio"], "title_terms_any": ["music", "song", "audio", "音乐", "歌曲", "音频"]}),
    ("cat_subtitle_video", "含字幕视频", "Videos with Subtitles", "captions", {"modalities": ["video"], "transcript_terms_any": ["meeting", "预算", "字幕", "transcript"], "title_terms_any": ["subtitle", "srt", "字幕"]}),
    ("cat_unsorted", "待整理", "To Organize", "inbox", {"modalities": ["image", "video", "audio", "document", "archive", "code", "other"]}),
]


CATEGORY_PRIORITY = [item[1] for item in DEFAULT_CATEGORIES]
