"""Polish translations (English source string -> Polish).

tests/test_i18n.py checks that every string used in the code has an entry here
and that the {placeholders} match.
"""

PL: dict[str, str] = {
    # --- main window ---------------------------------------------------------------
    "Settings": "Ustawienia",
    "System": "System",
    "Dark": "Ciemny",
    "Light": "Jasny",
    "Paste a link to a YouTube video, playlist or channel…": "Wklej link do filmu, playlisty albo kanału YouTube…",
    "Paste": "Wklej",
    "Analyze": "Analizuj",
    "No link analysed yet": "Brak analizowanego linku",
    "Formats…": "Formaty…",
    "Video": "Wideo",
    "Audio": "Audio",
    "Audio only": "Tylko audio",
    "Quality:": "Jakość:",
    "Container:": "Kontener:",
    "Compatibility (H.264/AAC)": "Zgodność (H.264/AAC)",
    "Format:": "Format:",
    "Subtitles:": "Napisy:",
    "Folder:": "Folder:",
    "Browse…": "Wybierz…",
    "Open": "Otwórz",
    "Add to list": "Dodaj do listy",
    "Ctrl+L link · F5 analyze · Ctrl+Enter add · Ctrl+D download":
        "Ctrl+L link · F5 analizuj · Ctrl+Enter dodaj · Ctrl+D pobierz",
    "Analyzing the link…": "Analizuję link…",
    "Analyzing": "Analizuję",
    "Analyzing the link": "Analizuję link",
    "Fetching the title, available qualities and subtitles… {secs} s":
        "Pobieram tytuł, dostępne jakości i napisy… {secs} s",
    "taking longer than usual, YouTube is responding slowly": "dłużej niż zwykle, YouTube odpowiada wolno",
    "Restored {n} unfinished tasks from the previous session.":
        "Przywrócono {n} niezakończonych zadań z poprzedniej sesji.",
    "The language will change after a restart. Restart now?":
        "Język zmieni się po ponownym uruchomieniu. Uruchomić ponownie teraz?",
    "The language will change after a restart.": "Język zmieni się po ponownym uruchomieniu.",
    "Target folder": "Folder docelowy",
    "Settings saved.": "Zapisano ustawienia.",
    # option hints
    "Best quality among H.264/AAC — plays everywhere (TVs, phones, editors), usually up to 1080p.":
        "Najlepsza jakość wśród H.264/AAC — działa wszędzie (TV, telefony, edytory), zwykle do 1080p.",
    "Highest resolution and FPS (usually AV1/VP9 + Opus) without re-encoding, merged into MKV.":
        "Najwyższa rozdzielczość i FPS (zwykle AV1/VP9 + Opus) bez rekompresji, scalone do MKV.",
    "Highest resolution and FPS without re-encoding, in MP4 (not every player handles AV1/VP9 in MP4).":
        "Najwyższa rozdzielczość i FPS bez rekompresji, w MP4 (AV1/VP9 w MP4 nie każdy odtwarzacz obsłuży).",
    "Subtitle languages: comma-separated codes, e.g. pl,en": "Języki napisów: kody rozdzielone przecinkami, np. pl,en",
    "Subtitles {langs} embedded in the file.": "Napisy {langs} osadzone w pliku.",
    "Subtitles {langs} as separate .srt files.": "Napisy {langs} jako osobne pliki .srt.",
    "The best audio track exactly as it is on YouTube (usually Opus ~130–160 kb/s) — lossless.":
        "Najlepsza ścieżka audio dokładnie tak, jak jest na YouTube (zwykle Opus ~130–160 kb/s) — bez strat.",
    "Conversion to a lossless format: a bigger file, but no better than the source.":
        "Konwersja do formatu bezstratnego: większy plik, ale jakość nie wyższa niż źródło.",
    "Conversion to {fmt} (re-encoding). Cover art and tags are embedded.":
        "Konwersja do {fmt} (rekompresja). Okładka i tagi są osadzane w pliku.",
    "SponsorBlock will cut out: {cats}.": "SponsorBlock wytnie: {cats}.",
    "SponsorBlock will mark segments as chapters.": "SponsorBlock oznaczy segmenty jako rozdziały.",
    # link analysis
    "The clipboard does not contain a link.": "Schowek nie zawiera linku.",
    "Type or paste a link.": "Wpisz lub wklej link.",
    "This does not look like a link (it should start with https://).":
        "To nie wygląda na link (powinien zaczynać się od https://).",
    "Click “Add to list” to choose entries.": "Kliknij „Dodaj do listy”, aby wybrać pozycje.",
    "Ready to add.": "Gotowe do dodania.",
    "Could not read the link": "Nie udało się odczytać linku",
    "Try setting cookies in Settings.": "Spróbuj ustawić cookies w Ustawieniach.",
    "Analysis: {msg}": "Analiza: {msg}",
    "Clipboard: {text}": "Schowek: {text}",
    # adding
    "The playlist is empty.": "Playlista jest pusta.",
    "Skipped duplicates: {n}.": "Pominięto duplikaty: {n}.",
    "All entries are already on the list.": "Wszystkie pozycje są już na liście.",
    "Added to the list": "Dodano do listy",
    "Added {n} items to the list": "Dodano {n} pozycji do listy",
    "{what} and started.": "{what} i uruchomiono.",
    "{what}. Start it with “▶ Download all”.": "{what}. Uruchom przyciskiem „▶ Pobierz wszystkie”.",
    "“{title}” in the same mode was already downloaded as #{id}:\n{path}":
        "„{title}” w tym samym trybie został już pobrany jako #{id}:\n{path}",
    "“{title}” in the same mode is already on the list as #{id} ({state}).":
        "„{title}” w tym samym trybie jest już na liście jako #{id} ({state}).",
    "A second task would be saved under the same file name, so yt-dlp would skip it. "
    "Change the mode/format or add it anyway.\n\nAdd anyway?":
        "Drugie zadanie zapisze się pod tą samą nazwą pliku, więc yt-dlp je pominie. "
        "Zmień tryb/format albo dodaj mimo to.\n\nDodać mimo to?",
    "Not added — duplicate.": "Nie dodano — duplikat.",
    # yt-dlp update
    "In the packaged app yt-dlp is built in — updating it requires a new release of the app.":
        "W wersji spakowanej yt-dlp jest wbudowany — aktualizacja wymaga nowej wersji aplikacji.",
    "Finish or cancel the running downloads first.": "Najpierw zakończ albo anuluj trwające pobierania.",
    "Update yt-dlp (currently {version}) and deno with pip?":
        "Zaktualizować yt-dlp (obecnie {version}) i deno przez pip?",
    "Updating…": "Aktualizuję…",
    "The update failed (code {rc}): {detail}": "Aktualizacja nie powiodła się (kod {rc}): {detail}",
    "The update failed — see the log for details.": "Aktualizacja nie powiodła się — szczegóły w logu.",
    "yt-dlp updated: {old} → {new}": "yt-dlp zaktualizowany: {old} → {new}",
    "yt-dlp {new} installed — restart the app.": "yt-dlp {new} zainstalowany — uruchom aplikację ponownie.",
    "Restart the app.": "Uruchom aplikację ponownie.",
    "yt-dlp is up to date ({version}).": "yt-dlp jest aktualny ({version}).",
    "You have the latest yt-dlp ({version}).": "Masz najnowszą wersję yt-dlp ({version}).",
    # status / activity
    "in progress {running}/{active}": "w toku {running}/{active}",
    "List finished — done: {done}": "Lista zakończona — gotowe: {done}",
    "errors: {n}": "błędy: {n}",
    "Downloaded: {title}": "Pobrano: {title}",
    "Error: {title} — {error}": "Błąd: {title} — {error}",
    "Missing: {tools} — run the setup_env script": "Brakuje: {tools} — uruchom skrypt setup_env",
    "Not found: {tools}. Without deno YouTube only offers low qualities; without ffmpeg "
    "nothing can be merged or converted.":
        "Nie znaleziono: {tools}. Bez deno YouTube daje tylko niskie jakości, bez ffmpeg "
        "nie da się scalać ani konwertować.",
    "Downloading in progress ({n}). Close and stop it?\nUnfinished tasks will return to the list on the next start.":
        "Trwa pobieranie ({n}). Zamknąć i przerwać?\nNiezakończone zadania wrócą na listę przy następnym uruchomieniu.",
    # --- options (core) --------------------------------------------------------------
    "Best": "Najlepsza",
    "Original (no re-encoding)": "Oryginał (bez rekompresji)",
    "FLAC (lossless container)": "FLAC (bezstratny kontener)",
    "Best (VBR)": "Najlepsza (VBR)",
    "Off": "Wyłączony",
    "Mark as chapters": "Oznacz jako rozdziały",
    "Cut out segments": "Wytnij segmenty",
    "original": "oryginał",
    "subtitles": "napisy",
    "Invalid speed limit: {value} (e.g. 5M, 800K)": "Niepoprawny limit prędkości: {value} (np. 5M, 800K)",
    "Unknown audio format: {value}": "Nieznany format audio: {value}",
    "Unknown container: {value}": "Nieznany kontener: {value}",
    "Unknown video quality: {value}": "Nieznana jakość wideo: {value}",
    "Invalid subtitle languages: {value} (e.g. pl,en)": "Niepoprawne języki napisów: {value} (np. pl,en)",
    "Unknown mode: {value}": "Nieznany tryb: {value}",
    "Unknown SponsorBlock categories: {value}": "Nieznane kategorie SponsorBlock: {value}",
    "Unknown SponsorBlock mode: {value}": "Nieznany tryb SponsorBlock: {value}",
    # probe / files
    "Playlist · {n} entries": "Playlista · {n} pozycji",
    "subtitles: {langs}": "napisy: {langs}",
    "subtitles: auto-generated only": "napisy: tylko automatyczne",
    "Could not read information about the link.": "Nie udało się odczytać informacji o linku.",
    "Could not move to the Recycle Bin (code {rc}): {path}": "Nie udało się przenieść do Kosza (kod {rc}): {path}",
    "The file still exists: {path}": "Plik nadal istnieje: {path}",
    "No free name in the trash for {name}": "Brak wolnej nazwy w koszu dla {name}",
    # --- task states and stages --------------------------------------------------------
    "Added": "Dodane",
    "Waiting": "Oczekuje",
    "In progress": "W toku",
    "Done": "Gotowe",
    "Error": "Błąd",
    "Cancelled": "Anulowane",
    "Downloading": "Pobieranie",
    "Processing": "Przetwarzanie",
    "Merging": "Scalanie",
    "Extracting audio": "Wyodrębnianie audio",
    "Metadata": "Metadane",
    "Thumbnail": "Okładka",
    "Embedding subtitles": "Osadzanie napisów",
    "Converting subtitles": "Konwersja napisów",
    "SponsorBlock": "SponsorBlock",
    "Cutting segments": "Wycinanie segmentów",
    "Fixing container": "Naprawa kontenera",
    "Fixing aspect ratio": "Naprawa proporcji",
    "Fixing timestamps": "Naprawa znaczników",
    "Moving file": "Przenoszenie",
    # --- queue table --------------------------------------------------------------
    "Title": "Tytuł",
    "Mode": "Tryb",
    "Progress": "Postęp",
    "Speed": "Prędkość",
    "Left": "Zostało",
    "Status": "Status",
    "Actions": "Akcje",
    "Start": "Start",
    "Remove": "Usuń",
    "Cancel": "Anuluj",
    "Play": "Odtwórz",
    "Folder": "Folder",
    "Delete": "Usuń",
    "Retry": "Ponów",
    "Download list": "Lista pobierania",
    "Download all": "Pobierz wszystkie",
    "Selected": "Zaznaczone",
    "Remove from list": "Usuń z listy",
    "Retry failed": "Ponów błędy",
    "Clear finished": "Wyczyść gotowe",
    "Parallel:": "Równolegle:",
    "The list is empty — paste a link, choose a mode and click “Add to list”.":
        "Lista jest pusta — wklej link, wybierz tryb i kliknij „Dodaj do listy”.",
    "The file no longer exists:\n{path}": "Plik już nie istnieje:\n{path}",
    "Move {n} file(s) to the Recycle Bin and remove them from the list?":
        "Przenieść do Kosza {n} plik(ów) i usunąć z listy?",
    "Yes — to the Recycle Bin and off the list\nNo — only off the list (the file stays)":
        "Tak — do Kosza i z listy\nNie — tylko z listy (plik zostaje)",
    "Not all files could be deleted:": "Nie wszystkie pliki udało się usunąć:",
    "Download all added": "Pobierz wszystkie dodane",
    "Show in folder": "Pokaż w folderze",
    "Copy link": "Kopiuj link",
    "Copy yt-dlp command": "Kopiuj komendę yt-dlp",
    "Delete file (to Recycle Bin)…": "Usuń plik (do Kosza)…",
    "Starting…": "Start…",
    "file deleted": "plik usunięty",
    "Added (failed before)": "Dodane (wcześniej błąd)",
    "added": "dodane",
    "in progress": "w toku",
    "done": "gotowe",
    "errors": "błędy",
    "{n} items selected": "Zaznaczono {n} pozycji",
    # --- playlist dialog -----------------------------------------------------------
    "Choose playlist entries": "Wybierz pozycje z playlisty",
    "Filter by title…": "Filtruj po tytule…",
    "All": "Wszystkie",
    "None": "Żadne",
    "Invert": "Odwróć",
    "Duration": "Czas",
    "Add selected": "Dodaj zaznaczone",
    "Click toggles an entry, Shift+click toggles a whole range.": "Klik zaznacza/odznacza, Shift+klik — cały zakres.",
    "Selected {n} of {total}": "Zaznaczono {n} z {total}",
    # --- format dialog -------------------------------------------------------------
    "Choose format": "Wybór formatu",
    "Ext.": "Rozsz.",
    "Resolution": "Rozdzielczość",
    "Codec": "Kodek",
    "Size": "Rozmiar",
    "Notes": "Uwagi",
    "no video (audio only)": "bez obrazu (tylko dźwięk)",
    "audio only": "tylko audio",
    "no audio": "bez dźwięku",
    "Choose at least a video or an audio stream.": "Wybierz co najmniej obraz albo dźwięk.",
    "Audio only: {id} — saved using the audio format from the options panel.":
        "Tylko dźwięk: {id} — zapis wg formatu audio z panelu opcji.",
    "Format: {spec}": "Format: {spec}",
    "total ~{size}": "razem ~{size}",
    # --- settings dialog ("Downloading" section title shares the stage translation above) -----
    "File name:": "Nazwa pliku:",
    "Default": "Domyślna",
    "A yt-dlp template, e.g. %(uploader)s/%(title)s [%(id)s].%(ext)s — a slash creates a subfolder.":
        "Szablon yt-dlp, np. %(uploader)s/%(title)s [%(id)s].%(ext)s — ukośnik tworzy podfolder.",
    "Speed limit:": "Limit prędkości:",
    "no limit": "bez limitu",
    "Per download, e.g. 5M (5 MB/s) or 800K. Empty = no limit.":
        "Na każde pobieranie, np. 5M (5 MB/s) albo 800K. Puste = bez limitu.",
    "Queue": "Kolejka",
    "Start a task right after adding it to the list": "Uruchamiaj zadanie od razu po dodaniu do listy",
    "Restore unfinished tasks after a restart": "Przywracaj niezakończone zadania po ponownym uruchomieniu",
    "Subtitles (video mode)": "Napisy (tryb wideo)",
    "Also auto-generated / translated subtitles": "Także napisy generowane automatycznie / tłumaczone",
    "Embed subtitles in the video file (otherwise separate .srt files)":
        "Osadzaj napisy w pliku wideo (inaczej osobne pliki .srt)",
    "Turn subtitles on and pick languages (e.g. pl,en) in the options panel of the main window.":
        "Włączanie napisów i języki (np. pl,en) — w panelu opcji okna głównego.",
    "SponsorBlock — categories": "SponsorBlock — kategorie",
    "Sponsor / ad": "Sponsor / reklama",
    "Self-promotion": "Autopromocja",
    "Subscribe reminders": "Prośby o subskrypcję",
    "Intro": "Intro",
    "Outro / end credits": "Outro / napisy końcowe",
    "Preview / recap": "Zapowiedź / podsumowanie",
    "Filler / tangents": "Dygresje",
    "Music: non-music parts": "Muzyka: fragmenty niemuzyczne",
    "Hook / teaser": "Zajawka (hook)",
    "The mode (mark chapters / cut out) is chosen in the options panel. Data: sponsor.ajay.app.":
        "Tryb (oznacz rozdziały / wytnij) wybierasz w panelu opcji. Dane: sponsor.ajay.app.",
    "Cookies (age-restricted, private and members-only videos)":
        "Cookies (filmy z ograniczeniem wieku, prywatne, członkowskie)",
    "From browser:": "Z przeglądarki:",
    "none": "brak",
    "cookies.txt file:": "Plik cookies.txt:",
    "cookies.txt file": "Plik cookies.txt",
    "All files": "Wszystkie pliki",
    "The file takes precedence over the browser. Chrome/Edge on Windows encrypt cookies in a way yt-dlp "
    "usually cannot read — Firefox or an exported cookies.txt work best. Close the browser while reading.":
        "Plik ma pierwszeństwo przed przeglądarką. Chrome/Edge na Windows szyfrują cookies w sposób, którego "
        "yt-dlp zwykle nie odczyta — najpewniej działa Firefox albo wyeksportowany cookies.txt. "
        "Przeglądarka powinna być zamknięta podczas odczytu.",
    "Other": "Inne",
    "Paste a link from the clipboard when switching to the window (if the field is empty)":
        "Wklejaj link ze schowka po przełączeniu na okno (gdy pole jest puste)",
    "Watch the clipboard — a copied YouTube link goes straight to the list":
        "Obserwuj schowek — skopiowany link YouTube od razu trafia na listę",
    "Sound and taskbar flash when the list finishes": "Dźwięk i mignięcie paska zadań po zakończeniu listy",
    "Verbose log (yt-dlp [debug] messages)": "Szczegółowy log (komunikaty [debug] yt-dlp)",
    "Save": "Zapisz",
    "The file name template must contain %(ext)s.": "Szablon nazwy musi zawierać %(ext)s.",
    "Speed limit: a number with a K/M/G unit, e.g. 5M.": "Limit prędkości: liczba z jednostką K/M/G, np. 5M.",
}
