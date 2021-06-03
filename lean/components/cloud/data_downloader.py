# QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
# Lean CLI v1.0. Copyright 2021 QuantConnect Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import zipfile
from pathlib import Path
from typing import Any, List

import click

from lean.components.api.api_client import APIClient
from lean.components.config.lean_config_manager import LeanConfigManager
from lean.components.util.logger import Logger
from lean.models.errors import RequestFailedError
from lean.models.map_file import MapFile


class DataDownloader:
    """The DataDownloader is responsible for downloading data from the QuantConnect Data Library."""

    def __init__(self, logger: Logger, api_client: APIClient, lean_config_manager: LeanConfigManager):
        """Creates a new CloudBacktestRunner instance.

        :param logger: the logger to use to log messages with
        :param api_client: the APIClient instance to use when communicating with the QuantConnect API
        :param lean_config_manager: the LeanConfigManager instance to retrieve the data directory from
        """
        self._logger = logger
        self._api_client = api_client
        self._lean_config_manager = lean_config_manager
        self._force_overwrite = None
        self._map_files_cache = None

    def download_files(self, data_files: List[Any], overwrite_flag: bool, organization_id: str) -> None:
        """Downloads files from the QuantConnect Data Library to the local data directory.

        :param data_files: the list of data files to download
        :param overwrite_flag: whether the user has given permission to overwrite existing files
        :param organization_id: the id of the organization that should be billed
        """
        data_dir = self._lean_config_manager.get_data_directory()

        for index, data_file in enumerate(data_files):
            self._logger.info(
                f"[{index + 1}/{len(data_files)}] Downloading {data_file.file} ({data_file.vendor.price:,.0f} QCC)")
            self._download_file(data_file.file, overwrite_flag, data_dir, organization_id)

    def download_map_files(self, organization_id: str) -> List[MapFile]:
        """Downloads and parses all available map files.

        :param organization_id: the id of the organization that should be used for downloads
        :return: the list of available map files
        """
        if self._map_files_cache is not None:
            return self._map_files_cache

        map_files = self._api_client.data.list_files("equity/usa/map_files")
        map_files_zip = [m for m in map_files if m.endswith(".zip")][-1]

        data_directory = self._lean_config_manager.get_data_directory()
        map_files_zip_path = data_directory / map_files_zip

        if not map_files_zip_path.is_file():
            self._logger.info("Downloading the latest map files (free)")
            self._download_file(map_files_zip, True, data_directory, organization_id)

        map_files = []
        with zipfile.ZipFile(map_files_zip_path) as zip_file:
            for file_info in zip_file.filelist:
                map_files.append(MapFile.parse(zip_file.read(file_info.filename).decode("utf-8")))

        self._map_files_cache = map_files

        return map_files

    def _download_file(self,
                       relative_file: str,
                       overwrite_flag: bool,
                       data_directory: Path,
                       organization_id: str) -> None:
        """Downloads a single file from the QuantConnect Data Library to the local data directory.

        :param relative_file: the relative path to the file in the data directory
        :param overwrite_flag: whether the user has given permission to overwrite existing files
        :param data_directory: the path to the local data directory
        :param organization_id: the id of the organization that should be billed
        """
        local_path = data_directory / relative_file

        if local_path.exists() and not self._should_overwrite(overwrite_flag, local_path):
            return

        try:
            file_content = self._api_client.data.download_file(relative_file, organization_id)
        except RequestFailedError as error:
            if "File not found" in str(error):
                self._logger.warn("\n".join([
                    f"{relative_file} does not exist in the QuantConnect Data Library",
                    "You have not been billed for this file"
                ]))
                return
            raise error

        local_path.parent.mkdir(parents=True, exist_ok=True)
        with local_path.open("wb+") as f:
            f.write(file_content)

    def _should_overwrite(self, overwrite_flag: bool, path: Path) -> bool:
        """Returns whether we should overwrite existing files.

        :param overwrite_flag: whether the user has given permission to overwrite existing files
        :param path: the path to the file that already exists
        :return: True if existing files may be overwritten, False if not
        """
        if overwrite_flag or self._force_overwrite:
            return True

        self._logger.warn(f"{path} already exists, use --overwrite to overwrite it")

        if self._force_overwrite is None:
            self._force_overwrite = click.confirm(
                "Do you want to temporarily enable overwriting for the previously selected items?",
                default=False)

        if not self._force_overwrite:
            self._logger.warn("You have not been billed for this file")

        return self._force_overwrite
