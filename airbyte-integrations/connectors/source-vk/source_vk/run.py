import sys

from airbyte_cdk.entrypoint import launch

from source_vk import SourceVk


def run() -> None:
    source = SourceVk()
    launch(source, sys.argv[1:])
