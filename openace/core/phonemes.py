from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import List

from pypinyin import Style, lazy_pinyin

from .models import Note, Phoneme


class PhonemeError(ValueError):
    pass


@dataclass(frozen=True)
class PhonemeToken:
    symbol: str
    is_vowel: bool = False


ZH_INITIALS = {
    "b": "p", "p": "pʰ", "m": "m", "f": "f",
    "d": "t", "t": "tʰ", "n": "n", "l": "l",
    "g": "k", "k": "kʰ", "h": "x",
    "j": "tɕ", "q": "tɕʰ", "x": "ɕ",
    "zh": "ʈʂ", "ch": "ʈʂʰ", "sh": "ʂ", "r": "ɻ",
    "z": "ts", "c": "tsʰ", "s": "s",
}

# Finals are represented in a compact IPA-like inventory understood by OpenACE's
# score payload. The engine adapter may translate them to the exact phoneset of a
# given checkpoint, but unknown input is never replaced with a placeholder vowel.
ZH_FINALS = {
    "a": "a", "o": "o", "e": "ɤ", "i": "i", "u": "u", "v": "y", "ü": "y",
    "ai": "ai", "ei": "ei", "ao": "au", "ou": "ou",
    "an": "an", "en": "ən", "ang": "aŋ", "eng": "əŋ", "ong": "ʊŋ",
    "ia": "ia", "ie": "iɛ", "iao": "iau", "iu": "iou", "iou": "iou",
    "ian": "iɛn", "in": "in", "iang": "iaŋ", "ing": "iŋ", "iong": "iʊŋ",
    "ua": "ua", "uo": "uo", "uai": "uai", "ui": "uei", "uei": "uei",
    "uan": "uan", "un": "uən", "uang": "uaŋ", "ueng": "uəŋ",
    "ve": "yɛ", "ue": "yɛ", "van": "yɛn", "vn": "yn", "er": "aɻ",
}

ZERO_INITIAL_SYLLABLES = {
    "yi": "i", "yin": "in", "ying": "ing", "ya": "ia", "ye": "ie", "yao": "iao",
    "you": "iou", "yan": "ian", "yang": "iang", "yong": "iong",
    "wu": "u", "wa": "ua", "wo": "uo", "wai": "uai", "wei": "uei",
    "wan": "uan", "wen": "un", "wang": "uang", "weng": "ueng",
    "yu": "v", "yue": "ve", "yuan": "van", "yun": "vn",
}

APICAL_SYLLABLES = {"zhi", "chi", "shi", "ri", "zi", "ci", "si"}

EN_LEXICON = {
    "a": ["ə"], "i": ["aɪ"], "you": ["j", "u"], "the": ["ð", "ə"],
    "love": ["l", "ʌ", "v"], "me": ["m", "i"], "we": ["w", "i"],
    "hello": ["h", "ə", "l", "oʊ"], "world": ["w", "ɝ", "l", "d"],
    "sing": ["s", "ɪ", "ŋ"], "song": ["s", "ɔ", "ŋ"], "star": ["s", "t", "ɑ", "r"],
    "sky": ["s", "k", "aɪ"], "dream": ["d", "r", "i", "m"],
    "heart": ["h", "ɑ", "r", "t"], "time": ["t", "aɪ", "m"],
    "light": ["l", "aɪ", "t"], "night": ["n", "aɪ", "t"],
    "forever": ["f", "ɔ", "r", "ɛ", "v", "ɝ"], "moon": ["m", "u", "n"],
}

KANA_ROMAJI = {
    "a": ["a"], "i": ["i"], "u": ["ɯ"], "e": ["e"], "o": ["o"],
    "ka": ["k", "a"], "ki": ["k", "i"], "ku": ["k", "ɯ"], "ke": ["k", "e"], "ko": ["k", "o"],
    "sa": ["s", "a"], "shi": ["ɕ", "i"], "su": ["s", "ɯ"], "se": ["s", "e"], "so": ["s", "o"],
    "ta": ["t", "a"], "chi": ["tɕ", "i"], "tsu": ["ts", "ɯ"], "te": ["t", "e"], "to": ["t", "o"],
    "na": ["n", "a"], "ni": ["n", "i"], "nu": ["n", "ɯ"], "ne": ["n", "e"], "no": ["n", "o"],
    "ha": ["h", "a"], "hi": ["ç", "i"], "fu": ["ɸ", "ɯ"], "he": ["h", "e"], "ho": ["h", "o"],
    "ma": ["m", "a"], "mi": ["m", "i"], "mu": ["m", "ɯ"], "me": ["m", "e"], "mo": ["m", "o"],
    "ya": ["j", "a"], "yu": ["j", "ɯ"], "yo": ["j", "o"],
    "ra": ["ɾ", "a"], "ri": ["ɾ", "i"], "ru": ["ɾ", "ɯ"], "re": ["ɾ", "e"], "ro": ["ɾ", "o"],
    "wa": ["w", "a"], "wo": ["o"], "n": ["ɴ"],
}

