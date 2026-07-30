"""Post-process imported Latin CFF glyphs with AFDKO."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory


def autohint_latin_glyphs(
    output_path: Path,
    glyph_names: tuple[str, ...],
    executable: str | None = None,
) -> None:
    """Autohint imported CFF glyphs without touching native Japanese glyphs."""

    if not glyph_names:
        return
    command = executable or shutil.which("otfautohint")
    if command is None:
        raise RuntimeError("--autohint requires the AFDKO otfautohint command on PATH")
    with TemporaryDirectory(
        prefix=f".{output_path.stem}-autohint-",
        dir=output_path.parent,
    ) as temporary_directory:
        temporary_path = Path(temporary_directory)
        glyph_list_path = temporary_path / "glyphs.txt"
        hinted_path = temporary_path / output_path.name
        glyph_list_path.write_text(",".join(glyph_names), encoding="utf-8")
        subprocess.run(
            [
                command,
                "--glyphs-file",
                str(glyph_list_path),
                "--output",
                str(hinted_path),
                str(output_path),
            ],
            check=True,
        )
        hinted_path.replace(output_path)
