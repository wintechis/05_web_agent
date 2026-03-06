"""Tests for parse_predicted and parse_gold_path."""

import pytest
from benchmark.domain.path_parser import extract_uris, normalize_uri, parse_gold_path, parse_predicted


WIKI_A = "https://en.wikipedia.org/wiki/A"
WIKI_B = "https://en.wikipedia.org/wiki/B"
WIKI_C = "https://en.wikipedia.org/wiki/C"
WIKI_D = "https://en.wikipedia.org/wiki/D"


class TestParsePredicted:
    def test_list_predicted_returned_directly(self):
        entry = {"predicted_answer": [WIKI_A, WIKI_B, WIKI_C, WIKI_D]}
        assert parse_predicted(entry) == [WIKI_A, WIKI_B, WIKI_C, WIKI_D]

    def test_list_predicted_filters_blank_strings(self):
        entry = {"predicted_answer": [WIKI_A, "", "  ", WIKI_B]}
        assert parse_predicted(entry) == [WIKI_A, WIKI_B]

    def test_answer_tag_string(self):
        text = f"<answer> {WIKI_A} {WIKI_B} {WIKI_C} {WIKI_D} </answer>"
        entry = {"predicted_answer": text}
        assert parse_predicted(entry) == [WIKI_A, WIKI_B, WIKI_C, WIKI_D]

    def test_empty_predicted(self):
        assert parse_predicted({}) == []
        assert parse_predicted({"predicted_answer": ""}) == []

    def test_string_repr_of_dict_has_trailing_quote_bug(self):
        """Documents the OLD behaviour before fix: str(dict) left trailing quotes on URLs.
        This test confirms extract_uris alone still has the issue — the fix lives upstream
        in _extract_answer_and_task_state which now returns a list, bypassing extract_uris."""
        python_dict_str = f"{{'urls': ['{WIKI_A}', '{WIKI_D}'], 'task_state': 'completed'}}"
        uris = extract_uris(python_dict_str)
        # The regex captures the trailing ' on each URL — extract_uris is not the fix point
        assert any(u.endswith("'") for u in uris), (
            "extract_uris still has the trailing-quote issue; "
            "the fix must be upstream (store list, not string)"
        )


class TestParseGoldPath:
    def test_gold_path_as_list_in_dict(self):
        entry = {"gold_standard_answer": {"path": [WIKI_A, WIKI_B, WIKI_C, WIKI_D]}}
        assert parse_gold_path(entry) == [WIKI_A, WIKI_B, WIKI_C, WIKI_D]

    def test_gold_path_as_list_directly(self):
        entry = {"gold_standard_answer": [WIKI_A, WIKI_B]}
        assert parse_gold_path(entry) == [WIKI_A, WIKI_B]

    def test_gold_path_missing(self):
        assert parse_gold_path({}) == []

    def test_gold_path_filters_blank_entries(self):
        entry = {"gold_standard_answer": {"path": [WIKI_A, "", WIKI_D]}}
        result = parse_gold_path(entry)
        assert "" not in result
        assert WIKI_A in result
        assert WIKI_D in result


class TestNormalizeUri:
    """URI normalization: percent-encoded and Unicode URIs must compare equal."""

    def test_percent_encoded_non_ascii_decoded_to_unicode(self):
        assert normalize_uri("https://en.wikipedia.org/wiki/K%C3%A4larne") == \
            "https://en.wikipedia.org/wiki/Kälarne"

    def test_already_decoded_uri_unchanged(self):
        assert normalize_uri("https://en.wikipedia.org/wiki/Kälarne") == \
            "https://en.wikipedia.org/wiki/Kälarne"

    def test_ascii_uri_unchanged(self):
        assert normalize_uri(WIKI_A) == WIKI_A

    def test_multiple_encoded_segments(self):
        encoded = "https://en.wikipedia.org/wiki/%C3%96stersund_%C3%A4lv"
        decoded = "https://en.wikipedia.org/wiki/Östersund_älv"
        assert normalize_uri(encoded) == decoded

    def test_mixed_encoded_and_plain(self):
        uri = "https://en.wikipedia.org/wiki/Br%C3%A4cke_Municipality"
        assert normalize_uri(uri) == "https://en.wikipedia.org/wiki/Bräcke_Municipality"


class TestParsePredictedNormalization:
    """parse_predicted normalizes percent-encoded URIs to Unicode."""

    def test_list_with_percent_encoded_uris_normalized(self):
        entry = {"predicted_answer": [
            "https://en.wikipedia.org/wiki/K%C3%A4larne",
            "https://en.wikipedia.org/wiki/Br%C3%A4cke_Municipality",
        ]}
        result = parse_predicted(entry)
        assert result == [
            "https://en.wikipedia.org/wiki/Kälarne",
            "https://en.wikipedia.org/wiki/Bräcke_Municipality",
        ]

    def test_string_with_percent_encoded_uris_normalized(self):
        text = "<answer> https://en.wikipedia.org/wiki/K%C3%A4larne https://en.wikipedia.org/wiki/%C3%96stersund </answer>"
        entry = {"predicted_answer": text}
        result = parse_predicted(entry)
        assert result == [
            "https://en.wikipedia.org/wiki/Kälarne",
            "https://en.wikipedia.org/wiki/Östersund",
        ]

    def test_encoded_predicted_matches_decoded_gold(self):
        """Core scenario: percent-encoded predicted URIs equal decoded gold URIs."""
        predicted_entry = {"predicted_answer": [
            "https://en.wikipedia.org/wiki/K%C3%A4larne",
            "https://en.wikipedia.org/wiki/Country",
        ]}
        gold_entry = {"gold_standard_answer": {"path": [
            "https://en.wikipedia.org/wiki/Kälarne",
            "https://en.wikipedia.org/wiki/Country",
        ]}}
        assert parse_predicted(predicted_entry) == parse_gold_path(gold_entry)


class TestParseGoldPathNormalization:
    """parse_gold_path normalizes percent-encoded URIs to Unicode."""

    def test_gold_list_with_percent_encoded_uris_normalized(self):
        entry = {"gold_standard_answer": {"path": [
            "https://en.wikipedia.org/wiki/K%C3%A4larne",
            "https://en.wikipedia.org/wiki/Country",
        ]}}
        result = parse_gold_path(entry)
        assert result[0] == "https://en.wikipedia.org/wiki/Kälarne"

    def test_gold_string_with_percent_encoded_uris_normalized(self):
        entry = {"gold_standard_answer": "https://en.wikipedia.org/wiki/K%C3%A4larne\nhttps://en.wikipedia.org/wiki/Country"}
        result = parse_gold_path(entry)
        assert result[0] == "https://en.wikipedia.org/wiki/Kälarne"
