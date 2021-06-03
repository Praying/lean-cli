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

from datetime import datetime
from enum import Enum
from typing import List, Optional

from lean.container import container
from lean.models.api import QCFullOrganization, QCResolution
from lean.models.logger import Option
from lean.models.market_hours_database import SecurityType
from lean.models.products.base import Product, ProductDetails
from lean.models.products.security import DataType, SecurityProduct


class OptionStyle(str, Enum):
    American = "American"
    European = "European"


class EquityOptionProduct(SecurityProduct):
    """The EquityOptionProduct class supports downloading equity option data with the `lean data download` command."""

    def __init__(self,
                 data_type: DataType,
                 market: str,
                 ticker: str,
                 resolution: QCResolution,
                 option_style: Optional[OptionStyle],
                 start_date: Optional[datetime],
                 end_date: Optional[datetime]) -> None:
        super().__init__(SecurityType.EquityOption, data_type, market, ticker, resolution, start_date, end_date)

        self._option_style = option_style

    @classmethod
    def get_product_name(cls) -> str:
        return SecurityType.EquityOption.value

    @classmethod
    def build(cls, organization: QCFullOrganization) -> List[Product]:
        data_type = cls._ask_data_type([DataType.Trade, DataType.Quote, DataType.OpenInterest, DataType.Chains])
        market = "USA"
        resolution = "chains" if data_type is DataType.Chains else QCResolution.Minute

        if data_type != DataType.Chains:
            option_style = container.logger().prompt_list("Select the option style of the data", [
                Option(id=s, label=s.value) for s in OptionStyle.__members__.values()
            ])
        else:
            option_style = None

        base_directory = f"option/{market.lower()}/{'chains' if data_type is DataType.Chains else 'minute'}"

        def validate_ticker(t: str) -> bool:
            # Chains data is stored by date instead of by ticker, listing all files takes too long
            if data_type == DataType.Chains:
                return True

            return len(cls._list_files(f"{base_directory}/{t.lower()}/",
                                       fr"/\d+_{data_type.name.lower()}_{option_style.name.lower()}\.zip")) > 0

        ticker = cls._ask_ticker(SecurityType.EquityOption, market, resolution, validate_ticker)

        if data_type != DataType.Chains:
            dates = cls._list_dates(f"{base_directory}/{ticker.lower()}/",
                                    fr"/(\d+)_{data_type.name.lower()}_{option_style.name.lower()}\.zip")
        else:
            dates = None

        start_date, end_date = cls._ask_start_end_date(dates)

        return [EquityOptionProduct(data_type, market, ticker, resolution, option_style, start_date, end_date)]

    def get_details(self) -> ProductDetails:
        details = super().get_details()

        if self._data_type is DataType.Chains:
            details.resolution = "-"

        return details

    def _get_data_files(self) -> List[str]:
        base_directory = f"option/{self._market.lower()}/{'chains' if self._data_type is DataType.Chains else 'minute'}"

        if self._data_type != DataType.Chains:
            return self._get_data_files_in_range(
                f"{base_directory}/{self._ticker.lower()}/",
                fr"/(\d+)_{self._data_type.name.lower()}_{self._option_style.name.lower()}\.zip"
            )

        files = []
        for date in self._get_tradable_dates():
            files.append(f"{base_directory}/{date}/{self._ticker.lower()}.csv")

        return files
