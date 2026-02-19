from enum import Enum
from pathlib import Path
from datetime import datetime


class SupportedJobSites(Enum):
    JUSTJOINIT = "justjoinit"
    PRACUJPLIT = "pracujplit"


SITE_ABBREVIATIONS = {
    SupportedJobSites.JUSTJOINIT: "jjit",
    SupportedJobSites.PRACUJPLIT: "ppl"
}

REGION_ABBREVIATIONS = {
    "warszawa": "waw",
    "warsaw": "waw",
    "gdansk": "gd",
    "trojmiasto": "tri",
    "all-locations": "all",
    "all": "all"
}

EXPERIENCE_ABBREVIATIONS = {
    "junior": "j",
    "mid": "m",
    "senior": "s",
    "intern": "i",
    "c-level": "man",
    "c-level,mid": "man",
    "1": "i",
    "3": "as",
    "17": "j",
    "4": "m",
    "18": "s",
    "19": "ex",
    "20": "man",
    "20%2C6": "man"
}

# Default paths
RAW_DATA_DIR = "data/raw"
STAGING_DATA_DIR = "data/staging"


def get_abbreviations(job_site: SupportedJobSites, city: str, experience: str | int) -> tuple[str, str, str]:
    """Get abbreviations for site, region and experience."""
    site_abbr = SITE_ABBREVIATIONS.get(job_site, str(job_site.value)[:4])
    region_abbr = REGION_ABBREVIATIONS.get(city.lower() if city else "all", city[:3] if city else "all")
    exp_key = str(experience).lower() if isinstance(experience, str) else str(experience)
    exp_abbr = EXPERIENCE_ABBREVIATIONS.get(exp_key, exp_key[:1])
    return site_abbr, region_abbr, exp_abbr


def get_timestamp() -> str:
    """Get current timestamp in ddmmyyyy format."""
    return datetime.now().strftime("%d%m%Y")


def build_data_path(
    base_dir: str,
    job_site: SupportedJobSites,
    city: str,
    experience: str,
    extension: str = "html"
) -> Path:
    """
    Build data path following the structure: base_dir/site/region/experience/timestamp.extension
    Creates directories if they don't exist.
    """
    site_abbr, region_abbr, exp_abbr = get_abbreviations(job_site, city, experience)
    timestamp = get_timestamp()

    output_path = Path(base_dir) / site_abbr / region_abbr / exp_abbr
    output_path.mkdir(parents=True, exist_ok=True)

    return output_path / f"{timestamp}.{extension}"


def get_latest_file(
    base_dir: str,
    job_site: SupportedJobSites,
    city: str,
    experience: str,
    extension: str = "html"
) -> Path | None:
    """
    Get the latest file from the data directory for given parameters.
    Returns None if no files found.
    """
    site_abbr, region_abbr, exp_abbr = get_abbreviations(job_site, city, experience)
    dir_path = Path(base_dir) / site_abbr / region_abbr / exp_abbr

    if not dir_path.exists():
        return None

    files = sorted(dir_path.glob(f"*.{extension}"), reverse=True)
    return files[0] if files else None
