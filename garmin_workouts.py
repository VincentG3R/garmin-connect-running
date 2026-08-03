#!/usr/bin/env python3
"""
Cree des entrainements de course a pied dans Garmin Connect via l'API interne
utilisee par connect.garmin.com (non documentee officiellement, mais stable et
utilisee par plusieurs outils communautaires actifs).

Installation :
    python3 -m pip install garminconnect

Verifie via inspection reelle du code installe (garminconnect 0.2.8 + garth 0.4.47) :
    - Garmin(email, password).login(token_store) met en cache la session dans
      token_store apres une premiere connexion reussie (rafraichissement auto ensuite).
    - client.connectapi(path, method=..., json=...) fait des requetes authentifiees
      vers https://connectapi.garmin.com{path}.
    - L'endpoint de creation d'entrainement est POST /workout-service/workout,
      confirme par le code source du projet communautaire mkuthan/garmin-workouts.
    - Les IDs de type (sportTypeId=1 pour running, stepTypeId, conditionTypeId,
      workoutTargetTypeId) sont confirmes par deux sources independantes
      (mkuthan/garmin-workouts et ThomasRondof/GarminWorkoutAItoJSON) :
      warmup=1, cooldown=2, interval=3, recovery=4, rest=5, repeat(step)=6 ;
      conditions time=2, distance=3 ; cibles no.target=1, heart.rate.zone=4.

Cibles (targetType/targetValueOne/targetValueTwo/zoneNumber) -- schema relu directement
dans le code source de mkuthan/garmin-workouts (garminworkouts/models/workout.py) et
ThomasRondof/GarminWorkoutAItoJSON (GarminGenJSON.html, table TARGET_TYPE_MAPPING +
fonction parseExecutableStep) :
    - "targetType" ne contient QUE workoutTargetTypeId/workoutTargetTypeKey.
      "targetValueOne"/"targetValueTwo"/"zoneNumber" sont des champs FRERES de
      "targetType" au niveau de l'etape (ExecutableStepDTO), pas niches dedans.
    - no.target = 1 ; cadence.zone = 3 ; heart.rate.zone = 4 ; speed.zone = 5 ;
      pace.zone = 6.
    - heart.rate.zone : soit "zoneNumber" (1-5, zones FC du profil), soit
      targetValueOne/Two en bpm.
    - pace.zone : targetValueOne/Two en metres/seconde (PAS en min/km).
      Conversion : m/s = 1000 / (min_par_km * 60). targetValueOne = borne basse
      (allure la PLUS LENTE = vitesse la plus faible), targetValueTwo = borne
      haute (allure la PLUS RAPIDE).
    - speed.zone : targetValueOne/Two en m/s (km/h / 3.6).
    - cadence.zone : targetValueOne/Two en pas/minute (spm).
    ATTENTION : ce schema de cibles n'a PAS ete confirme par --dump-workout sur un
    vrai entrainement -- seulement par les deux sources communautaires ci-dessus.
    Tester avec un entrainement jetable + --dump-workout avant de s'y fier pour de
    vrai, puis supprimer (--delete-workout).
"""

import argparse
import json
import os
from getpass import getpass

from garminconnect import Garmin

TOKEN_STORE = "~/.garminconnect"

RUNNING_SPORT_TYPE = {"sportTypeId": 1, "sportTypeKey": "running"}

STEP_TYPES = {
    "warmup": {"stepTypeId": 1, "stepTypeKey": "warmup"},
    "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown"},
    "interval": {"stepTypeId": 3, "stepTypeKey": "interval"},
    "recovery": {"stepTypeId": 4, "stepTypeKey": "recovery"},
    "rest": {"stepTypeId": 5, "stepTypeKey": "rest"},
    "repeat": {"stepTypeId": 6, "stepTypeKey": "repeat"},
}

TIME_CONDITION = {"conditionTypeId": 2, "conditionTypeKey": "time"}
DISTANCE_CONDITION = {"conditionTypeId": 3, "conditionTypeKey": "distance"}
ITERATIONS_CONDITION = {"conditionTypeId": 7, "conditionTypeKey": "iterations", "displayable": False}

NO_TARGET = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}
CADENCE_ZONE_TARGET = {"workoutTargetTypeId": 3, "workoutTargetTypeKey": "cadence.zone"}
HR_ZONE_TARGET = {"workoutTargetTypeId": 4, "workoutTargetTypeKey": "heart.rate.zone"}
SPEED_ZONE_TARGET = {"workoutTargetTypeId": 5, "workoutTargetTypeKey": "speed.zone"}
PACE_ZONE_TARGET = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"}