VOWEL_CANONICAL = {
    "a", "e", "i", "o", "u", "y", "ɯ", "ɤ", "ə", "ɛ", "ʊ", "ɔ", "ɑ", "ʌ", "ɪ", "ɝ", "ɒ",
}
VOWEL_CHARS = set("aeiouyɯɤəɛʊɔɑʌɪɝɒɐœɵ")


def _is_vowel(symbol: str) -> bool:
    return symbol in {"ʂɻ̩", "sɿ", "m̩", "ŋ̩"} or any(ch in VOWEL_CHARS for ch in symbol)


def _is_cjk(char: str) -> bool:
    return "\u3400" <= char <= "\u9fff" or "\uf900" <= char <= "\ufaff"


def _split_pinyin(syllable: str) -> List[str]:
    syllable = syllable.lower().replace("u:", "v").replace("ü", "v")
    if syllable in APICAL_SYLLABLES:
        if syllable.startswith(("zh", "ch", "sh")):
            initial = syllable[:2]
        else:
            initial = syllable[0]
        apical = "ʂɻ̩" if syllable in {"zhi", "chi", "shi", "ri"} else "sɿ"
        return [ZH_INITIALS[initial], apical]
    if syllable in ZERO_INITIAL_SYLLABLES:
        final = ZERO_INITIAL_SYLLABLES[syllable]
        if final not in ZH_FINALS:
            raise PhonemeError(f"unsupported Mandarin final: {final}")
        return [ZH_FINALS[final]]
    initial = ""
    final = syllable
    for candidate in ("zh", "ch", "sh"):
        if syllable.startswith(candidate):
            initial = candidate
            final = syllable[len(candidate):]
            break
    if not initial and syllable and syllable[0] in ZH_INITIALS:
        # Choose the longest legal final rather than blindly treating the first letter
        # as an initial; this handles syllables such as an/ang/en/eng correctly.
        for size in range(len(syllable), 0, -1):
            possible_final = syllable[1:size] or syllable[1:]
            if syllable[0] in ZH_INITIALS and possible_final in ZH_FINALS:
                initial = syllable[0]
                final = possible_final
                break
        else:
            initial = syllable[0]
            final = syllable[1:]
    if initial and initial not in ZH_INITIALS:
        raise PhonemeError(f"unsupported Mandarin initial: {initial}")
    if final not in ZH_FINALS:
        raise PhonemeError(f"unsupported Mandarin final in syllable '{syllable}'")
    pieces = []
    if initial:
        pieces.append(ZH_INITIALS[initial])
    pieces.append(ZH_FINALS[final])
    return pieces


def mandarin_tokens(text: str) -> List[PhonemeToken]:
    tokens: List[PhonemeToken] = []
    for char in text:
        if char.isspace() or char in "，。！？、,.!?":
            continue
        if not _is_cjk(char):
            raise PhonemeError(f"Mandarin lyrics contain unsupported character '{char}'")
        pinyin = lazy_pinyin(char, style=Style.NORMAL, errors=lambda x: [])
        if not pinyin or not pinyin[0]:
            raise PhonemeError(f"no Mandarin pronunciation found for '{char}'")
        for symbol in _split_pinyin(pinyin[0]):
            tokens.append(PhonemeToken(symbol=symbol, is_vowel=_is_vowel(symbol)))
    if not tokens:
        raise PhonemeError(f"no Mandarin phonemes could be derived from '{text}'")
    return tokens


@lru_cache(maxsize=1)
def _cmudict():
    try:
        import cmudict  # type: ignore

        return cmudict.dict()
    except Exception:
        return None


