"""app/plantids.py — the identity strings the facility prints on things.

Pure functions, so these are the cheapest possible pins on conventions the
owner stated in words on 2026-09-05. Everything that composes a product code,
a mother-plant ID or a clone ID goes through this module, so a convention can
only drift here.
"""
from datetime import date

import pytest

from app.plantids import (acronym_of, clone_code, grade_str, legacy_plant_code,
                          mother_code, product_code, window_for)


@pytest.mark.parametrize("nominal,expected", [
    (26, (23.40, 28.59)),      # GP_THC26 — the owner's worked example
    (8, (7.20, 8.79)),         # OPM_THC8, the lowest page
    (28, (25.20, 30.79)),      # CJ_THC28 — reaches ABOVE 30 %, which the old
                               # ladder validator forbade outright
    (12, (10.80, 13.19)),
    (18, (16.20, 19.79)),      # J31_THC18
    (7.5, (6.75, 8.24)),       # a fractional nominal still lands on 2 decimals
])
def test_the_window_is_ten_percent_relative_exactly_as_the_page_prints_it(nominal, expected):
    assert window_for(nominal) == expected


def test_a_grade_prints_without_a_trailing_zero():
    # The mother ID embeds the grade (GP26, CLE7.5); "26.0" would be a
    # different, wrong id.
    assert grade_str(26) == "26" and grade_str(26.0) == "26" and grade_str(7.5) == "7.5"


def test_product_code_and_its_acronym_round_trip():
    assert product_code("GP", 26) == "GP_THC26:CBD1"
    assert product_code("CLE", 7.5) == "CLE_THC7.5:CBD1"
    assert acronym_of("GP_THC26:CBD1") == "GP"
    assert acronym_of("J31_THC18:CBD1") == "J31"      # digits belong in an acronym
    assert acronym_of("nonsense") is None


def test_the_mother_id_is_the_owners_five_segments():
    # GP26 = strain + grade · S1 = facility-wide selection campaign ·
    # M03 = mother 3 of that campaign · -2 = its own generation ·
    # _020 = clone number 20 in stock.
    assert mother_code("GP", 26, 1, 3, 2, 20) == "GP26_S1M03-2_020"
    assert mother_code("OPM", 8, 12, 7, 1, 1) == "OPM8_S12M07-1_001"


def test_a_clone_carries_its_mothers_id_plus_cutting_and_clone_number():
    m = "GP26_S1M03-2_020"
    assert clone_code(m, 3, 147) == "GP26_S1M03-2_020-03.147"
    # A mother is cut 6–9+ times at 200–300 clones each, so the clone number is
    # per cutting and both are zero-padded to sort.
    assert clone_code(m, 1, 1) == "GP26_S1M03-2_020-01.001"
    assert clone_code(m, 12, 300) == "GP26_S1M03-2_020-12.300"


def test_a_plant_with_no_known_mother_keeps_the_legacy_id():
    assert legacy_plant_code(date(2026, 7, 6), "GP", 1) == "20260706_GP_0001"