def no_target() -> dict:
    return {"targetType": NO_TARGET}


def hr_zone_target(zone_number: int) -> dict:
    """Cible FC par zone Garmin (1-5, definies dans le profil utilisateur)."""
    return {"targetType": HR_ZONE_TARGET, "zoneNumber": zone_number}


def hr_range_target(low_bpm: float, high_bpm: float) -> dict:
    """Cible FC personnalisee (bpm)."""
    return {"targetType": HR_ZONE_TARGET, "targetValueOne": float(low_bpm), "targetValueTwo": float(high_bpm)}


def pace_zone_target(zone_number: int) -> dict:
    """Cible allure par zone Garmin (1-5, definies dans le profil utilisateur)."""
    return {"targetType": PACE_ZONE_TARGET, "zoneNumber": zone_number}


def pace_range_target(slow_min_per_km: float, fast_min_per_km: float) -> dict:
    """Cible allure personnalisee (min/km, ex: 5.5 pour 5:30/km).
    Convertie en m/s cote Garmin -- non verifie par dump-workout, tester avant usage reel."""
    return {
        "targetType": PACE_ZONE_TARGET,
        "targetValueOne": 1000.0 / (slow_min_per_km * 60.0),
        "targetValueTwo": 1000.0 / (fast_min_per_km * 60.0),
    }


def speed_range_target(low_kmh: float, high_kmh: float) -> dict:
    """Cible vitesse personnalisee (km/h) -- non verifie par dump-workout."""
    return {"targetType": SPEED_ZONE_TARGET, "targetValueOne": low_kmh / 3.6, "targetValueTwo": high_kmh / 3.6}


def cadence_range_target(low_spm: float, high_spm: float) -> dict:
    """Cible cadence personnalisee (pas/minute) -- non verifie par dump-workout."""
    return {"targetType": CADENCE_ZONE_TARGET, "targetValueOne": float(low_spm), "targetValueTwo": float(high_spm)}


def login() -> Garmin:
    token_store = os.path.expanduser(TOKEN_STORE)
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")

    client = Garmin(email, password)
    try:
        client.login(token_store)
        return client
    except Exception:
        pass  # pas de session en cache (ou expiree) -> connexion complete ci-dessous

    if not email:
        email = input("Email Garmin : ")
    if not password:
        password = getpass("Mot de passe Garmin : ")

    client = Garmin(email, password)
    client.login()  # demande le code MFA via input() si necessaire
    client.garth.dump(token_store)
    return client


def duration_step(step_type_key: str, seconds: float, step_order: int, target: dict = None) -> dict:
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": STEP_TYPES[step_type_key],
        "endCondition": TIME_CONDITION,
        "endConditionValue": seconds,
        **(target or no_target()),
    }


def distance_step(step_type_key: str, meters: float, step_order: int, target: dict = None) -> dict:
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": STEP_TYPES[step_type_key],
        "endCondition": DISTANCE_CONDITION,
        "endConditionValue": meters,
        **(target or no_target()),
    }


def rest_step(seconds: float, step_order: int) -> dict:
    return {
        "type": "ExecutableStepDTO",
        "stepOrder": step_order,
        "stepType": STEP_TYPES["rest"],
        "endCondition": TIME_CONDITION,
        "endConditionValue": float(seconds),
        **no_target(),
    }


def repeat_step(step_order: int, iterations: int, nested_steps: list) -> dict:
    return {
        "type": "RepeatGroupDTO",
        "stepOrder": step_order,
        "stepType": STEP_TYPES["repeat"],
        "numberOfIterations": iterations,
        "workoutSteps": nested_steps,
        "endCondition": ITERATIONS_CONDITION,
        "endConditionValue": float(iterations),
        "skipLastRestStep": False,
        "smartRepeat": False,
    }


def build_workout(name: str, steps: list) -> dict:
    return {
        "workoutName": name,
        "sportType": RUNNING_SPORT_TYPE,
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "sportType": RUNNING_SPORT_TYPE,
                "workoutSteps": steps,
            }
        ],
    }


