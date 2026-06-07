"""橙果玩英语 PDF 文件名 → ORT book_id 映射（图与课文分离，课文真源 books.json）。"""

from __future__ import annotations

import re

# (PDF 文件名, book_id, 显示标题)
CHENGGUO_LEVEL2: list[tuple[str, str, str]] = [
    ("2-01 The Toy's Party.pdf", "ort_the_toys_party", "The Toys' Party"),
    ("2-02 New Trainers.pdf", "ort_new_trainers", "New Trainers"),
    ("2-03 A New Dog.pdf", "ort_a_new_dog", "A New Dog"),
    ("2-04 What a Bad Dog!.pdf", "ort_what_a_bad_dog", "What a Bad Dog!"),
    ("2-05 The Go-Kart.pdf", "ort_the_go_kart", "The Go-Kart"),
    ("2-06 The Dream.pdf", "ort_the_dream", "The Dream"),
    ("2-07 Floppy's Bath.pdf", "ort_floppys_bath", "Floppy's Bath"),
    ("2-08 The Baby-sitter.pdf", "ort_the_baby_sitter", "The Baby-sitter"),
    ("2-09 The Water Fight.pdf", "ort_the_water_fight", "The Water Fight"),
    ("2-10 Kipper's Balloon.pdf", "ort_kippers_balloon", "Kipper's Balloon"),
    ("2-11 Spots.pdf", "ort_spots", "Spots"),
    ("2-12 Kipper's Birthday.pdf", "ort_kippers_birthday", "Kipper's Birthday"),
    ("2-13 Kipper's Laces.pdf", "ort_kippers_laces", "Kipper's Laces"),
    ("2-14 The Wobbly Tooth.pdf", "ort_the_wobbly_tooth", "The Wobbly Tooth"),
    ("2-15 The Foggy Day.pdf", "ort_the_foggy_day", "The Foggy Day"),
    ("2-16 Biff's Aeroplane.pdf", "ort_biffs_aeroplane", "Biff's Aeroplane"),
    ("2-17 Floppy the Hero.pdf", "ort_floppy_the_hero", "Floppy the Hero"),
    ("2-18 The Chase.pdf", "ort_the_chase", "The Chase"),
    ("2-19 The Big Egg.pdf", "ort_the_big_egg", "The Big Egg"),
    ("2-20 Poor Floppy.pdf", "ort_poor_floppy", "Poor Floppy"),
    ("2-21 Put it back.pdf", "ort_put_it_back", "Put it back"),
    ("2-22 In a bit.pdf", "ort_in_a_bit", "In a bit"),
    ("2-23 A present for Mum.pdf", "ort_a_present_for_mum", "A present for Mum"),
    ("2-24 A hole in the sand.pdf", "ort_a_hole_in_the_sand", "A hole in the sand"),
    ("2-25 Monkey Tricks.pdf", "ort_monkey_tricks", "Monkey Tricks"),
    ("2-26 Hey Presto!.pdf", "ort_hey_presto", "Hey Presto!"),
    ("2-27 It's the Weather.pdf", "ort_its_the_weather", "It's the Weather"),
    ("2-28 Naughty Children.pdf", "ort_naughty_children", "Naughty Children"),
    ("2-29 A Sinking Feeling.pdf", "ort_a_sinking_feeling", "A Sinking Feeling"),
    ("2-30 Creepy-crawly!.pdf", "ort_creepy_crawly", "Creepy-crawly!"),
    ("2-31 What is it.pdf", "ort_what_is_it", "What is it?"),
    ("2-32 the Lost Puppy.pdf", "ort_the_lost_puppy", "The Lost Puppy"),
    ("2-33 New Trees.pdf", "ort_new_trees", "New Trees"),
    ("2-34 Up and Down.pdf", "ort_up_and_down", "Up and Down"),
    ("2-35 The Little Dragon.pdf", "ort_the_little_dragon", "The Little Dragon"),
    ("2-36 The Band.pdf", "ort_the_band", "The Band"),
]

CHENGGUO_LEVEL3: list[tuple[str, str, str]] = [
    ("3-01 The Duck Race.pdf", "ort_the_duck_race", "The Duck Race"),
    ("3-02 Sniff.pdf", "ort_sniff", "Sniff"),
    ("3-03 Pond Dipping.pdf", "ort_pond_dipping", "Pond Dipping"),
    ("3-04 The Ice Rink.pdf", "ort_the_ice_rink", "The Ice Rink"),
    ("3-05 The Mud Bath.pdf", "ort_the_mud_bath", "The Mud Bath"),
    ("3-06 The Steel Band.pdf", "ort_the_steel_band", "The Steel Band"),
    ("3-07 On the Sand.pdf", "ort_on_the_sand", "On the Sand"),
    ("3-08 The Egg Hunt.pdf", "ort_the_egg_hunt", "The Egg Hunt"),
    ("3-09 Nobody Wanted to Play.pdf", "ort_nobody_wanted_to_play", "Nobody Wanted to Play"),
    ("3-10 A Cat in the Tree.pdf", "ort_a_cat_in_the_tree", "A Cat in the Tree"),
    ("3-11 The Rope Swing.pdf", "ort_the_rope_swing", "The Rope Swing"),
    ("3-12 By the Stream.pdf", "ort_by_the_stream", "By the Stream"),
]

CHENGGUO_BY_LEVEL: dict[str, list[tuple[str, str, str]]] = {
    "2": CHENGGUO_LEVEL2,
    "3": CHENGGUO_LEVEL3,
}

# 爱贝亲子网 ORT L2 中文指导 aid（人工校对：≠ 橙果 2-XX 序号）
IBEI_LEVEL2_AIDS: dict[str, int] = {
    "ort_the_toys_party": 31049,
    "ort_new_trainers": 31050,
    "ort_a_new_dog": 31051,
    "ort_what_a_bad_dog": 31052,
    "ort_the_go_kart": 31053,
    "ort_the_dream": 31055,
    "ort_floppys_bath": 31057,
    "ort_the_baby_sitter": 31058,
    "ort_the_water_fight": 31059,
    "ort_kippers_balloon": 31060,
    "ort_spots": 31063,
    "ort_kippers_birthday": 31064,
    "ort_kippers_laces": 31065,
    "ort_the_wobbly_tooth": 31066,
    "ort_the_foggy_day": 31068,
    "ort_biffs_aeroplane": 31069,
    "ort_floppy_the_hero": 31070,
    "ort_the_big_egg": 31074,
    "ort_a_present_for_mum": 31087,
}


def pdf_map_for_level(level: str) -> list[tuple[str, str]]:
    """Return [(pdf_filename, book_id), ...] for extract script."""
    rows = CHENGGUO_BY_LEVEL.get(level) or []
    return [(pdf, bid) for pdf, bid, _title in rows]
