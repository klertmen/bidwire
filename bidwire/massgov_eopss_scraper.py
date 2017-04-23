from bid import Bid, get_new_identifiers
from datetime import datetime
from lxml import etree, html
from base_scraper import BaseScraper
from db import Session
import logging
import scrapelib
import concurrent.futures
import re

# Logger object for this module
log = logging.getLogger(__name__)

URL_PREFIX = 'http://www.mass.gov/eopss/funding-and-training/'
DOMAIN_NAME = 'http://www.mass.gov'

# homeland-sec/grants/hs-grant-guidance-and-policies.html
# homeland-sec/grants/standard-documents.html
# law-enforce/grants/
# law-enforce/grants/2017-muni-public-safety-staffing-grant.html
# law-enforce/grants/le-grants-public-records.html
# justice-and-prev/grants/
# justice-and-prev/grants/bgp/
# hwy-safety/grants/
# hwy-safety/grants/ffy-2017-traffic-enforcement-grant-program.html
# hwy-safety/grants/ffy2017-hsd-grant-opportunities.html
# hwy-safety/grants/ffy-2017-step.html
# hwy-safety/grants/highway-safety-grants-public-records.html

class MassGovEOPSSScraper(BaseScraper):
    def __init__(self):
        self.url_dict = {
            'homeland-sec/grants/docs/': EOPSSHomelandSecDocsScraper()
        }

    def get_site(self):
        return Bid.Site.MASSGOV_EOPSS

    def scrape(self):
        """Iterates through a single results page and extracts bids.

        This is implemented as follows:
          1. Download each of the results pages.
          2. Extract the bid identifiers from this page.
          3. Check which of those identifiers are not yet in our database.
          4. For each of the identifiers not yet in our database:
            4.1. Download the detail page for each identifier.
            4.2. Extract the fields we are interested in.
            4.3. Create a Bid object and store it in the database.
        """
        scraper = scrapelib.Scraper()
        session = Session()
        for url, eopss_scraper in self.url_dict.items():
            page = scraper.get(URL_PREFIX + url)
            # doc_ids is dictionary: relative URL => title of doc
            doc_ids = eopss_scraper.scrape_results_page(page.content)
            log.info("Found docs: {}".format(doc_ids))
            new_ids = get_new_identifiers(
                session,
                doc_ids.keys(), # relative URL is the identifier
                self.get_site()
            )
            log.info("New docs: {}".format(new_ids))
            new_bids = self.add_new_bids(new_ids, doc_ids)
            session.add_all(new_bids)
            # Save all the new bids from this results page in one db call.
            session.commit()

    def add_new_bids(self, new_ids, doc_ids):
        bids = []
        for new_id in new_ids:
            bids.append(Bid(
                identifier=new_id,
                description=doc_ids[new_id],
                site=self.get_site().name
            ))
        return bids


class EOPSSHomelandSecDocsScraper:
    def scrape_results_page(self, page_str):
        """Scrapes mass.gov/eopss/funding-and-training/homeland-sec/grants/docs/

        Args:
        page_str -- the entire HTML page as a string

        Returns:
        document_ids -- a dictionary of relative URL path => description
        """
        tree = html.fromstring(page_str)
        document_list = tree.xpath('//ul[@class="category"]/li')
        document_ids = {}
        for doc in document_list:
            elem = doc.xpath('./h2/span/a[@class="titlelink"]')[0]
            document_ids[elem.get('href')] = elem.text.strip()
        return document_ids
