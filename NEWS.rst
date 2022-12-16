Feedarchiver 0.1.2b0 (2022-12-16)
=================================

Bugfixes
--------

- Tolerate errors when parsing the local archive copy of the feed.  Try to parse the local
  archive version of the feed if possible.  If there are errors parsing it, then treat it
  as if it's the first time archiving this feed. (archive-feed-parse-errors)
- Cleanup ``pathlib.Path(...)`` objects in ``$ feed-archiver update`` output. (download-path-output)


Feedarchiver 0.1.1 (2022-12-14)
===============================

No significant changes.


Feedarchiver 0.1.1b0 (2022-12-14)
=================================

Bugfixes
--------

- Add CI/CD pipeline/workflow that also publishes releases.  Force a patch version bump
  and release to ensure the latest published release artifacts are all the same. (ci-cd-publish-releases)
