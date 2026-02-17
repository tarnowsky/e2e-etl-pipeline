import re
import time
from abc import ABC, abstractmethod

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import (
    SupportedJobSites,
    RAW_DATA_DIR,
    build_data_path,
)


class BaseSiteScraper(ABC):
    def __init__(self, driver: webdriver.Chrome, wait: WebDriverWait):
        self.driver = driver
        self.wait = wait

    @abstractmethod
    def scrape(self, **kwargs) -> str:
        pass


class JustJoinITScraper(BaseSiteScraper):
    class City:
        ALL = "all-locations"
        GDANSK = "gdansk"
        WARSZAWA = "warszawa"
        TROJMIASTO = "trojmiasto"

    class Experience:
        JUNIOR = "junior"
        MID = "mid"
        SENIOR = "senior"
        MANAGER_C_LEVEL = "c-level,mid"

    BASE_URL = "https://justjoin.it/job-offers"

    def _build_url(self, city: str, experience: str, with_salary: bool) -> str:
        salary_param = "yes" if with_salary else "no"
        return f"{self.BASE_URL}/{city}?experience-level={experience}&with-salary={salary_param}"

    def _parse_total_offers(self) -> int:
        h1 = self.wait.until(EC.presence_of_element_located((By.XPATH, "//h1[contains(., 'offers')]")))
        text = h1.text.replace("\xa0", " ")
        nums = re.findall(r"\d[\d\s]*", text)
        if not nums:
            raise ValueError(f"Failed to parse offer count from: {text}")
        return int(nums[-1].replace(" ", ""))

    def _accept_cookies_if_present(self) -> None:
        try:
            self.wait.until(EC.element_to_be_clickable((By.ID, "cookiescript_accept"))).click()
        except Exception:
            return

    def _collect_visible_items(self, seen: dict[str, str]) -> None:
        rows = self.driver.execute_script(
            """
            return Array.from(
                document.querySelectorAll('#up-offers-list ul li[data-index]')
            ).map(li => ({
                idx: li.getAttribute('data-index'),
                html: li.outerHTML
            }));
            """
        )

        for row in rows:
            idx = row["idx"]
            if idx is not None and idx not in seen:
                seen[idx] = row["html"]

    def scrape(
        self,
        city: str,
        experience: str,
        with_salary: bool = True,
        max_stale_rounds: int = 5,
        max_rounds: int = 400,
    ) -> str:
        url = self._build_url(city, experience, with_salary)
        self.driver.get(url)

        self._accept_cookies_if_present()

        try:
            total = self._parse_total_offers()
            print("Total offers (header):", total)
        except Exception:
            print("Failed to parse offer count from header.")

        seen: dict[str, str] = {}
        self._collect_visible_items(seen)

        stale_rounds = 0
        last_count = len(seen)
        last_max_idx = max((int(k) for k in seen.keys()), default=-1)

        for _ in range(max_rounds):
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#up-offers-list ul li[data-index]"))
            )
            self._collect_visible_items(seen)

            current_count = len(seen)
            current_max_idx = max((int(k) for k in seen.keys()), default=-1)

            progressed = (current_count > last_count) or (current_max_idx > last_max_idx)
            stale_rounds = 0 if progressed else stale_rounds + 1
            if stale_rounds >= max_stale_rounds:
                break

            last_count = current_count
            last_max_idx = current_max_idx

            self.driver.execute_script("window.scrollBy(0, 1200);")
            time.sleep(0.35)

        merged_html = "<ul>" + "".join(seen[k] for k in sorted(seen, key=lambda x: int(x))) + "</ul>"
        return merged_html


class DataScraper:
    def __init__(
        self,
        job_site: SupportedJobSites,
        web_driver_options: Options | None = None,
        wait_timeout: int = 10,
    ):
        self.job_site = job_site

        options = web_driver_options or Options()
        if web_driver_options is None:
            options.add_argument("--headless")
            options.add_argument("--window-size=1920,1080")

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, wait_timeout)

        self._scrapers: dict[SupportedJobSites, BaseSiteScraper] = {
            SupportedJobSites.JUSTJOINIT: JustJoinITScraper(self.driver, self.wait)
        }

    def scrape(self, output_dir: str = RAW_DATA_DIR, **kwargs) -> str:
        scraper = self._scrapers[self.job_site]
        merged_html = scraper.scrape(**kwargs)

        city = kwargs.get("city", "")
        experience = kwargs.get("experience", "")

        filepath = build_data_path(output_dir, self.job_site, city, experience, "html")
        with open(filepath, "w", encoding="utf-8") as file:
            file.write(merged_html)

        print(f"Scraping completed. Output saved to: {filepath}")
        return merged_html

    def close(self) -> None:
        self.driver.quit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    
