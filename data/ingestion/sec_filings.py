"""
SEC EDGAR filing ingestion (10-K and 10-Q).
Uses the free EDGAR submissions and Archives APIs — no key required.

Flow:
  1. Resolve ticker → CIK via EDGAR's company_tickers.json (cached once per run)
  2. Fetch submission history → accession numbers + primaryDocument filenames
  3. Download the primaryDocument (the actual .htm/.xml filing, not the SGML envelope)
  4. Extract MD&A section, store raw text via storage backend, write metadata to PostgreSQL
"""
import logging
import re
import time
from datetime import date
from functools import lru_cache

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import ALL_TICKERS
from data.storage.db_client import insert_filing
from data.storage.s3_client import filing_s3_filename, upload_text

logger = logging.getLogger(__name__)

EDGAR_BASE        = "https://data.sec.gov"
EDGAR_SUBMISSIONS = f"{EDGAR_BASE}/submissions/CIK{{cik}}.json"
EDGAR_ARCHIVES    = "https://www.sec.gov/Archives/edgar/data"
HEADERS           = {"User-Agent": "FinanceProject adisingh2256@gmail.com"}

FILING_TYPES  = {"10-K", "10-Q"}
MIN_PERIOD    = date(2020, 1, 1)   # how far back to backfill
REQUEST_DELAY = 0.12               # SEC guideline: stay under 10 req/sec


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(tickers: list[str] | None = None) -> int:
    """Pull 10-K and 10-Q filings for all tickers. Returns total filings stored."""
    tickers = tickers or ALL_TICKERS
    total = 0
    for ticker in tickers:
        try:
            cik = _resolve_cik(ticker)
            if not cik:
                logger.warning("CIK not found for %s", ticker)
                continue
            total += _ingest_ticker_filings(ticker, cik)
        except Exception as exc:
            logger.error("Failed filings for %s: %s", ticker, exc)
    logger.info("SEC filings ingest complete — %d stored", total)
    return total


# ---------------------------------------------------------------------------
# Step 1 — Resolve ticker → CIK
# Cached: the full company_tickers.json (~1 MB) is fetched ONCE per process
# and reused for every ticker lookup.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _fetch_ticker_map() -> dict[str, str]:
    """
    Download EDGAR's canonical ticker→CIK map and return it as
    {TICKER_UPPER: zero_padded_cik_string}.
    Cached for the lifetime of the process.
    """
    resp = requests.get(
        "https://www.sec.gov/files/company_tickers.json",
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        entry["ticker"].upper(): str(entry["cik_str"]).zfill(10)
        for entry in data.values()
    }


def _resolve_cik(ticker: str) -> str | None:
    ticker_map = _fetch_ticker_map()
    return ticker_map.get(ticker.upper())


# ---------------------------------------------------------------------------
# Step 2 — Fetch filing list for one ticker
# No @retry here — the loop calls _fetch_and_store_filing which handles
# its own retries per filing, so a transient error on one filing doesn't
# restart the entire ticker from scratch.
# ---------------------------------------------------------------------------

def _ingest_ticker_filings(ticker: str, cik: str) -> int:
    time.sleep(REQUEST_DELAY)
    url  = EDGAR_SUBMISSIONS.format(cik=cik)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    submissions = resp.json()

    count = 0
    count += _process_filings_block(ticker, cik, submissions.get("filings", {}).get("recent", {}))

    # EDGAR paginates older filings into separate JSON files.
    # For MIN_PERIOD=2020 this is usually not needed, but handled for correctness.
    for extra_file in submissions.get("filings", {}).get("files", []):
        filing_to = extra_file.get("filingTo", "")
        if filing_to and filing_to < MIN_PERIOD.isoformat():
            # All entries in this page are older than our cutoff — skip
            continue
        extra_url  = f"{EDGAR_BASE}/submissions/{extra_file['name']}"
        extra_resp = requests.get(extra_url, headers=HEADERS, timeout=20)
        extra_resp.raise_for_status()
        count += _process_filings_block(ticker, cik, extra_resp.json())

    logger.info("%s (CIK %s): %d filings stored", ticker, cik, count)
    return count