def _rule_based_english(word: str) -> List[str]:
    """Small deterministic fallback for English when CMUdict is unavailable.

    It is intentionally conservative and deterministic. Production installations should
    install `cmudict` or espeak-ng; the fallback still never substitutes unknown lyrics
    with a canonical placeholder syllable.
    """
    out: List[str] = []
    i = 0
    while i < len(word):
        rest = word[i:]
        if rest.startswith("tion"):
            out.extend(["ʃ", "ən"]); i += 4
        elif rest.startswith("th"):
            out.extend(["θ"]); i += 2
        elif rest.startswith("sh"):
            out.extend(["ʃ"]); i += 2
        elif rest.startswith("ch"):
            out.extend(["tʃ"]); i += 2
        elif rest.startswith("ph"):
            out.extend(["f"]); i += 2
        elif rest.startswith("ee") or rest.startswith("ea"):
            out.extend(["i"]); i += 2
        elif rest.startswith("oo"):
            out.extend(["u"]); i += 2
        elif rest.startswith("ai") or rest.startswith("ay"):
            out.extend(["eɪ"]); i += 2
        elif rest.startswith("ow") or rest.startswith("ou"):
            out.extend(["aʊ"]); i += 2
        elif rest.startswith("oy") or rest.startswith("oi"):
            out.extend(["ɔɪ"]); i += 2
        else:
            ch = word[i]
            simple = {
                "a": "æ", "e": "ɛ", "i": "ɪ", "o": "ɑ", "u": "ʌ", "y": "j",
                "b": "b", "c": "k", "d": "d", "f": "f", "g": "g", "h": "h", "j": "dʒ",
                "k": "k", "l": "l", "m": "m", "n": "n", "p": "p", "q": "k", "r": "r",
                "s": "s", "t": "t", "v": "v", "w": "w", "x": "ks", "z": "z",
            }.get(ch)
            if simple is None:
                raise PhonemeError(f"unsupported English character '{ch}' in '{word}'")
            out.append(simple)
            i += 1
    return out


def english_tokens(text: str) -> List[PhonemeToken]:
    words = re.findall(r"[A-Za-z']+", text.lower())
    if not words:
        raise PhonemeError(f"no English words found in '{text}'")
    result: List[str] = []
    cmu = _cmudict()
    for word in words:
        if word in EN_LEXICON:
            result.extend(EN_LEXICON[word])
        elif cmu and word in cmu:
            # Strip lexical stress digits and keep ARPAbet symbols. They are stable,
            # explicitly validated, and preferable to inventing sounds.
            result.extend(re.sub(r"\d", "", phone).lower() for phone in cmu[word][0])
        else:
            result.extend(_rule_based_english(word))
    return [PhonemeToken(symbol=s, is_vowel=_is_vowel(s) or s in {"aa", "ae", "ah", "ao", "aw", "ay", "eh", "er", "ey", "ih", "iy", "ow", "oy", "uh", "uw"}) for s in result]


def japanese_tokens(text: str) -> List[PhonemeToken]:
    normalized = text.lower().strip()
    if not normalized:
        raise PhonemeError("empty Japanese lyric")
    pieces = re.findall(r"shi|chi|tsu|ka|ki|ku|ke|ko|sa|su|se|so|ta|te|to|na|ni|nu|ne|no|ha|hi|fu|he|ho|ma|mi|mu|me|mo|ya|yu|yo|ra|ri|ru|re|ro|wa|wo|[aiueon]", normalized)
    if not pieces or "".join(pieces) != normalized.replace(" ", ""):
        raise PhonemeError(f"unsupported Japanese romaji lyric '{text}'")
    symbols: List[str] = []
    for piece in pieces:
        if piece not in KANA_ROMAJI:
            raise PhonemeError(f"unsupported Japanese mora '{piece}'")
        symbols.extend(KANA_ROMAJI[piece])
    return [PhonemeToken(symbol=s, is_vowel=_is_vowel(s)) for s in symbols]


