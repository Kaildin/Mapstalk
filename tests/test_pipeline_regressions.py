"""Regression checks for the deduplication and contact-enrichment pipeline.

Set MAPSTALK_REPO to a source checkout. HTTP uses a local fixture server;
only Google Maps acquisition, geocoding and Chrome cleanup are replaced.
"""
import csv
import logging
import os
from pathlib import Path
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest

REPO = Path(os.environ.get("MAPSTALK_REPO", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(REPO))
from src import scraper as s
from src import email_utils as e
from src.dedup_utils import phone_key


@pytest.fixture
def site():
    pages = {"/": (200, '<a href="/azienda/scrivici">Contatti</a>'),
             "/azienda/scrivici": (200, "paolo@artigianiaudit.it")}
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            code, body = pages.get(self.path, (404, ""))
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", pages, calls
    server.shutdown()
    server.server_close()
    thread.join()


def lead(name, phone, website="", reviews=5):
    return dict(nome=name, telefono=phone, comune="Roma", sito_web=website,
                num_recensioni=reviews, indirizzo="Via Roma", keyword="Idraulico")


def pipeline(rows, output=None, **kwargs):
    # Exercise the actual search_contractors processing and CSV writes.
    with patch.object(s, "scrape_with_selenium", return_value=(rows, None, None)), \
         patch.object(s, "build_search_urls", return_value=[]), \
         patch.object(s, "cleanup_chrome_tmp"):
        return s.search_contractors("Roma", ["Idraulico"], lang="it", output_csv=output,
                                    enable_relevance_analysis=kwargs.pop("relevance", False),
                                    **kwargs)


def test_existing_phone_is_skipped_before_http(tmp_path, site, caplog):
    url, _, calls = site
    out = tmp_path / "leads.csv"
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=s.EXTENDED_CSV_FIELDNAMES)
        w.writeheader()
        w.writerow(dict(nome="Vecchio", city="Milano", telefono="+39 342 809 7473"))
    with caplog.at_level(logging.INFO):
        result = pipeline([lead("Altro nome", "3428097473", url)], str(out))
    assert result == []
    assert calls == []
    assert "[Dedup] Telefono gia' presente" in caplog.text
    assert len(list(csv.DictReader(out.open()))) == 1


def test_same_run_dedup_before_site_check_and_email(site):
    url, _, calls = site
    rows = [lead("Primo", "+39 342 809 7473", url), lead("Secondo", "0039 3428097473", url)]
    with patch.object(s, "get_website_status", return_value=dict(ok=True, status_code=200, reason="ok")) as status:
        result = pipeline(rows)
    assert len(result) == 1
    assert status.call_count == 1
    assert calls.count("/") == 1
    assert result[0]["email"] == "paolo@artigianiaudit.it"


def test_no_phone_does_not_merge_different_businesses():
    assert len(pipeline([lead("Uno", ""), lead("Due", "")])) == 2


def test_rejected_lead_does_not_reserve_phone():
    result = pipeline([lead("Scartato", "3428097473", reviews=100), lead("Valido", "3428097473")])
    assert [r["nome"] for r in result] == ["Valido"]


def test_phone_persists_between_calls(tmp_path):
    out = str(tmp_path / "leads.csv")
    assert len(pipeline([lead("Uno", "+39 3428097473")], out)) == 1
    assert pipeline([lead("Due", "3428097473")], out) == []


@pytest.mark.parametrize("national", ["02123456", "061234567"])
def test_short_italian_landline_international_equivalence(national):
    assert phone_key("+39 " + national, "it") == phone_key(national, "it")


def test_discovered_contact_link_is_fetched(site):
    url, _, calls = site
    assert s._extract_emails_from_website(url) == ["paolo@artigianiaudit.it"]
    assert "/azienda/scrivici" in calls
    assert len(calls) <= 6


def test_conventional_contact_path_without_link(site):
    url, pages, calls = site
    pages["/"] = (200, "Home senza link")
    pages["/contact-us"] = (200, "paolo@artigianiaudit.it")
    assert "paolo@artigianiaudit.it" in s._extract_emails_from_website(url)
    assert "/contact-us" in calls


def test_external_link_is_ignored_and_emails_deduplicated(site):
    url, pages, calls = site
    pages["/"] = (200, '<a href="https://external.invalid/contact">Contact</a>'
                       '<a href="/azienda/scrivici#x">Contatti</a>'
                       '<a href="/azienda/scrivici">Contatti</a>paolo@artigianiaudit.it')
    assert s._extract_emails_from_website(url) == ["paolo@artigianiaudit.it"]
    assert calls.count("/azienda/scrivici") == 1
    assert len(calls) <= 6


def test_http_failure_does_not_stop_other_contact_paths(site):
    url, pages, _ = site
    pages["/azienda/scrivici"] = (500, "")
    pages["/contact"] = (200, "paolo@artigianiaudit.it")
    assert s._extract_emails_from_website(url) == ["paolo@artigianiaudit.it"]


def test_generic_business_emails_survive_entire_pipeline(site):
    url, pages, _ = site
    pages["/azienda/scrivici"] = (200, "info@artigianiaudit.it contact@artigianiaudit.it sales@artigianiaudit.it")
    result = pipeline([lead("Artigiano", "3428097473", url)], check_website_alive=False)
    assert set(result[0]["email"].split(", ")) == {
        "info@artigianiaudit.it", "contact@artigianiaudit.it", "sales@artigianiaudit.it"}


