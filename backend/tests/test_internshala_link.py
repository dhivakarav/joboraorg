"""The 'Search on Internshala' deep-link is a CONSTRUCTED URL (like a 'Search on
Google' link) — never a fetched/scraped listing. These tests lock in the verified
Internshala URL patterns and the honest labelling.

Verified-working patterns (manually confirmed to return 200 + apply the keyword
filter on internshala.com):
    internships → https://internshala.com/internships/keywords-{phrase}/
    fresher jobs → https://internshala.com/jobs/keywords-{phrase}/
"""
from app.automation.portals import internshala_search_link


def test_internship_keyword_url():
    d = internshala_search_link("Software Engineer", "India", "internship")
    assert d["search_url"] == "https://internshala.com/internships/keywords-software%20engineer/"
    assert d["label"] == "Search on Internshala"
    assert d["auto_apply"] is False


def test_fresher_uses_jobs_section():
    d = internshala_search_link("Data Science", "India", "fresher")
    assert d["search_url"] == "https://internshala.com/jobs/keywords-data%20science/"


def test_generic_intern_context_uses_internships_section():
    # No explicit type (e.g. internships_only default) → internships section.
    d = internshala_search_link("Backend Developer", "India", "")
    assert d["search_url"] == "https://internshala.com/internships/keywords-backend%20developer/"


def test_empty_query_falls_back_to_section_root():
    d = internshala_search_link("", "India", "internship")
    assert d["search_url"] == "https://internshala.com/internships/"


def test_note_is_honest_about_being_a_search_link():
    note = internshala_search_link("AI ML", "India", "internship")["note"].lower()
    assert "search" in note
    assert "not a specific listing" in note
