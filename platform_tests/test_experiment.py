def test_objective_tradeoff_is_explicit_and_constraints_hold():
    from experiments.compare_milp import compare

    data = compare()
    rows = {row["objective"]: row for row in data["results"]}
    assert rows["deterministic_lexical"]["units"] == 12
    assert rows["deterministic_lexical"]["complete_orders"] == 1
    assert rows["max_complete_orders"]["complete_orders"] == 3
    assert rows["max_min_fraction"]["minimum_served_fraction"] == 0.5
    assert all(row["units"] <= 12 for row in rows.values())

    import json

    assert json.loads(json.dumps(data))["synthetic"] is True
