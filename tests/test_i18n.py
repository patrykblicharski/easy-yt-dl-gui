import ast
import re
import string
from pathlib import Path

import pytest

from ytddlg import i18n
from ytddlg.config import Settings
from ytddlg.core.options import DownloadRequest, migrate_ids
from ytddlg.core.queue import State
from ytddlg.i18n_pl import PL

from i18n_keys import all_keys, literal_keys  # tests/ is on sys.path (pytest rootdir import mode)


def placeholders(s: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(s) if name}


def test_every_string_has_a_polish_translation():
    missing = sorted(all_keys() - set(PL))
    locations = literal_keys()
    assert not missing, "Missing Polish translations:\n" + "\n".join(
        f"  {k!r}  ({', '.join(locations.get(k, ['dynamic']))})" for k in missing
    )


def test_placeholders_match():
    bad = [(k, v) for k, v in PL.items() if placeholders(k) != placeholders(v)]
    assert not bad, bad


def test_no_unused_translations():
    unused = sorted(set(PL) - all_keys())
    assert not unused, f"Translations not used anywhere: {unused}"


def test_pl_source_has_no_duplicate_keys():
    src = Path(i18n.__file__).with_name("i18n_pl.py").read_text(encoding="utf-8")
    keys = [k.value for k in next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Dict)).keys]
    dups = {k for k in keys if keys.count(k) > 1}
    assert not dups, dups


def test_t_switches_language():
    try:
        i18n.set_language("pl")
        assert i18n.t("Download all") == "Pobierz wszystkie"
        assert State.DONE.label == "Gotowe"
        assert i18n.t("errors: {n}", n=3) == "błędy: 3"
        i18n.set_language("en")
        assert i18n.t("Download all") == "Download all"
        assert State.DONE.label == "Done"
        assert i18n.t("not a key") == "not a key"
    finally:
        i18n.set_language("en")


def test_unknown_language_falls_back_to_detection():
    try:
        assert i18n.set_language("xx") in i18n.LANGUAGES
    finally:
        i18n.set_language("en")


@pytest.mark.parametrize("lang", ["pl", "en"])
def test_request_label_has_no_raw_ids(lang):
    try:
        i18n.set_language(lang)
        label = DownloadRequest("u", Path("."), video_quality="best").label()
        assert "best" not in label
    finally:
        i18n.set_language("en")


def test_legacy_polish_settings_are_migrated(tmp_path):
    f = tmp_path / "settings.json"
    f.write_text(
        '{"video_quality": "1080p", "audio_format": "Oryginał (bez rekompresji)", '
        '"audio_quality": "320 kb/s", "appearance": "Dark"}',
        encoding="utf-8",
    )
    s = Settings.load(f)
    assert (s.video_quality, s.audio_format, s.audio_quality, s.appearance) == ("1080", "best", "320K", "Dark")


def test_legacy_queue_request_is_migrated():
    req = DownloadRequest.from_dict({"url": "u", "out_dir": ".", "mode": "audio", "audio_format": "MP3",
                                     "audio_quality": "Najlepsza (VBR)", "video_quality": "Najlepsza"})
    assert (req.audio_format, req.audio_quality, req.video_quality) == ("mp3", "0", "best")
    assert migrate_ids({"video_quality": "720"}) == {"video_quality": "720"}  # ids stay untouched


def test_no_polish_literals_left_in_code():
    """User-facing Polish text belongs in i18n_pl.py only."""
    pkg = Path(i18n.__file__).parent
    pl_chars = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
    offenders = []
    for path in pkg.rglob("*.py"):
        if path.name == "i18n_pl.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and pl_chars.search(node.value):
                offenders.append(f"{path.name}:{node.lineno}: {node.value[:50]!r}")
    # options.py keeps the legacy Polish labels for migrating old settings (LEGACY_IDS)
    offenders = [o for o in offenders if o.split(":")[0] != "options.py"]
    assert not offenders, "\n".join(offenders)
