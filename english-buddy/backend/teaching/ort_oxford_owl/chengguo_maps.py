"""橙果玩英语 PDF 文件名 → ORT book_id 映射（图与课文分离，课文真源 books.json）。"""

from __future__ import annotations

import os
import re
from pathlib import Path

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

CHENGGUO_LEVEL4: list[tuple[str, str, str]] = [
    ("4-01 Lucky the Goat.pdf", "ort_lucky_the_goat", "Lucky the Goat"),
    ("4-02 Adam's Car.pdf", "ort_adams_car", "Adam's Car"),
    ("4-03 Yasmin and the Flood.pdf", "ort_yasmin_and_the_flood", "Yasmin and the Flood"),
    ("4-04 Yasmin's Dress.pdf", "ort_yasmins_dress", "Yasmin's Dress"),
    ("4-05 Mosque School.pdf", "ort_mosque_school", "Mosque School"),
    ("4-06 Adam Goes Shopping.pdf", "ort_adam_goes_shopping", "Adam Goes Shopping"),
    ("4-07 House for Sale.pdf", "ort_house_for_sale", "House for Sale"),
    ("4-08 The New House.pdf", "ort_the_new_house", "The New House"),
    ("4-09 Come In!.pdf", "ort_come_in", "Come In"),
    ("4-10 The Secret Room.pdf", "ort_the_secret_room", "The Secret Room"),
    ("4-11 The Play.pdf", "ort_the_play", "The Play"),
    ("4-12 The Storm.pdf", "ort_the_storm", "The Storm"),
    ("4-13 Nobody Got Wet.pdf", "ort_nobody_got_wet", "Nobody Got Wet"),
    ("4-14 The Weather Vane.pdf", "ort_the_weather_vane", "The Weather Vane"),
    ("4-15 Poor Old Mum.pdf", "ort_poor_old_mum", "Poor Old Mum"),
    ("4-16 The Wedding.pdf", "ort_the_wedding", "The Wedding"),
    ("4-17 The Camcorder.pdf", "ort_the_camcorder", "The Camcorder"),
    ("4-18 The Balloon.pdf", "ort_the_balloon", "The Balloon"),
    ("4-19 Wet Paint.pdf", "ort_wet_paint", "Wet Paint"),
    ("4-20 Swap!.pdf", "ort_swap", "Swap!"),
    ("4-21 The Flying Elephant .pdf", "ort_the_flying_elephant", "The Flying Elephant"),
    ("4-22 The Scarf.pdf", "ort_the_scarf", "The Scarf"),
    ("4-23 The Dragon Dance.pdf", "ort_the_dragon_dance", "The Dragon Dance"),
    ("4-24 Everyone Got Wet.pdf", "ort_everyone_got_wet", "Everyone Got Wet"),
    ("4-25 Dad's Jacket.pdf", "ort_dad_s_jacket", "Dad's Jacket"),
    ("4-26 Stuck in the Mud.pdf", "ort_stuck_in_the_mud", "Stuck in the Mud"),
    ("4-27 The Den.pdf", "ort_the_den", "The Den"),
    ("4-28 Look Smart.pdf", "ort_look_smart", "Look Smart"),
    ("4-29 Tug of War.pdf", "ort_tug_of_war", "Tug of War"),
    ("4-30 An Important Case.pdf", "ort_an_important_case", "An Important Case"),
]

CHENGGUO_BY_LEVEL: dict[str, list[tuple[str, str, str]]] = {
    "2": CHENGGUO_LEVEL2,
    "3": CHENGGUO_LEVEL3,
    "4": CHENGGUO_LEVEL4,
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


def pdf_filename_for_book(book_id: str) -> str | None:
    for rows in CHENGGUO_BY_LEVEL.values():
        for pdf, bid, _title in rows:
            if bid == book_id:
                return pdf
    return None


def ort_level_for_book(book_id: str) -> str | None:
    for level, rows in CHENGGUO_BY_LEVEL.items():
        for _pdf, bid, _title in rows:
            if bid == book_id:
                return level
    return None


def chengguo_batch_dir(level: str) -> Path:
    env_key = f"ENGLISH_BUDDY_CHENGGUO_L{level}_DIR"
    default = f"~/Documents/Oxfordreadingtree/级别 ({level})【橙果玩英语】"
    return Path(os.getenv(env_key, default)).expanduser()


def resolve_chengguo_pdf(book_id: str) -> Path | None:
    pdf_name = pdf_filename_for_book(book_id)
    level = ort_level_for_book(book_id)
    if not pdf_name or not level:
        return None
    batch = chengguo_batch_dir(level)
    path = batch / pdf_name
    return path if path.is_file() else None


