"""Download pinned Latin candidates and build comparison-page webfonts."""
# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
from pathlib import Path
import tempfile
import urllib.parse
import urllib.request
from typing import cast

from fontTools import subset


GOOGLE_FONTS_COMMIT = "7ff85c87f93ea6cca5f41c69f2e4edcb90240f26"
GOOGLE_FONTS_RAW = (
    "https://raw.githubusercontent.com/google/fonts/"
    f"{GOOGLE_FONTS_COMMIT}/ofl"
)
STIX_TAG = "v2.13b171"
STIX_RAW = f"https://raw.githubusercontent.com/stipub/stixfonts/{STIX_TAG}/fonts"
NOTO_COMMIT = "9b0f1436e455d902de067a2501422e5dc71ad16b"
NOTO_RAW = (
    "https://raw.githubusercontent.com/notofonts/noto-cjk/"
    f"{NOTO_COMMIT}/Serif/Variable/TTF/Subset"
)
CACHE_DIR = Path(".cache/font-sources/latin-candidates")
OUTPUT_DIR = Path("website/src/assets/fonts")
LATIN_UNICODES = ",".join(
    (
        "U+0020-024F",
        "U+0300-036F",
        "U+1E00-1EFF",
        "U+2000-206F",
        "U+20A0-20CF",
    )
)


@dataclass(frozen=True)
class CandidateSource:
    output: str
    filename: str
    url: str
    sha256: str


def google_source(
    family: str,
    filename: str,
    output: str,
    sha256: str,
) -> CandidateSource:
    encoded = urllib.parse.quote(filename)
    return CandidateSource(
        output,
        filename,
        f"{GOOGLE_FONTS_RAW}/{family}/{encoded}",
        sha256,
    )


SOURCES = (
    CandidateSource(
        "LatinCandidate-NotoSerifJP.woff2",
        "NotoSerifJP-VF.ttf",
        f"{NOTO_RAW}/NotoSerifJP-VF.ttf",
        "99999f906b3793c7c97661a05ef9d53488d488604683b308c756d084b71df7d1",
    ),
    CandidateSource(
        "LatinCandidate-STIXTwoText.woff2",
        "STIXTwoText[wght].ttf",
        f"{STIX_RAW}/variable_ttf/STIXTwoText%5Bwght%5D.ttf",
        "7962b8b7811e6a896c9a91a0bccbb5241047770eb24d4997c5cb5fe21d5c0df2",
    ),
    google_source(
        "sourceserif4",
        "SourceSerif4[opsz,wght].ttf",
        "LatinCandidate-SourceSerif4.woff2",
        "97b2d4da6e3cb494b5a1e66ae176914d852ccabef49e0c02c0df25f3e39aca0b",
    ),
    google_source(
        "literata",
        "Literata[opsz,wght].ttf",
        "LatinCandidate-Literata.woff2",
        "b41138c9373112f32abb589cc22e8674b06ed4048b0c513be922bdd26f274440",
    ),
    google_source(
        "robotoserif",
        "RobotoSerif[GRAD,opsz,wdth,wght].ttf",
        "LatinCandidate-RobotoSerif.woff2",
        "351ced75f3851806aa6d846b669361521eb1925cfc530396df9c1a1b77061ddb",
    ),
    google_source(
        "newsreader",
        "Newsreader[opsz,wght].ttf",
        "LatinCandidate-Newsreader.woff2",
        "8a08d13f8a6c0d51be379a60af84f945f65369a67e509ee3c3bdcc421254d7c1",
    ),
    google_source(
        "petrona",
        "Petrona[wght].ttf",
        "LatinCandidate-Petrona.woff2",
        "0ede77fbf726541cf93ece7b721a7b069f004cb413ab205f74963560015ab075",
    ),
    google_source(
        "spectral",
        "Spectral-ExtraLight.ttf",
        "LatinCandidate-Spectral-200.woff2",
        "5d852db897fd7ad5ce640a6e88f1cd70eac75777c541d02d86749af8d4797ff1",
    ),
    google_source(
        "spectral",
        "Spectral-Light.ttf",
        "LatinCandidate-Spectral-300.woff2",
        "a2a530303d326473b69ab7863b879e9203ec747e51d5fa7c7b19e0e975e00740",
    ),
    google_source(
        "spectral",
        "Spectral-Regular.ttf",
        "LatinCandidate-Spectral-400.woff2",
        "c89021dc20720c8d0dcf40b0b2f6e00c13665fa8041717f581396f51b8c78f5d",
    ),
    google_source(
        "spectral",
        "Spectral-Medium.ttf",
        "LatinCandidate-Spectral-500.woff2",
        "f385bc588599c879112272711d4acecc126674009d747a27284f59e93a240e83",
    ),
    google_source(
        "spectral",
        "Spectral-SemiBold.ttf",
        "LatinCandidate-Spectral-600.woff2",
        "5f86915a744832ecf6e4a17ab04bea091b9fa992ef5164ff65ae34c1da2fe94b",
    ),
    google_source(
        "spectral",
        "Spectral-Bold.ttf",
        "LatinCandidate-Spectral-700.woff2",
        "70ddb1ec6ae3b0b8d0c79231f670de786978f19baeba2130757526e407aebf9b",
    ),
    google_source(
        "spectral",
        "Spectral-ExtraBold.ttf",
        "LatinCandidate-Spectral-800.woff2",
        "af3f8513db8d047ebecb1682b5e04dfc12ec7e6b51b71654d4d348f12a5e6b5a",
    ),
)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            hasher.update(chunk)
    return hasher.hexdigest()


def resolve(source: CandidateSource) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    destination = CACHE_DIR / source.filename
    if destination.is_file() and digest(destination) == source.sha256:
        return destination
    if destination.exists():
        destination.unlink()

    with tempfile.NamedTemporaryFile(
        prefix=f".{source.filename}.", suffix=".tmp", dir=CACHE_DIR, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        print(f"Downloading {source.url}")
        _ = urllib.request.urlretrieve(source.url, temporary_path)
        actual = digest(temporary_path)
        if actual != source.sha256:
            raise ValueError(
                f"SHA-256 mismatch for {source.filename}: {actual} != {source.sha256}"
            )
        _ = temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination


def build(source: CandidateSource) -> None:
    input_path = resolve(source)
    output_path = OUTPUT_DIR / source.output
    subset_main = cast(Callable[[list[str]], int | None], subset.main)
    _ = subset_main(
        [
            str(input_path),
            f"--output-file={output_path}",
            "--flavor=woff2",
            f"--unicodes={LATIN_UNICODES}",
            "--layout-features=*",
            "--name-IDs=*",
            "--name-languages=*",
            "--notdef-glyph",
            "--notdef-outline",
            "--recommended-glyphs",
        ]
    )
    print(f"Built {output_path}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for source in SOURCES:
        build(source)


if __name__ == "__main__":
    main()
