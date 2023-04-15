feed-archiver 2.0.0b0 (2023-04-15)
==================================

Bugfixes
--------

- Restore correct versions going forward.  Versions from here to v1.0.0 below are
  incorrect. (correct-versions)


feed-archiver 1.0.0b11 (2023-04-15)
===================================

Bugfixes
--------

- Upgrade all requirements to the latest versions as of Sat Apr 15 06:11:17 PM UTC 2023. (upgrade-requirements)


Feedarchiver 1.0.0b10 (2023-03-15)
==================================

Features
--------

- Address a Bandit warning about requests without timeouts. (request-timeouts)
- Write an ``./index.html`` file listing links to archived feeds. (archive-index)
- Rename the ``link-paths`` plugin system to a more accurate name, ``enclosures``.  Note
  that this requires an update to existing archive configurations using ``link-paths``
  plugins. (enclosure-plugin-rename)
- Replace ``content`` term with more correct ``enclosure`` term.  Requires running the ``$
  feed-archiver relink`` sub-command to update existing archives. (enclosure-term)
- Avoid unintended sub-directories in link path plugin template paths, add support for
  quoting path separators in plugin configuration. (link-quote-path-sep)
- Make a parsed version of the feed and item with richer data available to link path
  plugin configurations, e.g. dates and times. (link-rich-parser)
- Provide access to regular expression symbolic group names in the ``template`` plugins
  format strings. (re-group-names)
- Improve link plugin template usability by providing the ``basename`` via a
  ``pathlib.Path`` object and use that to improve the default enclosure link basename. (template-url-path)


Bugfixes
--------

- Fix an error when backup feed XML is present in the archive. (feed-backups)
- Filter out duplicate link paths returned from plugins. (link-duplicates)


Feedarchiver 1.0.0b9 (2023-02-22)
=================================

Features
--------

- Support all currently maintained versions of Python. (python-versions)


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


Feedarchiver 1.0.0b1 (2022-12-17)
=================================

Bugfixes
--------

- Don't report results from the ``update`` sub-command when there are none. (empty-results)


Feedarchiver 1.0.0 (2022-12-16)
===============================

No significant changes.


Feedarchiver 1.0.0b0 (2022-12-16)
=================================

Features
--------

- First stable release. (initial-release)


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


Feedarchiver 0.1.1b0 (2022-12-14)
=================================

Bugfixes
--------

- Add CI/CD pipeline/workflow that also publishes releases.  Force a patch version bump
  and release to ensure the latest published release artifacts are all the same. (ci-cd-publish-releases)
