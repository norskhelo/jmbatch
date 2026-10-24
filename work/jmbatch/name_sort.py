"""Left-to-right character keys, with the same offline pinyin data as Android."""
from name_pinyin import GROUPS

_READINGS = {char: reading for row in GROUPS
             for reading, chars in [row.split('\t', 1)] for char in chars}


def name_key(title):
    # A tuple preserves character boundaries (e.g. 西 xi comes before 先 xian).
    # Homophones defer to the next character; complete ties retain input order.
    return tuple(_READINGS.get(char, char) for char in title.lower())