def build_running_workout() -> dict:
    """Fractionne CAP : echauffement 10min + 6x(400m rapide / 200m recup) + retour au calme 10min."""
    interval = distance_step("interval", 400.0, step_order=1)
    recovery = distance_step("recovery", 200.0, step_order=2)

    return build_workout(
        "Fractionne 6x400m",
        [
            duration_step("warmup", 600.0, step_order=1),
            repeat_step(step_order=2, iterations=6, nested_steps=[interval, recovery]),
            duration_step("cooldown", 600.0, step_order=3),
        ],
    )


def build_tempo_run_workout() -> dict:
    """Sortie tempo : echauffement 10min (FC zone 2) + 20min allure tempo 5:00-4:50/km + retour au calme 10min.

    Sert de demo pour les cibles allure/FC (pace.zone / heart.rate.zone) -- tester
    avec --dump-workout apres creation pour confirmer que Garmin affiche bien la
    bonne plage avant de reutiliser ces cibles ailleurs.
    """
    return build_workout(
        "Tempo 20min",
        [
            duration_step("warmup", 600.0, step_order=1, target=hr_zone_target(2)),
            duration_step("interval", 1200.0, step_order=2, target=pace_range_target(5.0, 4.83)),
            duration_step("cooldown", 600.0, step_order=3),
        ],
    )


def build_run_walk_workout() -> dict:
    """Marche-course : echauffement marche 5min + 6x(3min course / 2min marche recup) + retour au calme marche 5min.

    Utile en reprise ou en prevention de blessure. Demo du type d'etape "rest"
    pour la portion marchee."""
    interval = duration_step("interval", 180.0, step_order=1)
    walk = rest_step(120.0, step_order=2)

    return build_workout(
        "Marche-course 6x3min",
        [
            duration_step("warmup", 300.0, step_order=1),
            repeat_step(step_order=2, iterations=6, nested_steps=[interval, walk]),
            duration_step("cooldown", 300.0, step_order=3),
        ],
    )


def create_workout(client: Garmin, workout: dict) -> dict:
    return client.connectapi("/workout-service/workout", method="POST", json=workout)


def delete_workout(client: Garmin, workout_id: int) -> None:
    client.connectapi(f"/workout-service/workout/{workout_id}", method="DELETE")


def schedule_workout(client: Garmin, workout_id: int, date: str) -> None:
    client.connectapi(
        f"/workout-service/schedule/{workout_id}",
        method="POST",
        json={"date": date},
    )


def list_workouts(client: Garmin, limit: int = 20) -> list:
    return client.connectapi("/workout-service/workouts", params={"start": 0, "limit": limit})


def dump_workout(client: Garmin, workout_id: int) -> None:
    workout = client.connectapi(f"/workout-service/workout/{workout_id}")
    print(json.dumps(workout, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-workouts", action="store_true", help="Liste tes entrainements existants (id + nom)")
    parser.add_argument("--dump-workout", type=int, metavar="ID", help="Affiche le JSON complet d'un entrainement existant")
    parser.add_argument("--delete-workout", type=int, metavar="ID", help="Supprime un entrainement existant")
    parser.add_argument("--schedule", metavar="YYYY-MM-DD", help="Planifie les entrainements crees a cette date")
    parser.add_argument("--running", action="store_true", help="Cree le fractionne CAP 6x400m")
    parser.add_argument("--tempo-run", action="store_true", help="Cree la seance Tempo 20min (demo cibles allure/FC)")
    parser.add_argument("--run-walk", action="store_true", help="Cree la seance Marche-course 6x3min")
    args = parser.parse_args()

    client = login()

    if args.list_workouts:
        for w in list_workouts(client):
            print(f"{w['workoutId']:>12}  {w['workoutName']}")
        return

    if args.dump_workout:
        dump_workout(client, args.dump_workout)
        return

    if args.delete_workout:
        delete_workout(client, args.delete_workout)
        print(f"Supprime : {args.delete_workout}")
        return

    builders = []
    if args.running:
        builders.append(build_running_workout)
    if args.tempo_run:
        builders.append(build_tempo_run_workout)
    if args.run_walk:
        builders.append(build_run_walk_workout)

    if not builders:
        parser.error("precise au moins un type a creer : --running, --tempo-run, --run-walk")

    for build in builders:
        workout = build()
        result = create_workout(client, workout)
        workout_id = result["workoutId"]
        print(f"Cree : {workout['workoutName']} (id={workout_id})")
        if args.schedule:
            schedule_workout(client, workout_id, args.schedule)
            print(f"  -> planifie le {args.schedule}")


if __name__ == "__main__":
    main()
