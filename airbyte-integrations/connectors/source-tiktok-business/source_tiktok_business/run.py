import sys

from airbyte_cdk.entrypoint import launch

from source_tiktok_business import SourceTiktokBusiness


def run() -> None:
    source = SourceTiktokBusiness()
    launch(source, sys.argv[1:])
