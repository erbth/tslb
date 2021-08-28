#!/usr/bin/python3
"""
Find enabled packages the last build of which did either fail or is not
finished yet.
"""
from sqlalchemy.orm import aliased
from tslb import Architecture
from tslb import build_pipeline
from tslb import database as db
from tslb.SourcePackage import SourcePackage, SourcePackageList
from tslb.database import BuildPipeline as dbbp
from tslb.parse_utils import is_yes


def main():
    last_stage = build_pipeline.all_stages[-1].name

    for arch in Architecture.architectures:
        print("Checking architecture %s:" % Architecture.to_str(arch))
        for name in SourcePackageList(arch).list_source_packages():
            sp = SourcePackage(name, arch)

            for v in sp.list_version_numbers():
                spv = sp.get_version(v)
                if not is_yes(spv.get_attribute_or_default('enabled', 'false')):
                    continue

                # Get last build pipeline event
                with db.session_scope() as s:
                    se = aliased(dbbp.BuildPipelineStageEvent)
                    se2 = aliased(dbbp.BuildPipelineStageEvent)

                    event = s.query(se.stage, se.status)\
                            .filter(se.source_package == sp.name,
                                    se.architecture == Architecture.to_int(sp.architecture),
                                    se.version_number == spv.version_number,
                                    ~s.query(se2)\
                                            .filter(se2.source_package == se.source_package,
                                                    se2.architecture == se.architecture,
                                                    se2.version_number == se.version_number,
                                                    se2.time > se.time)\
                                            .exists())\
                            .first()

                if event:
                    ev_stage, ev_status = event

                    # Is it a success event? If yes, is it for the last stage?
                    if ev_status == dbbp.BuildPipelineStageEvent.status_values.success and \
                            ev_stage == last_stage:
                        continue

                    # Is it an error?
                    if ev_status == dbbp.BuildPipelineStageEvent.status_values.failed:
                        print("  %s: build failed" % spv)

                # Otherwise the package's build did not complete yet.
                print("  %s: build is not complete yet" % spv)

        print()


if __name__ == '__main__':
    main()
