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
VOWEL_CHARS = set("aeiouyɯɤəɛʊɔɑʌɪɝɒ")


def _is_vowel(symbol: str) -> bool:
    return symbol in {"ʂɻ̩", "sɿ"} or any(ch in VOWEL_CHARS for ch in symbol)


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


def phonemes_for_text(text: str, language: str) -> List[PhonemeToken]:
    language = language.lower()
    if not text.strip():
        raise PhonemeError("lyric is empty; OpenACE never silently substitutes 'la'")
    if language in {"zh", "zh-cn", "mandarin", "cmn"}:
        return mandarin_tokens(text)
    if language in {"en", "en-us", "en-gb", "english"}:
        return english_tokens(text)
    if language in {"ja", "jp", "japanese"}:
        return japanese_tokens(text)
    if language in {"yue", "cantonese", "zh-hk"}:
        raise PhonemeError(
            "Cantonese requires a validated Jyutping lexicon; no fallback syllable is allowed"
        )
    raise PhonemeError(f"unsupported lyric language: {language}")


def ensure_note_phonemes(note: Note, language: str) -> List[Phoneme]:
    """Populate or validate strict phonemes for a note.

    Note onset is defined as the vowel onset. Consonants therefore receive negative
    start offsets (typically -40..-90 ms) rather than pushing the vowel late.
    """
    if note.phonemes:
        if not any(p.is_vowel for p in note.phonemes):
            raise PhonemeError(f"note '{note.lyric}' has no vowel phoneme")
        return note.phonemes
    tokens = phonemes_for_text(note.lyric, language)
    consonants = [t for t in tokens if not t.is_vowel]
    vowels = [t for t in tokens if t.is_vowel]
    if not vowels:
        raise PhonemeError(f"lyric '{note.lyric}' contains no vowel phoneme")
    # Consonants are pre-onset, clamped to the ACE-like 40-90ms articulation zone.
    pre_ms = min(90.0, max(40.0, 45.0 + 7.5 * max(0, len(consonants) - 1)))
    step = pre_ms / max(1, len(consonants))
    phonemes: List[Phoneme] = []
    cursor = -pre_ms
    for token in consonants:
        phonemes.append(Phoneme(symbol=token.symbol, start_ms=cursor, duration_ms=step, is_vowel=False))
        cursor += step
    # Vowels start exactly at zero: the beat anchor is the vowel, not the consonant.
    vowel_duration = max(80.0, note.duration_ticks / 4.0)
    each = vowel_duration / len(vowels)
    for index, token in enumerate(vowels):
        phonemes.append(Phoneme(symbol=token.symbol, start_ms=index * each, duration_ms=each, is_vowel=True))
    note.phonemes = phonemes
    return phonemes


def validate_phoneme_inventory(phonemes) -> None:
    # A legitimate isolated phoneme can be 'a'; only reject a one-symbol all-vowel
    # inventory when it was supplied as the literal text placeholder "la".
    literal_placeholders = [p.symbol for p in phonemes if p.symbol.lower() == "la"]
    if literal_placeholders:
        raise PhonemeError("placeholder phoneme 'la' is forbidden")
    if any(not p.symbol.strip() for p in phonemes):
        raise PhonemeError("empty phoneme symbol")