def _process_filings_block(ticker: str, cik: str, filings_data: dict) -> int:
    """Process one block of filings (either 'recent' or a paginated extra file)."""
    forms         = filings_data.get("form", [])
    dates         = filings_data.get("filingDate", [])
    periods       = filings_data.get("reportDate", [])
    accessions    = filings_data.get("accessionNumber", [])
    primary_docs  = filings_data.get("primaryDocument", [])

    count = 0
    for form, filed_str, period_str, accession, primary_doc in zip(
        forms, dates, periods, accessions, primary_docs
    ):
        if form not in FILING_TYPES:
            continue
        try:
            period = date.fromisoformat(period_str) if period_str else None
        except ValueError:
            period = None
        if period and period < MIN_PERIOD:
            continue

        stored = _fetch_and_store_filing(
            ticker, cik, form, filed_str, period, accession, primary_doc
        )
        if stored:
            count += 1

    return count


# ---------------------------------------------------------------------------
# Step 3 — Download and store one filing
# @retry is here, on the individual filing, so a failure retries only that
# one document rather than restarting the whole ticker loop.
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=15))
def _fetch_and_store_filing(
    ticker:      str,
    cik:         str,
    form:        str,
    filed_str:   str,
    period:      date | None,
    accession:   str,
    primary_doc: str,
) -> bool:
    """
    Download the primary filing document, extract MD&A, persist to storage + DB.
    Returns True if successfully stored, False if skipped/failed.
    """
    if not primary_doc:
        logger.warning("%s: no primaryDocument for accession %s — skipping", ticker, accession)
        return False

    accession_clean = accession.replace("-", "")
    cik_int         = int(cik)   # URL uses un-padded integer

    # ----------------------------------------------------------------
    # This is the correct URL — the named primary document (.htm / .xml),
    # NOT the SGML envelope (<accession>.txt) which wraps all sub-files
    # and does not contain extractable narrative text.
    # ----------------------------------------------------------------
    doc_url = f"{EDGAR_ARCHIVES}/{cik_int}/{accession_clean}/{primary_doc}"

    time.sleep(REQUEST_DELAY)
    resp = requests.get(doc_url, headers=HEADERS, timeout=45)
    resp.raise_for_status()
    raw_text = resp.text

    mda_text = _extract_mda(raw_text)

    s3_filename = filing_s3_filename(ticker, accession, form)
    s3_path     = upload_text(raw_text, "filings", s3_filename)

    filed_at = date.fromisoformat(filed_str) if filed_str else None
    insert_filing({
        "ticker":           ticker,
        "cik":              cik,
        "type":             form,
        "period":           period,
        "filed_at":         filed_at,
        "accession_number": accession,
        "s3_path":          s3_path,
        "parsed_mda":       mda_text,
    })
    return True


# ---------------------------------------------------------------------------
# Step 4 — Extract the MD&A section from raw filing text
# Works on both HTML filings (.htm) and plain-text filings (.txt).
# Searches for "Item 7" header, captures until "Item 7A" or "Item 8".
# ---------------------------------------------------------------------------

_MDA_START = re.compile(
    r"(?i)item\s+7\.?\s*[—–\-]?\s*management[\s\S]{0,80}?discussion",
    re.DOTALL,
)
_MDA_END = re.compile(
    r"(?i)(item\s+7a\.?\s*[—–\-]?\s*quantitative|item\s+8\.?\s*[—–\-]?\s*financial)",
    re.DOTALL,
)


def _extract_mda(raw: str) -> str | None:
    # Strip HTML if present — many modern filings are inline XBRL (.htm)
    if re.search(r"<html", raw[:2000], re.IGNORECASE):
        soup = BeautifulSoup(raw, "lxml")
        text = soup.get_text(separator="\n")
    else:
        text = raw

    # Collapse excessive whitespace introduced by HTML stripping
    text = re.sub(r"\n{3,}", "\n\n", text)

    start_m = _MDA_START.search(text)
    if not start_m:
        return None

    snippet = text[start_m.start():]
    end_m   = _MDA_END.search(snippet)
    if end_m:
        snippet = snippet[: end_m.start()]

    # Cap at 50k characters to keep the DB column manageable
    return snippet[:50_000].strip() or None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
