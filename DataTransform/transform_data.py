import csv
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
import re

from config import (
    SupportedJobSites,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    build_data_path,
    get_latest_file,
)


class BaseSiteTransformer(ABC):
    """Abstract base class for site-specific HTML to structured data transformers."""

    @abstractmethod
    def parse(self, html_content: str) -> list[dict[str, Any]]:
        """Parse HTML content and return list of offer dictionaries."""
        pass

    @abstractmethod
    def get_fieldnames(self) -> list[str]:
        """Return CSV column names for this transformer."""
        pass


class JustJoinITTransformer(BaseSiteTransformer):
    """Transformer for JustJoinIT job offers HTML."""

    def get_fieldnames(self) -> list[str]:
        return ["position", "company_name", "minimum", "maximum", "currency", "pay_period"]

    def _clean_position(self, text: str) -> str:
        """Clean position text from non-ASCII characters."""
        cleaned = ''.join(
            char for char in text 
            if char.isascii() or char.isalnum() or char in ' .,()-'
        ).strip()
        return re.sub(r' {2,}', ' ', cleaned)

    def _parse_salary(self, h6_element) -> dict[str, str]:
        """Parse salary information from h6 element."""
        if not h6_element:
            return {
                "minimum": "",
                "maximum": "",
                "currency": "",
                "pay_period": ""
            }

        salary_spans = [span.get_text(strip=True) for span in h6_element.find_all("span")]

        if len(salary_spans) == 2:
            minimum, currency_pay_period = salary_spans
            maximum = minimum
            try:
                currency, pay_period = currency_pay_period.split('/')
            except ValueError:
                currency, pay_period = currency_pay_period, ""
        elif len(salary_spans) >= 3:
            minimum, maximum, currency_per_time = salary_spans[:3]
            try:
                currency, pay_period = currency_per_time.split('/')
            except ValueError:
                currency, pay_period = currency_per_time, ""
        else:
            return {
                "minimum": "",
                "maximum": "",
                "currency": "",
                "pay_period": ""
            }

        return {
            "minimum": minimum.replace(" ", ""),
            "maximum": maximum.replace(" ", ""),
            "currency": currency,
            "pay_period": pay_period
        }

    def parse(self, html_content: str) -> list[dict[str, Any]]:
        """Parse JustJoinIT HTML and extract job offers."""
        soup = BeautifulSoup(html_content, "lxml")
        offers: list[dict] = []

        ul = soup.find("ul")
        if not ul:
            return offers

        for li in ul.find_all("li", recursive=False):
            # Extract position
            h3 = li.find("h3")
            position_raw = h3.get_text(strip=True) if h3 else ""
            position = self._clean_position(position_raw)

            # Extract salary
            h6 = li.find("h6")
            salary_data = self._parse_salary(h6)

            # Extract company name
            company_p = li.select_one("a > div > div > div > div > div > div > p")
            company_name = company_p.get_text(strip=True) if company_p else ""

            offers.append({
                "position": position,
                "company_name": company_name,
                **salary_data
            })

        return offers


class DataTransformer:
    """
    Main transformer class that handles HTML to CSV transformation.
    
    Can be used standalone with explicit file paths or integrated with DataScraper
    using shared path configuration.
    """

    def __init__(self, job_site: SupportedJobSites):
        self.job_site = job_site
        self._transformers: dict[SupportedJobSites, BaseSiteTransformer] = {
            SupportedJobSites.JUSTJOINIT: JustJoinITTransformer()
        }

    def transform(
        self,
        input_path: str | Path | None = None,
        output_dir: str = PROCESSED_DATA_DIR,
        city: str = "",
        experience: str = "",
        raw_data_dir: str = RAW_DATA_DIR,
    ) -> Path:
        """
        Transform HTML file to CSV.
        
        Args:
            input_path: Explicit path to input HTML file. If None, will auto-detect
                       from raw_data_dir using city and experience.
            output_dir: Base directory for processed output.
            city: City parameter (used for auto-detection and output path).
            experience: Experience level (used for auto-detection and output path).
            raw_data_dir: Base directory for raw data (used for auto-detection).
        
        Returns:
            Path to the generated CSV file.
        """
        transformer = self._transformers[self.job_site]

        # Determine input path
        if input_path is None:
            if not city or not experience:
                raise ValueError(
                    "Either provide input_path explicitly or specify city and experience "
                    "for auto-detection from raw data directory."
                )
            input_path = get_latest_file(raw_data_dir, self.job_site, city, experience)
            if input_path is None:
                raise FileNotFoundError(
                    f"No raw data file found for {self.job_site.value} in {raw_data_dir}"
                )
        
        input_path = Path(input_path)

        # Read and parse HTML
        with open(input_path, encoding="utf-8") as html_file:
            html_content = html_file.read()

        offers = transformer.parse(html_content)
        print(f"Parsed {len(offers)} offers from {input_path}")

        # Determine output path
        if city and experience:
            output_path = build_data_path(output_dir, self.job_site, city, experience, "csv")
        else:
            # Fallback: use input filename structure
            output_path = Path(output_dir) / input_path.parent.relative_to(
                Path(raw_data_dir)
            ) / f"{input_path.stem}.csv"
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write CSV
        fieldnames = transformer.get_fieldnames()
        with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(offers)

        print(f"Transformation completed. Output saved to: {output_path}")
        return output_path

    def transform_from_html(
        self,
        html_content: str,
        output_dir: str = PROCESSED_DATA_DIR,
        city: str = "",
        experience: str = "",
    ) -> tuple[list[dict], Path | None]:
        """
        Transform HTML content directly (useful when chaining with scraper).
        
        Args:
            html_content: Raw HTML string to transform.
            output_dir: Base directory for processed output.
            city: City parameter for output path.
            experience: Experience level for output path.
        
        Returns:
            Tuple of (parsed offers list, output path or None if not saved).
        """
        transformer = self._transformers[self.job_site]
        offers = transformer.parse(html_content)
        print(f"Parsed {len(offers)} offers from HTML content")

        output_path = None
        if city and experience:
            output_path = build_data_path(output_dir, self.job_site, city, experience, "csv")
            
            fieldnames = transformer.get_fieldnames()
            with open(output_path, "w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(offers)

            print(f"Transformation completed. Output saved to: {output_path}")

        return offers, output_path

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
