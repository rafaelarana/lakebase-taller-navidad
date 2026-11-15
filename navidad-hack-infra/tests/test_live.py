from datetime import datetime, timedelta, timezone

import pytest

from live_sim import Clock, Event, Stop, assign_helpers, build_events, due, to_record
from provision_live import app_grants, live_sql, uc_statements, zerobus_endpoint, zerobus_grants

T0 = datetime(2025, 12, 24, 21, 0, tzinfo=timezone.utc)


def stops(n=200, routes=2, bringer="papa_noel"):
    return [Stop(r, i, r * 10_000 + i, bringer, "Valencia", T0 + timedelta(minutes=i), 39.4, -0.37)
            for r in range(1, routes + 1) for i in range(n)]


def test_helpers_split_each_route_into_contiguous_segments():
    who = assign_helpers(stops(100, 1), 4)
    ids = [who[(1, i)][0] for i in range(100)]
    assert ids == sorted(ids, key=lambda h: int(h.split("-")[1]))  # contiguous
    assert len(set(ids)) == 4 and all(who[(1, i)][2] == "duende" for i in range(100))
    assert assign_helpers(stops(10, 1, "melchor"), 2)[(1, 0)][2] == "paje"


def test_every_stop_gets_one_outcome_and_retries_come_later():
    ss = stops(2000, 2)
    ev = build_events(ss, exception_rate=0.05, seed=1)
    first = {}
    for e in ev:
        first.setdefault(e.stop.household_id, e)
    assert len(first) == len(ss)
    exc = [e for e in ev if e.event_type == "excepcion"]
    assert 0.03 < len(exc) / len(ss) < 0.07
    retried = {e.stop.household_id for e in exc} & {e.stop.household_id for e in ev if e.event_type == "entregado"}
    assert retried  # some exceptions are delivered later
    for hid in retried:
        x = next(e for e in exc if e.stop.household_id == hid)
        d = next(e for e in ev if e.stop.household_id == hid and e.event_type == "entregado")
        assert timedelta(minutes=20) <= d.event_ts - x.event_ts <= timedelta(minutes=40)
    assert [e.event_ts for e in ev] == sorted(e.event_ts for e in ev)


def test_record_matches_bronze_columns_and_uses_microseconds():
    from provision_live import BRONZE_COLUMNS
    e = build_events(stops(1, 1), exception_rate=0)[0]
    rec = to_record(e, sim_run_id="r", year=2025, campaign="nochebuena", sent=T0)
    cols = [c.split()[0] for c in BRONZE_COLUMNS.split(", ")]
    assert list(rec) == cols
    assert rec["event_ts"] == int(T0.timestamp() * 1_000_000)


def test_clock_compresses_the_night():
    c = Clock(T0, T0 + timedelta(hours=10), real_seconds=600, real_start=T0)
    assert c.speed == 60
    assert c.sim_now(T0 + timedelta(seconds=60)) == T0 + timedelta(hours=1)
    ev = build_events(stops(120, 1), exception_rate=0)
    assert len(list(due(ev, 0, T0 + timedelta(minutes=9, seconds=30)))) == 10


def test_sql_and_grants():
    sql = live_sql("navidad_x")
    assert "__SCHEMA__" not in sql and "navidad_x.households_sync" in sql
    assert "CREATE TRIGGER touch" in sql
    g = app_grants("abc-123")
    assert 'GRANT SELECT, INSERT, UPDATE ON navidad_live.agent_action TO "abc-123"' in g
    assert not any("delivery_status" in s and "INSERT" in s for s in g)  # the sink is the only writer
    assert "allowColumnDefaults" not in uc_statements("c", "s")[0]
    assert zerobus_grants("c", "s", "app-id")[-1] == "GRANT MODIFY, SELECT ON TABLE c.s.delivery_events_bronze TO `app-id`"
    with pytest.raises(ValueError):
        uc_statements("c; DROP", "s")


def test_zerobus_endpoint_from_lakebase_host():
    assert (zerobus_endpoint(123, "ep-x.database.us-east-2.cloud.databricks.com")
            == "123.zerobus.us-east-2.cloud.databricks.com")


def test_zerobus_endpoint_on_azure():
    assert (zerobus_endpoint(9, "ep-x.database.westeurope.azuredatabricks.net", cloud="azure")
            == "9.zerobus.westeurope.azuredatabricks.net")


def _city_stops(city, n=6000, start_id=0):
    return [Stop(1, i, start_id + i, "papa_noel", city, T0 + timedelta(seconds=10 * i), 40.0, -3.0) for i in range(n)]


def test_regions_change_rates_and_codes():
    from collections import Counter
    north = build_events(_city_stops("Bilbao"), exception_rate=0.015, seed=3)
    south = build_events(_city_stops("Sevilla", start_id=10_000), exception_rate=0.015, seed=3)
    n_exc = [e for e in north if e.event_type == "excepcion"]
    s_exc = [e for e in south if e.event_type == "excepcion"]
    assert len(n_exc) > 1.6 * len(s_exc)                                  # ×1.5 vs ×0.7
    assert Counter(e.exception_code for e in n_exc).most_common(1)[0][0] == "clima"
    flat = build_events(_city_stops("Bilbao"), exception_rate=0.015, seed=3, regional=False)
    assert len([e for e in flat if e.event_type == "excepcion"]) < len(n_exc)


def test_incident_burst_only_inside_zone_and_window():
    stops = _city_stops("Valencia")
    zone = {s.household_id for s in stops[::2]}          # half the households are inside the zone
    ev = build_events(stops, exception_rate=0.015, seed=5, incident="dana_valencia", incident_households=zone)
    from live_sim import burst_window
    w0, w1 = burst_window(stops, zone)
    in_win = lambda e: w0 <= e.stop.arrived_at <= w1
    exc = [e for e in ev if e.event_type == "excepcion"]
    burst = [e for e in exc if e.stop.household_id in zone and in_win(e)]
    outside = [e for e in exc if e.stop.household_id not in zone]
    n_burst_stops = sum(1 for s in stops if s.household_id in zone and in_win(Event(s.arrived_at, 0, "", s, "", "", "")))
    assert 0.08 < len(burst) / n_burst_stops < 0.16                     # ~12 % inside the zone
    assert len(outside) / (len(stops) / 2) < 0.03                         # regional rate elsewhere
    zone_codes = sum(e.exception_code in ("clima", "direccion_no_encontrada") for e in burst)
    assert zone_codes / len(burst) > 0.9                                  # the zone's codes dominate


def test_burst_hits_a_zone_visited_only_at_the_start_and_end_of_the_night():
    # Hilbert routes visit a zone in short blocks (DANA: deciles 1–2 and 8–9), none in the night's 35–65 %.
    from live_sim import burst_window
    stops = _city_stops("Valencia")
    n = len(stops)
    zone = {s.household_id for k, s in enumerate(stops) if k < 0.2 * n or k > 0.8 * n}
    w0, w1 = burst_window(stops, zone)
    hit = [s for s in stops if s.household_id in zone and w0 <= s.arrived_at <= w1]
    assert 0.25 < len(hit) / len(zone) < 0.35                            # the middle 30 % of the zone's visits
    ev = build_events(stops, exception_rate=0.015, seed=5, incident="dana_valencia", incident_households=zone)
    burst = [e for e in ev if e.event_type == "excepcion" and e.stop in hit]
    assert len(burst) / len(hit) > 0.08                                   # the hot spot is visible
    assert burst_window(stops, set()) is None