def test_valid_unquoted_html_contact_href(site):
    url, pages, calls = site
    pages["/"] = (200, '<a href=/azienda/scrivici>Contatti</a>')
    assert "paolo@artigianiaudit.it" in s._extract_emails_from_website(url)


def test_csv_enrichment_uses_contact_crawl(site):
    from enrich_existing import enrich_row
    url, pages, calls = site
    pages["/azienda/scrivici"] = (200, "info@artigianiaudit.it")
    row = enrich_row(lead("Artigiano", "02123456", url), "fotovoltaico", skip_admin=True)
    assert row["email"] == "info@artigianiaudit.it"
    assert "/azienda/scrivici" in calls


def test_debug_funnel_and_crawl_logs(site, caplog):
    url, _, _ = site
    with caplog.at_level(logging.DEBUG):
        s._extract_emails_from_website(url)
    assert "unique raw candidates" in caplog.text
    assert "retained after cleaning" in caplog.text
    assert "[Email] Crawl completato" in caplog.text


def test_info_shows_crawl_summary_and_hides_debug_funnel(site, caplog):
    url, _, _ = site
    with caplog.at_level(logging.INFO):
        pipeline([lead("Artigiano", "3428097473", url)], check_website_alive=False)
    assert "[Email] Trovate 1 email valide" in caplog.text
    assert "unique raw candidates" not in caplog.text
    assert "[Email] Crawl completato" in caplog.text


def test_debug_logs_zero_candidates(caplog):
    with caplog.at_level(logging.DEBUG):
        assert e.extract_emails_from_text("Nessun indirizzo qui") == []
    assert "0 unique raw candidates" in caplog.text


def test_relevance_stage_does_not_silently_fail(site, caplog):
    url, pages, _ = site
    pages["/"] = (200, "fotovoltaico solare pannelli solari energia rinnovabile inverter accumulo impianto fotovoltaico")
    with caplog.at_level(logging.DEBUG):
        result = pipeline([lead("Artigiano", "3428097473", url)], relevance=True,
                          industry="fotovoltaico", check_website_alive=False)
    assert "[Relevance] Errore" not in caplog.text
    assert result[0]["pertinenza"] is True


def test_gmb_niches_and_token_defaults():
    from src.niches import get_niches, search_niches
    from src.mistral_analyzer import MistralWebsiteAnalyzer, AnalysisResult
    assert len(get_niches("it")) > 1000
    assert len(get_niches("en")) > 1000
    assert "Idraulico" in search_niches("idraul", 20)
    assert MistralWebsiteAnalyzer(api_key="audit-not-used").max_content_length == 5000
    assert AnalysisResult(url="x", is_relevant=False, category="x").confidence == 0


@pytest.mark.parametrize("raw", ["+39 02 123456", "0039 02 123456", "\ue0b0 +39 02 123456"])
def test_short_landline_dedup_in_pipeline(raw):
    assert len(pipeline([lead("Uno", raw), lead("Due", "02123456")])) == 1


def test_national_mobile_starting_with_39_is_preserved():
    assert phone_key("391 234 5678", "it") == "3912345678"


def test_business_email_cleanup_keeps_safety_filters(site):
    url, pages, _ = site
    pages["/azienda/scrivici"] = (200, '''<a href="mailto:INFO@artigianiaudit.it">Scrivici</a>
        info@artigianiaudit.it contact@artigianiaudit.it sales@artigianiaudit.it
        logo@2x.png fake@esempio.it abcdef123456abcdef123456@sentry.io
        privacy@wordpress.com''')
    assert set(e.extract_emails_from_website(url)) == {
        "info@artigianiaudit.it", "contact@artigianiaudit.it", "sales@artigianiaudit.it"}


def test_crawl_logs_only_truly_new_unique_emails(site, caplog):
    url, pages, _ = site
    pages["/"] = (200, '<a href="/azienda/scrivici">Contatti</a>paolo@artigianiaudit.it')
    with caplog.at_level(logging.DEBUG):
        s._extract_emails_from_website(url)
    assert "1 email pulite, 0 nuove email uniche" in caplog.text


def test_crawl_attempt_budget_includes_failures(site):
    url, pages, calls = site
    pages["/"] = (200, "".join(f'<a href="/contact-{i}">Contatti</a>' for i in range(10)))
    assert e.extract_emails_from_website(url) == []
    assert len(calls) == 6


def test_contact_query_route_with_nested_anchor_text(site):
    url, pages, calls = site
    pages["/"] = (200, '<a href="/index.php?page=contatti"><span>Scrivici</span></a>')
    pages["/index.php?page=contatti"] = (200, "info@artigianiaudit.it")
    assert e.extract_emails_from_website(url) == ["info@artigianiaudit.it"]
    assert "/index.php?page=contatti" in calls


def test_relevance_failures_are_visible_at_warning(site, caplog):
    url, _, _ = site
    with patch.object(s.WebsiteRelevanceAnalyzer, "analyze_website_relevance", side_effect=RuntimeError("audit failure")):
        with caplog.at_level(logging.WARNING):
            result = pipeline([lead("Artigiano", "02123456", url)], relevance=True,
                              check_website_alive=False)
    assert len(result) == 1
    assert "[Relevance] Errore" in caplog.text
    assert "audit failure" in caplog.text


@pytest.mark.parametrize("text", ["", None])
def test_empty_input_logs_zero_funnel(text, caplog):
    with caplog.at_level(logging.DEBUG):
        assert e.extract_emails_from_text(text) == []
    assert "0 unique raw candidates" in caplog.text
    assert "0/0 candidates retained after cleaning" in caplog.text