YUE_ONSETS = {
    "b": "p", "p": "pʰ", "m": "m", "f": "f",
    "d": "t", "t": "tʰ", "n": "n", "l": "l",
    "g": "k", "k": "kʰ", "ng": "ŋ", "h": "h",
    "gw": "kw", "kw": "kʰw", "w": "w",
    "z": "ts", "c": "tsʰ", "s": "s", "j": "j",
}
YUE_NUCLEI = {
    "aa": "aː", "a": "ɐ", "e": "ɛː", "i": "iː", "o": "ɔː", "u": "uː",
    "oe": "œː", "eo": "ɵ", "yu": "yː", "m": "m̩", "ng": "ŋ̩",
}
YUE_CODAS = {
    "i": "i", "u": "u", "m": "m", "n": "n", "ng": "ŋ",
    "p": "p̚", "t": "t̚", "k": "k̚",
}


def cantonese_jyutping_syllables(text: str) -> List[str]:
    """Return validated tone-bearing Jyutping syllables for Cantonese Han lyrics."""
    try:
        import pycantonese  # type: ignore
    except ImportError as exc:
        raise PhonemeError("Cantonese lyrics require the pycantonese package") from exc
    syllables: List[str] = []
    for char in text:
        if char.isspace() or char in "，。！？、,.!?":
            continue
        if not _is_cjk(char):
            raise PhonemeError(f"Cantonese lyrics contain unsupported character '{char}'")
        entries = pycantonese.characters_to_jyutping(char)
        if not entries or not entries[0][1]:
            raise PhonemeError(f"no Cantonese Jyutping pronunciation found for '{char}'")
        # Querying one character at a time avoids multiword grouping ambiguity. The
        # lexicon can still choose context-independent heteronym readings; unknown or
        # pronunciationless characters remain loud errors rather than placeholders.
        syllable = str(entries[0][1]).strip().split()[0]
        if not syllable or not syllable[-1].isdigit():
            raise PhonemeError(f"invalid tone-bearing Jyutping pronunciation for '{char}'")
        syllables.append(syllable)
    if not syllables:
        raise PhonemeError(f"no Cantonese phonemes could be derived from '{text}'")
    return syllables


def cantonese_tokens(text: str) -> List[PhonemeToken]:
    """Decompose validated Jyutping syllables into explicit Cantonese phoneme tokens."""
    try:
        import pycantonese  # type: ignore
    except ImportError as exc:
        raise PhonemeError("Cantonese lyrics require the pycantonese package") from exc
    tokens: List[PhonemeToken] = []
    for syllable in cantonese_jyutping_syllables(text):
        parsed = pycantonese.parse_jyutping(syllable)
        if not parsed:
            raise PhonemeError(f"invalid Cantonese Jyutping syllable '{syllable}'")
        unit = parsed[0]
        if unit.onset:
            if unit.onset not in YUE_ONSETS:
                raise PhonemeError(f"unsupported Cantonese onset '{unit.onset}' in '{syllable}'")
            tokens.append(PhonemeToken(YUE_ONSETS[unit.onset], is_vowel=False))
        if unit.nucleus not in YUE_NUCLEI:
            raise PhonemeError(f"unsupported Cantonese nucleus '{unit.nucleus}' in '{syllable}'")
        tokens.append(PhonemeToken(YUE_NUCLEI[unit.nucleus], is_vowel=True))
        if unit.coda:
            if unit.coda not in YUE_CODAS:
                raise PhonemeError(f"unsupported Cantonese coda '{unit.coda}' in '{syllable}'")
            tokens.append(PhonemeToken(YUE_CODAS[unit.coda], is_vowel=False))
    return tokens


def mixed_mandarin_english_tokens(text: str) -> List[PhonemeToken]:
    """Tokenize one lyric containing Mandarin Han characters and/or English words.

    Cantonese shares Han orthography with Mandarin, so automatic mixed mode is
    deliberately limited to Mandarin+English rather than pretending it can detect
    Cantonese from text alone.
    """
    pieces = re.findall(r"[\u3400-\u9fff\uf900-\ufaff]+|[A-Za-z]+(?:'[A-Za-z]+)?", text)
    if not pieces:
        if re.search(r"[\u3040-\u30ff]", text):
            raise PhonemeError("Japanese script is not supported in mixed Mandarin/English mode; choose a supported explicit language instead of silent substitution")
        raise PhonemeError(f"no Mandarin or English lyric units found in '{text}'")
    remainder = re.sub(r"[\u3400-\u9fff\uf900-\ufaff]+|[A-Za-z]+(?:'[A-Za-z]+)?|[\s，。！？、,.!?]+", "", text)
    if remainder:
        raise PhonemeError(f"mixed Mandarin/English lyrics contain unsupported character '{remainder[0]}'")
    tokens: List[PhonemeToken] = []
    for piece in pieces:
        if _is_cjk(piece[0]):
            tokens.extend(mandarin_tokens(piece))
        else:
            tokens.extend(english_tokens(piece))
    if not tokens:
        raise PhonemeError(f"no mixed-language phonemes could be derived from '{text}'")
    return tokens


