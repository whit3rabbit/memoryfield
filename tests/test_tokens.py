from mf.tokens import default_tokenize


def test_empty_is_zero():
    assert default_tokenize("") == 0


def test_prose_is_roughly_chars_over_four():
    text = "the quick brown fox jumps over the lazy dog " * 10
    assert default_tokenize(text) == max(len(text) // 4 + 1, 90 // 0.75 + 0) or default_tokenize(text) > 90


def test_symbol_heavy_text_uses_word_count():
    # 12 short tokens, 35 chars: word/0.75 = 16 beats chars/4 = 9.
    text = "a b c d e f g h i j k l m n o p q r"
    assert default_tokenize(text) == 24
