"""
Link enclosures about a TV series episode next to the video file as external audio.
"""

import functools
import pathlib
import re
import logging

import arrapi

from .. import linkpaths

logger = logging.getLogger(__name__)


class SonarrLinkPathPlugin(linkpaths.LinkPathPlugin):
    """
    Link enclosures about a TV series episode next to the video file as external audio.
    """

    MULTI_EPISODE_RE = re.compile("[Ee& -]")

    url = "http://localhost:8989"
    client = None
    client_get = None

    def load_config(self):
        """
        Pre-process and validate the plugin config prior to linking each enclosure.
        """
        # Validate the configuration
        self.url = self.config.get("url", self.url)
        if not isinstance(self.url, str):  # pragma: no cover
            raise ValueError(f"Sonarr `url` must be a string: {self.url!r}")
        if "api-key" not in self.config:  # pragma: no cover
            raise ValueError("Sonarr plugin configuration must specify `api-key`")
        api_key = self.config["api-key"]
        if not isinstance(api_key, str):  # pragma: no cover
            raise ValueError(f"Sonarr `api_key` must be a string: {api_key!r}")
        self.client = arrapi.SonarrAPI(self.url, api_key)
        self.client_get = self.client._raw._get  # pylint: disable=protected-access

    @functools.cached_property
    def series_by_title(self):
        """
        Request, collate and cache the full list of series titles to share across calls.
        """
        return {series["title"]: series["id"] for series in self.client_get("series")}

    # NOTE: These functions will cache globally, for the life of the process.  This
    # should be fine as `$ feedarchiver update` is expected to be run periodically, such
    # as by `# cron`.
    @functools.cache
    def get_episode_files_seasons(self, series_id):
        """
        Request, correlate and cache episode file DB ids to season and episode numbers.
        """
        episode_files_episodes = {}
        for episode in self.client_get("episode", seriesId=series_id):
            episode_files_episodes.setdefault(episode["episodeFileId"], []).append(
                (episode["seasonNumber"], episode["episodeNumber"])
            )
        return episode_files_episodes

    @functools.cache
    def get_episode_paths(self, series_id):
        """
        Request, collate and cache series episode file paths by season and episode.
        """
        episode_files_episodes = self.get_episode_files_seasons(series_id)
        episode_paths = {}
        for episode_file in self.client_get("episodeFile", seriesId=series_id):
            for season_number, episode_number in episode_files_episodes[
                episode_file["id"]
            ]:
                episode_paths.setdefault(season_number, {})[
                    episode_number
                ] = episode_file["path"]
        return episode_paths

    # I disagree with PyLint here regarding the number of local variables.  To me, the
    # variables here make this code much easier to read and understand so limiting them
    # is premature/inappropriate optimization.
    def __call__(
        self,
        basename,
        match,
        *args,
        **kwargs,
    ):  # pylint: disable=too-many-locals
        """
        Lookup the episode and link the enclosure/content next to the video file.
        """
        # Get API lookup parameters from the config and override with regex match groups
        params = dict(self.config, **match.groupdict())

        # Do any parameter validation that's possible without making API requests
        season_number = params.get("season_number")
        if not season_number:  # pragma: no cover
            raise ValueError(
                f"Sonarr `season_number` missing or empty: {season_number!r}",
            )
        try:
            season_number = int(season_number)
        except ValueError as exc:  # pragma: no cover
            raise ValueError(
                f"Sonarr `season_number` must be an integer: {season_number!r}",
            ) from exc
        episode_numbers_param = params.get("episode_numbers")
        if not episode_numbers_param:  # pragma: no cover
            raise ValueError(
                f"Sonarr `episode_numbers` missing or empty: {episode_numbers_param!r}",
            )
        episode_numbers = []
        for episode_number in self.MULTI_EPISODE_RE.split(episode_numbers_param):
            if not episode_number.strip():
                continue
            try:
                episode_number = int(episode_number.strip())
            except ValueError as exc:  # pragma: no cover
                raise ValueError(
                    f"Sonarr `episode_number` must be an integer: {episode_number!r}",
                ) from exc
            episode_numbers.append(episode_number)
        stem_append = params.get("stem-append", "")
        if not isinstance(stem_append, str):  # pragma: no cover
            raise ValueError(
                f"Sonarr `stem-append` must be a string: {stem_append!r}",
            )

        # Lookup the Sonarr series DB id in order to lookup the episode and file
        series_id = params.get("series_id")
        if not series_id:  # pragma: no cover
            series_title = params.get("series_title")
            if series_title not in self.series_by_title:  # pragma: no cover
                raise ValueError(
                    f"Sonarr `series_title` not in library: {series_title!r}",
                )
            series_id = self.series_by_title[series_title]

        # Combine all the parameters to lookup the episode file
        episode_paths = self.get_episode_paths(series_id)
        if season_number not in episode_paths:  # pragma: no cover
            raise ValueError(
                f"Sonarr `season_number` not in series {series_id} episodes: "
                f"S{season_number}",
            )
        season_episode_paths = episode_paths[season_number]

        episodes_file_paths = []
        for episode_number in episode_numbers:
            if episode_number not in season_episode_paths:  # pragma: no cover
                logger.error(
                    "Sonarr `episode_number` not in series %s episodes: S%sE%s",
                    series_id,
                    season_number,
                    episode_number,
                )
                continue
            # Assemble a path next to the episode file
            episode_path = pathlib.Path(season_episode_paths[episode_number])
            episodes_file_paths.append(
                episode_path.with_stem(f"{episode_path.stem}{stem_append}").with_suffix(
                    pathlib.Path(basename).suffix,
                ),
            )

        return [str(episode_file_path) for episode_file_path in episodes_file_paths]