def mixed_cantonese_english_tokens(text: str) -> List[PhonemeToken]:
    """Tokenize explicit Cantonese Han units mixed with English words."""
    pieces = re.findall(r"[\u3400-\u9fff\uf900-\ufaff]+|[A-Za-z]+(?:'[A-Za-z]+)?", text)
    if not pieces:
        if re.search(r"[\u3040-\u30ff]", text):
            raise PhonemeError("Japanese script is not supported in mixed Cantonese/English mode")
        raise PhonemeError(f"no Cantonese or English lyric units found in '{text}'")
    remainder = re.sub(r"[\u3400-\u9fff\uf900-\ufaff]+|[A-Za-z]+(?:'[A-Za-z]+)?|[\s，。！？、,.!?]+", "", text)
    if remainder:
        raise PhonemeError(f"mixed Cantonese/English lyrics contain unsupported character '{remainder[0]}'")
    tokens: List[PhonemeToken] = []
    for piece in pieces:
        tokens.extend(cantonese_tokens(piece) if _is_cjk(piece[0]) else english_tokens(piece))
    return tokens


def phonemes_for_text(text: str, language: str) -> List[PhonemeToken]:
    language = language.lower()
    if not text.strip():
        raise PhonemeError("lyric is empty; OpenACE never silently substitutes 'la'")
    if language in {"mixed", "multilingual", "zh-en", "en-zh"}:
        return mixed_mandarin_english_tokens(text)
    if language in {"mixed-yue", "yue-en", "en-yue", "cantonese-english"}:
        return mixed_cantonese_english_tokens(text)
    if language in {"zh", "zh-cn", "mandarin", "cmn"}:
        return mandarin_tokens(text)
    if language in {"en", "en-us", "en-gb", "english"}:
        return english_tokens(text)
    if language in {"ja", "jp", "japanese"}:
        return japanese_tokens(text)
    if language in {"yue", "cantonese", "zh-hk"}:
        return cantonese_tokens(text)
    raise PhonemeError(f"unsupported lyric language: {language}")


def tokens_from_symbols(symbols: List[str]) -> List[PhonemeToken]:
    """Build validated manual phoneme tokens from user-supplied symbols."""
    cleaned = [symbol.strip() for symbol in symbols if symbol.strip()]
    if not cleaned:
        raise PhonemeError("manual phoneme override is empty")
    if any(symbol.lower() == "la" for symbol in cleaned):
        raise PhonemeError("placeholder phoneme 'la' is forbidden")
    tokens = [PhonemeToken(symbol=symbol, is_vowel=_is_vowel(symbol)) for symbol in cleaned]
    if not any(token.is_vowel for token in tokens):
        raise PhonemeError("manual phoneme override has no vowel phoneme")
    return tokens


def timed_phonemes(tokens: List[PhonemeToken], duration_ms: float) -> List[Phoneme]:
    """Place a phoneme sequence relative to a beat-anchored first vowel.

    Only pre-vowel consonants receive negative onset times. Post-vowel consonants
    remain after the vowel instead of being incorrectly pulled before the beat.
    """
    vowel_indexes = [index for index, token in enumerate(tokens) if token.is_vowel]
    if not vowel_indexes:
        raise PhonemeError("lyric contains no vowel phoneme")
    first_vowel = vowel_indexes[0]
    pre_tokens = tokens[:first_vowel]
    post_tokens = tokens[first_vowel:]
    pre_ms = min(90.0, max(40.0, 45.0 + 7.5 * max(0, len(pre_tokens) - 1))) if pre_tokens else 0.0
    step = pre_ms / max(1, len(pre_tokens))
    phonemes: List[Phoneme] = []
    cursor = -pre_ms
    for token in pre_tokens:
        phonemes.append(Phoneme(symbol=token.symbol, start_ms=cursor, duration_ms=step, is_vowel=False))
        cursor += step

    duration_ms = max(120.0, duration_ms)
    post_consonants = [token for token in post_tokens if not token.is_vowel]
    post_vowels = [token for token in post_tokens if token.is_vowel]
    coda_each = min(70.0, max(35.0, duration_ms * 0.08))
    coda_total = coda_each * len(post_consonants)
    max_coda_total = duration_ms * 0.35
    if coda_total > max_coda_total and post_consonants:
        coda_each = max_coda_total / len(post_consonants)
        coda_total = max_coda_total
    vowel_total = duration_ms - coda_total
    vowel_each = vowel_total / len(post_vowels)
    cursor = 0.0
    for token in post_tokens:
        length = vowel_each if token.is_vowel else coda_each
        phonemes.append(Phoneme(symbol=token.symbol, start_ms=cursor, duration_ms=length, is_vowel=token.is_vowel))
        cursor += length
    validate_phoneme_inventory(phonemes)
    validate_phoneme_timing(phonemes)
    return phonemes


