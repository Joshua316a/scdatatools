import io
import logging
import re
import sys
import typing
from csv import DictWriter
from pathlib import Path

from rich import get_console, table

from . import common
from ..utils import track

logger = logging.getLogger(__name__)


class localization:
    """Localization utilities"""

    def translate(
        self,
        sc_dir: str,
        text: str,
        languages: typing.List[str] = None,
    ):
        """Translate a give text using the p4k's localization database."""
        sc = common.open_sc_dir(sc_dir)
        languages = languages or [sc.localization.default_language]

        translations = []
        for lang in languages:
            lang = lang.casefold()
            if lang not in sc.localization.languages:
                continue
            translations.append(sc.localization.gettext(text, language=lang, default_response=""))

        if len(translations) == 1:
            print(translations[0])
            sys.exit()

        t = table.Table()
        for lang in languages:
            t.add_column(lang)
        t.add_row(*translations)
        get_console().print(t)

    def ls(
        self,
        sc_dir: str,
        languages: typing.List[str] = None,
        filter: str = "",
    ):
        """List translations"""
        sc = common.open_sc_dir(sc_dir)

        selected_languages = []
        if not languages:
            selected_languages = sc.localization.languages
            selected_languages.remove(sc.localization.default_language)
            selected_languages.insert(0, sc.localization.default_language)
        else:
            for lang in languages:
                lang = lang.casefold()
                if lang in sc.localization.languages:
                    selected_languages.append(lang)
                else:
                    logger.error(f"invalid language {lang}")
        if not selected_languages:
            return

        t = table.Table()
        t.add_column("key")
        for lang in selected_languages:
            t.add_column(lang)

        filter = re.compile(filter.casefold()) if filter else None
        for k in sc.localization.keys:
            row = [k] + [sc.localization.gettext(k, lang, "") for lang in selected_languages]
            if filter is None or filter.search("".join(row).casefold()):
                t.add_row(*row)
        get_console().print(t)

    def export(
        self,
        sc_dir: str,
        output: str,
        languages: typing.List[str] = None,
        filter: str = "",
    ):
        """Export translations to  csv"""
        sc = common.open_sc_dir(sc_dir)
        if output == "-":
            outfile = io.StringIO(newline="")
        else:
            outfile = Path(output).open("w", newline="", encoding="utf-8")
        selected_languages = []

        if not languages:
            selected_languages = sc.localization.languages
            selected_languages.remove(sc.localization.default_language)
            selected_languages.insert(0, sc.localization.default_language)

        try:
            writer = DictWriter(outfile, fieldnames=["key"] + selected_languages)
            writer.writeheader()

            filter = re.compile(filter.casefold()) if filter else None
            for k in track(sc.localization.keys, description="Exporting translation"):
                row = dict(
                    **{"key": k},
                    **{lang: sc.localization.gettext(k, lang, "") for lang in selected_languages},
                )
                if filter is None or filter.search(str(row).casefold()):
                    writer.writerow(row)

            if output == "-":
                print(outfile.getvalue())
        finally:
            outfile.close()


def _add_languages_option(parser, description):
    common.add_option(
        parser, "languages", "list", None,
        description,
        aliases=["-l"],
    )


def _add_filter_option(parser):
    common.add_option(
        parser, "filter", str, "",
        "Regex filter to down-select the printed translations. The filter will apply to the key names, "
        "as well as the translations for the key",
        aliases=["-f"],
    )


def register_localization(subparsers, parents):
    """Register `scdt localization` (argparse translation of the nubia decorators)."""
    group = subparsers.add_parser(
        "localization",
        aliases=["loc"],
        parents=parents,
        help="Localization utilities",
        description="Localization utilities",
    )
    subs = group.add_subparsers(dest="localization_command", metavar="[subcommand]")
    inst = localization()

    translate = subs.add_parser(
        "translate",
        parents=parents,
        help="Translate a give text using the p4k's localization database.",
        description="Translate a give text using the p4k's localization database.",
    )
    common.add_sc_dir_argument(translate)
    translate.add_argument(
        "text",
        metavar="text<STR>",
        help="The text to translate",
    )
    _add_languages_option(
        translate,
        "Languages to translate to from the available languages. Defaults to english",
    )
    translate.set_defaults(_handler=lambda ns: inst.translate(
        sc_dir=ns.sc_dir,
        text=ns.text,
        languages=ns.languages,
    ))

    ls = subs.add_parser(
        "ls",
        parents=parents,
        help="List translations",
        description="List translations",
    )
    common.add_sc_dir_argument(ls)
    _add_filter_option(ls)
    _add_languages_option(
        ls,
        "Languages to display to from the available languages. Defaults to all",
    )
    ls.set_defaults(_handler=lambda ns: inst.ls(
        sc_dir=ns.sc_dir,
        languages=ns.languages,
        filter=ns.filter,
    ))

    export = subs.add_parser(
        "export",
        parents=parents,
        help="Export translations to  csv",
        description="Export translations to  csv",
    )
    common.add_sc_dir_argument(export)
    _add_filter_option(export)
    _add_languages_option(
        export,
        "Languages to display to from the available languages. Defaults to all",
    )
    export.add_argument(
        "output",
        metavar="output<STR>",
        help='Output filename or "-" to print to the screen',
    )
    export.set_defaults(_handler=lambda ns: inst.export(
        sc_dir=ns.sc_dir,
        output=ns.output,
        languages=ns.languages,
        filter=ns.filter,
    ))
    return group
