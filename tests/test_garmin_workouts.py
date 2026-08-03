import math

import garmin_workouts as gw


def test_hr_zone_target():
    target = gw.hr_zone_target(2)
    assert target == {"targetType": gw.HR_ZONE_TARGET, "zoneNumber": 2}


def test_hr_range_target():
    target = gw.hr_range_target(120, 150)
    assert target["targetType"] == gw.HR_ZONE_TARGET
    assert target["targetValueOne"] == 120.0
    assert target["targetValueTwo"] == 150.0


def test_pace_range_target_converts_min_per_km_to_m_per_s():
    target = gw.pace_range_target(5.0, 4.83)
    assert target["targetType"] == gw.PACE_ZONE_TARGET
    assert math.isclose(target["targetValueOne"], 1000.0 / (5.0 * 60.0))
    assert math.isclose(target["targetValueTwo"], 1000.0 / (4.83 * 60.0))
    # allure plus lente (min/km plus grand) -> vitesse plus faible
    assert target["targetValueOne"] < target["targetValueTwo"]


def test_speed_range_target_converts_kmh_to_ms():
    target = gw.speed_range_target(10.0, 15.0)
    assert math.isclose(target["targetValueOne"], 10.0 / 3.6)
    assert math.isclose(target["targetValueTwo"], 15.0 / 3.6)


def test_cadence_range_target():
    target = gw.cadence_range_target(170, 180)
    assert target["targetType"] == gw.CADENCE_ZONE_TARGET
    assert target["targetValueOne"] == 170.0
    assert target["targetValueTwo"] == 180.0


def test_duration_step_default_is_no_target():
    step = gw.duration_step("warmup", 600.0, step_order=1)
    assert step["targetType"] == gw.NO_TARGET
    assert step["endConditionValue"] == 600.0
    assert step["stepType"] == gw.STEP_TYPES["warmup"]


def test_duration_step_target_fields_are_siblings_not_nested():
    """Regression test: targetValueOne/targetValueTwo/zoneNumber must be siblings
    of targetType on the step, never nested inside the targetType dict itself."""
    step = gw.duration_step("interval", 1200.0, step_order=1, target=gw.pace_range_target(5.0, 4.83))
    assert step["targetType"] == gw.PACE_ZONE_TARGET
    assert "targetValueOne" in step
    assert "targetValueTwo" in step
    assert "targetValueOne" not in step["targetType"]
    assert "zoneNumber" not in step["targetType"]


def test_distance_step():
    step = gw.distance_step("interval", 400.0, step_order=1)
    assert step["endCondition"] == gw.DISTANCE_CONDITION
    assert step["endConditionValue"] == 400.0


def test_rest_step():
    step = gw.rest_step(120.0, step_order=2)
    assert step["stepType"] == gw.STEP_TYPES["rest"]
    assert step["endConditionValue"] == 120.0
    assert step["targetType"] == gw.NO_TARGET


def test_repeat_step_wraps_nested_steps():
    nested = [gw.duration_step("interval", 180.0, step_order=1), gw.rest_step(120.0, step_order=2)]
    step = gw.repeat_step(step_order=2, iterations=6, nested_steps=nested)
    assert step["type"] == "RepeatGroupDTO"
    assert step["numberOfIterations"] == 6
    assert step["workoutSteps"] == nested


def test_build_workout_uses_running_sport_type():
    workout = gw.build_workout("Test", [gw.duration_step("warmup", 60.0, step_order=1)])
    assert workout["workoutName"] == "Test"
    assert workout["sportType"] == gw.RUNNING_SPORT_TYPE
    assert workout["workoutSegments"][0]["sportType"] == gw.RUNNING_SPORT_TYPE
    assert len(workout["workoutSegments"][0]["workoutSteps"]) == 1


def test_build_running_workout_structure():
    workout = gw.build_running_workout()
    steps = workout["workoutSegments"][0]["workoutSteps"]
    assert len(steps) == 3
    assert steps[1]["type"] == "RepeatGroupDTO"
    assert steps[1]["numberOfIterations"] == 6


def test_build_tempo_run_workout_uses_hr_and_pace_targets():
    workout = gw.build_tempo_run_workout()
    steps = workout["workoutSegments"][0]["workoutSteps"]
    assert steps[0]["targetType"] == gw.HR_ZONE_TARGET
    assert steps[1]["targetType"] == gw.PACE_ZONE_TARGET


def test_build_run_walk_workout_uses_rest_step_for_walk():
    workout = gw.build_run_walk_workout()
    repeat = workout["workoutSegments"][0]["workoutSteps"][1]
    walk_step = repeat["workoutSteps"][1]
    assert walk_step["stepType"] == gw.STEP_TYPES["rest"]