def ensure_note_phonemes(note: Note, language: str, duration_ms: float | None = None) -> List[Phoneme]:
    """Populate or validate strict phonemes for a note.

    Note onset is defined as the first vowel onset. Pre-vowel consonants receive
    negative offsets while post-vowel consonants remain in sequence after the vowel.
    """
    if note.phonemes:
        if not any(p.is_vowel for p in note.phonemes):
            raise PhonemeError(f"note '{note.lyric}' has no vowel phoneme")
        validate_phoneme_inventory(note.phonemes)
        validate_phoneme_timing(note.phonemes)
        return note.phonemes
    tokens = phonemes_for_text(note.lyric, language)
    if duration_ms is None:
        # Nominal 120 BPM fallback for CLI/model-unit use; server/render callers pass
        # the exact project-tempo duration whenever available.
        duration_ms = note.duration_ticks * 60000.0 / (120.0 * 480.0)
    note.phonemes = timed_phonemes(tokens, duration_ms)
    return note.phonemes


def ensure_ordered_note_phonemes(notes: List[Note], language: str, duration_ms_for_note) -> None:
    """Validate a monophonic note sequence, deriving melisma continuations truthfully.

    A '-' continuation has no new onset or coda. It sustains the final vowel of the
    nearest preceding sung lyric and is invalid before any sung lyric.
    """
    ordered = sorted(notes, key=lambda note: (note.start_ticks, note.pitch, note.id))
    sustained_vowel: str | None = None
    for note in ordered:
        lyric = note.lyric.strip()
        if lyric == "-" and not note.phonemes:
            if sustained_vowel is None:
                raise PhonemeError("melisma continuation '-' cannot appear before a sung lyric note")
            note.phonemes = timed_phonemes([PhonemeToken(symbol=sustained_vowel, is_vowel=True)], duration_ms_for_note(note))
        elif lyric:
            ensure_note_phonemes(note, language, duration_ms_for_note(note))
        vowels = [phoneme for phoneme in note.phonemes if phoneme.is_vowel]
        if vowels:
            sustained_vowel = vowels[-1].symbol


def validate_phoneme_timing(phonemes) -> None:
    """Require contiguous, positive, beat-anchored manual timing."""
    if not phonemes:
        return
    first_vowel = next((p for p in phonemes if p.is_vowel), None)
    if first_vowel is None:
        raise PhonemeError("phoneme inventory has no vowel phoneme")
    if abs(first_vowel.start_ms) > 0.75:
        raise PhonemeError("first vowel must start at 0ms to preserve the beat anchor")
    for left, right in zip(phonemes, phonemes[1:]):
        if left.duration_ms <= 0 or right.duration_ms <= 0:
            raise PhonemeError("phoneme durations must be positive")
        boundary = left.start_ms + left.duration_ms
        if abs(boundary - right.start_ms) > 0.75:
            raise PhonemeError("phonemes must be contiguous without gaps or overlaps")


def validate_phoneme_inventory(phonemes) -> None:
    # A legitimate isolated phoneme can be 'a'; only reject a one-symbol all-vowel
    # inventory when it was supplied as the literal text placeholder "la".
    literal_placeholders = [p.symbol for p in phonemes if p.symbol.lower() == "la"]
    if literal_placeholders:
        raise PhonemeError("placeholder phoneme 'la' is forbidden")
    if any(not p.symbol.strip() for p in phonemes):
        raise PhonemeError("empty phoneme symbol")
