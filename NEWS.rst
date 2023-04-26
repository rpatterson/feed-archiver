feed-archiver 2.0.2b0 (2023-04-26)
==================================

Bugfixes
--------

- Upgrade all requirements to the latest versions as of Tue Apr 25 11:00:28 PM UTC 2023.


feed-archiver 2.0.1 (2023-04-24)
================================

No significant changes.


feed-archiver 2.0.1b0 (2023-04-24)
==================================

No significant changes.


feed-archiver 2.0.0 (2023-04-16)
================================

No significant changes.


feed-archiver 2.0.0b1 (2023-04-16)
==================================

Bugfixes
--------

- Upgrade all requirements to the latest versions as of Sun Apr 16 03:54:21 PM UTC 2023.


feed-archiver 2.0.0b0 (2023-04-15)
==================================

Bugfixes
--------

- Restore correct versions going forward.  Versions from here to v1.0.0 below are
  incorrect.


feed-archiver 1.0.0b11 (2023-04-15)
===================================

Bugfixes
--------

- Upgrade all requirements to the latest versions as of Sat Apr 15 06:11:17 PM UTC 2023.


Feedarchiver 1.0.0b10 (2023-03-15)
==================================

Features
--------

- Address a Bandit warning about requests without timeouts.
- Write an ``./index.html`` file listing links to archived feeds.
- Rename the ``link-paths`` plugin system to a more accurate name, ``enclosures``.  Note
  that this requires an update to existing archive configurations using ``link-paths``
  plugins.
- Replace ``content`` term with more correct ``enclosure`` term.  Requires running the ``$
  feed-archiver relink`` sub-command to update existing archives.
- Avoid unintended sub-directories in link path plugin template paths, add support for
  quoting path separators in plugin configuration.
- Make a parsed version of the feed and item with richer data available to link path
  plugin configurations, e.g. dates and times.
- Provide access to regular expression symbolic group names in the ``template`` plugins
  format strings.
- Improve link plugin template usability by providing the ``basename`` via a
  ``pathlib.Path`` object and use that to improve the default enclosure link basename.


Bugfixes
--------

- Fix an error when backup feed XML is present in the archive.
- Filter out duplicate link paths returned from plugins.


Feedarchiver 1.0.0b9 (2023-02-22)
=================================

Features
--------

- Support all currently maintained versions of Python.


Feedarchiver 1.0.0b5 (2022-12-22)
=================================

Features
--------

- Add the ``$ feed-archiver relink`` sub-command to re-link existing archived feed item
  enclosures as they would be if they had been newly archived by the ``$ feed-archiver
  update`` sub-command.


Bugfixes
--------

- Fix the check that the remote feed format (RSS vs Atom) matches the archived feed.


Feedarchiver 1.0.0b1 (2022-12-17)
=================================

Bugfixes
--------

- Don't report results from the ``update`` sub-command when there are none.


Feedarchiver 1.0.0 (2022-12-16)
===============================

No significant changes.


Feedarchiver 1.0.0b0 (2022-12-16)
=================================

Features
--------

- First stable release.


Feedarchiver 0.1.2b1 (2022-12-16)
=================================

Deprecations and Removals
-------------------------

- Remove the archive migration code and sub-command now that the format is stable.


Feedarchiver 0.1.2b0 (2022-12-16)
=================================

Bugfixes
--------

- Tolerate errors when parsing the local archive copy of the feed.  Try to parse the local
  archive version of the feed if possible.  If there are errors parsing it, then treat it
  as if it's the first time archiving this feed.
- Cleanup ``pathlib.Path(...)`` objects in ``$ feed-archiver update`` output.


Feedarchiver 0.1.1b0 (2022-12-14)
=================================

Bugfixes
--------

- Add CI/CD pipeline/workflow that also publishes releases.  Force a patch version bump
  and release to ensure the latest published release artifacts are all the same.
