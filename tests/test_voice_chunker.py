"""Sentence chunking for spoken replies: fast first chunk, no cuts inside numbers or abbreviations."""
from star.voice.chunker import SentenceChunker, speakable


def stream(text, size=1, **kwargs):
    chunker = SentenceChunker(**kwargs)
    out = []
    for i in range(0, len(text), size):
        out += chunker.feed(text[i:i + size])
    return out + chunker.flush()


def test_first_sentence_is_released_the_moment_its_full_stop_arrives():
    chunker = SentenceChunker()
    assert chunker.feed("Oh, well") == []
    assert chunker.feed(" done.") == ["Oh, well done."]          # no look-ahead needed for the first chunk
    assert chunker.feed(" You fixed it.") == []                   # later chunks wait for the next character
    assert chunker.feed(" That") == ["You fixed it."]
    assert chunker.flush() == ["That"]


def test_same_chunks_whatever_the_token_size():
    text = "Okay, I hear you. That sounds like a long day, love. Shall we look at it together?"
    expected = ["Okay, I hear you.", "That sounds like a long day, love.", "Shall we look at it together?"]
    for size in (1, 3, 7, 200):
        assert stream(text, size) == expected


def test_numbers_abbreviations_and_file_names_are_not_cut():
    assert stream("It costs 3.5 dollars today. Fine.") == ["It costs 3.5 dollars today.", "Fine."]
    assert stream("Ask Dr. Lee about it. Okay?") == ["Ask Dr. Lee about it.", "Okay?"]
    assert stream("Use a loop, e.g. a for loop. Easy.") == ["Use a loop, e.g. a for loop.", "Easy."]
    assert stream("Okay. Open main.py first. Then run it.") == ["Okay.", "Open main.py first.", "Then run it."]
    chunker = SentenceChunker()
    assert chunker.feed("That is version 2.") == []               # could still become 2.5
    assert chunker.feed("5 of it.") == ["That is version 2.5 of it."]


def test_question_and_exclamation_marks_end_sentences_with_closers():
    assert stream('Okay. She said "really?!" Then she laughed. Good!') == [
        "Okay.", 'She said "really?!"', "Then she laughed.", "Good!"]
    assert stream("Hmm. Wait... are you sure? Yes.") == ["Hmm.", "Wait...", "are you sure?", "Yes."]
    assert stream("Really? Yes!", 200) == ["Really?", "Yes!"]


def test_long_opening_sentence_is_split_at_a_clause_so_speech_starts_early():
    chunker = SentenceChunker(first_clause_words=4)
    text = "Before we start on the new feature, let's look at what you built yesterday and tidy it."
    out = []
    for word in text.split(" "):
        out += chunker.feed(word + " ")
        if out:
            break
    assert out == ["Before we start on the new feature,"]
    # a short "Oh," is not worth a chunk of its own
    assert SentenceChunker().feed("Oh, honey, that is ") == []
    assert SentenceChunker(first_clause_words=0).feed(text[:60]) == []


def test_run_on_text_is_force_split_and_newlines_end_chunks():
    words = " ".join(["word"] * 120)
    chunks = stream(words, 50, max_chars=100)
    assert len(chunks) >= 5 and all(len(c) <= 100 for c in chunks)
    assert " ".join(chunks) == words
    assert stream("First line\nSecond line") == ["First line", "Second line"]


def test_markup_emoji_and_stage_directions_are_never_spoken():
    assert speakable("**Well done!** 🎉 *smiles* You did it 😊") == "Well done! You did it"
    assert speakable("See [the docs](https://example.com/x) or https://example.com/y") == "See the docs or a link"
    assert speakable("# Plan\n- first step\n2. second step") == "Plan first step second step"
    assert stream("Sure. ```lua\nprint('hi')\n``` Done.") == ["Sure.", "I've put the code on screen for you. Done."]
    assert stream("<think>secret plan. really.</think>Hello there. Bye.") == ["Hello there.", "Bye."]
    assert stream("... !!! ") == []
