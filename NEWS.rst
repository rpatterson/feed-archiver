Feedarchiver 1.0.0b6 (2022-12-23)
=================================

No significant changes.


Feedarchiver 1.0.0b5 (2022-12-22)
=================================

Features
--------

- Add the ``$ feed-archiver relink`` sub-command to re-link existing archived feed item
  enclosures as they would be if they had been newly archived by the ``$ feed-archiver
  update`` sub-command. (relink-item-content)


Bugfixes
--------

- Fix the check that the remote feed format (RSS vs Atom) matches the archived feed. (wrong-archive-feed-format-check)


Feedarchiver 1.0.0b4 (2022-12-19)
=================================

No significant changes.


Feedarchiver 1.0.0b3 (2022-12-18)
=================================

No significant changes.


Feedarchiver 1.0.0b2 (2022-12-18)
=================================

No significant changes.


Feedarchiver 1.0.0b1 (2022-12-17)
=================================

Bugfixes
--------

- Don't report results from the ``update`` sub-command when there are none. (empty-results)


Feedarchiver 1.0.0b0 (2022-12-16)
=================================

Features
--------

- First stable release. (initial-release)


Feedarchiver 0.1.2 (2022-12-16)
===============================

No significant changes.


Feedarchiver 0.1.2b1 (2022-12-16)
=================================

Deprecations and Removals
-------------------------

- Remove the archive migration code and sub-command now that the format is stable. (migrate-sub-command)


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