from config.wind_turbine_database import HISTORICAL_TURBINE_KEYS, TURBINE_DB, get_power_curve, validate_database


def test_catalog_has_six_primary_turbines():
    assert len({k: TURBINE_DB[k] for k in HISTORICAL_TURBINE_KEYS}) == 6


def test_database_invariants():
    assert validate_database() == []


def test_nordex_reference_curve_is_exactly_rated_at_11_mps():
    curve = dict(get_power_curve("Nordex N117/2400"))
    assert curve[11.0] == 2400


def test_vestas_v90_reaches_3mw():
    curve = dict(get_power_curve("Vestas V90-3.0 MW"))
    assert curve[15.0] == 3000
