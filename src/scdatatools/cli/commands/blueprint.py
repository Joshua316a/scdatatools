import logging
import sys
import typing
from functools import partial
from pathlib import Path

from rich.progress import Progress

from scdatatools.sc.blueprints.generators.datacore_entity import blueprint_from_datacore_entity
from . import common

logger = logging.getLogger(__name__)


def resolve_blueprint(sc, entity):
    if record := sc.datacore.records_by_guid.get(entity):
        return record
    search = entity if entity.casefold().endswith(".xml") else entity + ".xml"
    records = [
        record for record in sc.datacore.search_filename(f"*/{search}") if record.type == "EntityClassDefinition"
    ]
    if len(records) > 1:
        logger.debug(f"{records =}")
        logger.error(f'"{entity}" is too ambiguous')
        sys.exit(1)
    elif records:
        return records[0]
    logger.error(f'Could not find entity for "{entity}"')
    sys.exit(1)


class blueprint:
    """Generate and extract STar Citizen Blueprint (scbp)."""

    def generate(
        self,
        sc_dir: str,
        entity: str,
        output: str = "",
    ):
        """Generate a scbp"""
        sc = common.open_sc_dir(sc_dir)
        entity = resolve_blueprint(sc, entity)
        logger.info(f"Generating blueprint for {entity.name} ({entity.id})")
        with Progress() as progbar:
            generating_bp = progbar.add_task("Generating blueprint", total=None)

            def log(msg, progress, total, level, exc_info):
                logger.log(level, msg, exc_info=exc_info)
                progbar.update(generating_bp, total=total, completed=progress)

            bp = blueprint_from_datacore_entity(sc, entity, monitor=log)

            if not output:
                output = f"{bp.name}.scbp"

            if output == "-":
                print(bp.dumps())
            else:
                logger.info(f"writing blueprint to {output}")
                with open(output, "w") as o:
                    bp.dump(o)

    def extract(
        self,
        sc_dir: str,
        entity_or_blueprint: str,
        output: typing.Text,
        convert_cryxml: typing.Text = "xml",
        unsplit_textures: bool = True,
        convert_textures: str = "",
        convert_models: bool = False,
        no_overwrite: bool = False,
    ):
        """Extract all the record assets for a given blueprint, optionally also generating the blueprint."""
        sc = common.open_sc_dir(sc_dir)

        with Progress() as progbar:

            def log(task, msg, progress=None, total=None, level=None, exc_info=None):
                level = level or logging.INFO
                logger.log(level, msg, exc_info=exc_info)
                progbar.update(task, total=total, completed=progress)

            output = Path(output)
            output.mkdir(parents=True, exist_ok=True)

            generating_bp = progbar.add_task("Generating blueprint", total=None)
            if (bp := Path(entity_or_blueprint)).is_file():
                print("TODO: handle already generated blueprints")
                sys.exit(1)
            else:
                entity = resolve_blueprint(sc, entity_or_blueprint)
                logger.info(f"Generating blueprint for {entity.name} ({entity.id})")

                bp = blueprint_from_datacore_entity(sc, entity, monitor=partial(log, generating_bp))
                with open(output / f"{bp.name}.scbp", "w") as o:
                    bp.dump(o)

            opts = {
                "convert_cryxml_fmt": convert_cryxml,
                "auto_unsplit_textures": unsplit_textures,
                "auto_convert_textures": bool(convert_textures),
                "convert_dds_fmt": convert_textures,
                "extract_sounds": True,
                "auto_convert_models": convert_models,
            }
            progbar.reset(generating_bp, description=f"Exporting {bp.name}")
            bp.extract(outdir=output, monitor=partial(log, generating_bp), **opts)


def register_blueprint(subparsers, parents):
    """Register `scdt blueprint` (argparse translation of the nubia decorators)."""
    group = subparsers.add_parser(
        "blueprint",
        aliases=["bp"],
        parents=parents,
        help="Generate and extract STar Citizen Blueprint (scbp).",
        description="Generate and extract STar Citizen Blueprint (scbp).",
    )
    subs = group.add_subparsers(dest="blueprint_command", metavar="[subcommand]")
    inst = blueprint()

    gen = subs.add_parser(
        "generate",
        parents=parents,
        help="Generate a scbp",
        description="Generate a scbp",
    )
    common.add_sc_dir_argument(gen)
    gen.add_argument(
        "entity",
        metavar="entity<STR>",
        help="The Data Core entity record to generate a blueprint for.",
    )
    common.add_option(
        gen, "output", str, "",
        "The output path to write the blueprint. Defaults to `entity_name.scbp` in the current directory. "
        'Use "-" to print the blueprint to stdout',
        aliases=["-o"],
    )
    gen.set_defaults(_handler=lambda ns: inst.generate(
        sc_dir=ns.sc_dir,
        entity=ns.entity,
        output=ns.output,
    ))

    ext = subs.add_parser(
        "extract",
        parents=parents,
        help="Extract all the record assets for a given blueprint, optionally also generating the blueprint.",
        description="Extract all the record assets for a given blueprint, optionally also generating the blueprint.",
    )
    common.add_sc_dir_argument(ext)
    ext.add_argument(
        "entity_or_blueprint",
        metavar="entity-or-blueprint<STR>",
        help="The Data Core entity record to extract, or scbp file.",
    )
    # NOTE: no default in the original signature either — required positional,
    # matching the previous interface.
    ext.add_argument(
        "output",
        metavar="output<STR>",
        help="Output directory to extract data into",
    )
    common.add_extraction_args(ext, exclude=["extract_model_assets", "output"], defaults={
        "convert_cryxml": "xml",
        "unsplit_textures": True,
        "convert_textures": "",
        "convert_models": False,
        "no_overwrite": False,
    })
    ext.set_defaults(_handler=lambda ns: inst.extract(
        sc_dir=ns.sc_dir,
        entity_or_blueprint=ns.entity_or_blueprint,
        output=ns.output,
        convert_cryxml=ns.convert_cryxml,
        unsplit_textures=ns.unsplit_textures,
        convert_textures=ns.convert_textures,
        convert_models=ns.convert_models,
        no_overwrite=ns.no_overwrite,
    ))
    return group
