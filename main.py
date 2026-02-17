from DataExtract import DataScraper, SupportedJobSites, JustJoinITScraper
from DataTransform import DataTransformer

RAW_DATA_DIR = "./data/raw"
STAGING_DATA_DIR = "./data/staging"

if __name__ == '__main__':
    city = JustJoinITScraper.City.TROJMIASTO
    experience = JustJoinITScraper.Experience.JUNIOR

    # Scrape data
    with DataScraper(SupportedJobSites.JUSTJOINIT) as scraper:
        scraper.scrape(
            city=city,
            experience=experience,
            with_salary=True,
            output_dir=RAW_DATA_DIR,
        )

    # Transform data
    with DataTransformer(SupportedJobSites.JUSTJOINIT) as transformer:
        transformer.transform(
            city=city,
            experience=experience,
            raw_data_dir=RAW_DATA_DIR,
            output_dir=STAGING_DATA_DIR,
        )