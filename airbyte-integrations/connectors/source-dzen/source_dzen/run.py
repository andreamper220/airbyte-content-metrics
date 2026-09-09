import sys

from airbyte_cdk.entrypoint import launch

from source_dzen import SourceDzen


def run() -> None:
    source = SourceDzen()
    launch(source, sys.argv[1:])
