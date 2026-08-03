# garmin-connect-running

[![CI](https://github.com/VincentG3R/garmin-connect-running/actions/workflows/ci.yml/badge.svg)](https://github.com/VincentG3R/garmin-connect-running/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)

Crée des entraînements **course à pied** dans Garmin Connect via l'API interne
utilisée par connect.garmin.com — non documentée officiellement, mais stable et
déjà utilisée par plusieurs outils communautaires.

Scripte des séances avec cibles allure, fréquence cardiaque, cadence et vitesse,
sans passer par le créateur d'entraînement web de Garmin Connect.

## Sommaire

- [Installation](#installation)
- [Authentification](#authentification)
- [Utilisation rapide](#utilisation-rapide)
- [Séances incluses](#séances-incluses)
- [Cibles disponibles](#cibles-disponibles)
- [Composer ses propres séances](#composer-ses-propres-séances)
- [Développement](#développement)
- [Notes techniques](#notes-techniques-vérifiées-empiriquement)
- [Avertissement](#avertissement)

## Installation

```bash
pip install git+https://github.com/VincentG3R/garmin-connect-running.git
```

Ça installe la commande `garmin-running`. Pour contribuer ou modifier le code,
voir [Développement](#développement).

## Authentification

```bash
export GARMIN_EMAIL="ton.email@example.com"
export GARMIN_PASSWORD="ton mot de passe"
garmin-running --running
```

Sans variables d'environnement, le script les demande de façon interactive
(`getpass`, y compris le code MFA si activé). La session est mise en cache dans
`~/.garminconnect` et rafraîchie automatiquement ensuite — pas besoin de se
reconnecter à chaque fois.

## Utilisation rapide

```bash
garmin-running --running                        # fractionne 6x400m
garmin-running --tempo-run                        # sortie tempo (demo cibles allure/FC)
garmin-running --run-walk                          # marche-course 6x3min

garmin-running --running --schedule 2026-08-10       # cree + planifie au calendrier Garmin

garmin-running --list-workouts                         # liste tes entrainements existants
garmin-running --dump-workout 123456789                  # JSON complet d'un entrainement
garmin-running --delete-workout 123456789
```

<details>
<summary><code>garmin-running --help</code></summary>

```
usage: garmin-running [-h] [--list-workouts] [--dump-workout ID]
                       [--delete-workout ID] [--schedule YYYY-MM-DD]
                       [--running] [--tempo-run] [--run-walk]

options:
  -h, --help            show this help message and exit
  --list-workouts       Liste tes entrainements existants (id + nom)
  --dump-workout ID     Affiche le JSON complet d'un entrainement existant
  --delete-workout ID   Supprime un entrainement existant
  --schedule YYYY-MM-DD
                        Planifie les entrainements crees a cette date
  --running             Cree le fractionne CAP 6x400m
  --tempo-run            Cree la seance Tempo 20min (demo cibles allure/FC)
  --run-walk              Cree la seance Marche-course 6x3min
```

</details>

## Séances incluses

| Flag | Séance | Structure |
|---|---|---|
| `--running` | Fractionné 6x400m | échauffement 10min + 6×(400m rapide / 200m récup) + retour au calme 10min |
| `--tempo-run` | Tempo 20min | échauffement 10min (cible FC zone 2) + 20min à allure 5:00→4:50/km (cible allure) + retour au calme 10min |
| `--run-walk` | Marche-course 6x3min | échauffement marche 5min + 6×(3min course / 2min marche récup) + retour au calme marche 5min |

## Cibles disponibles

Toutes les cibles (`targetType`) supportées par l'API Garmin pour la course à pied :

| Cible | Fonction | Unité |
|---|---|---|
| Zone de fréquence cardiaque | `hr_zone_target(1-5)` | zone du profil Garmin |
| FC personnalisée | `hr_range_target(bas, haut)` | bpm |
| Zone d'allure | `pace_zone_target(1-5)` | zone du profil Garmin |
| Allure personnalisée | `pace_range_target(lent, rapide)` | min/km |
| Vitesse personnalisée | `speed_range_target(bas, haut)` | km/h |
| Cadence personnalisée | `cadence_range_target(bas, haut)` | pas/minute |

## Composer ses propres séances

Les helpers `duration_step`, `distance_step`, `rest_step` et `repeat_step`, combinés
aux cibles ci-dessus, permettent de construire n'importe quelle séance structurée :

```python
from garmin_workouts import build_workout, duration_step, repeat_step, hr_zone_target, pace_range_target

workout = build_workout(
    "Ma séance",
    [
        duration_step("warmup", 600.0, step_order=1, target=hr_zone_target(2)),
        repeat_step(
            step_order=2,
            iterations=5,
            nested_steps=[
                duration_step("interval", 180.0, step_order=1, target=pace_range_target(4.5, 4.2)),
                duration_step("recovery", 90.0, step_order=2),
            ],
        ),
        duration_step("cooldown", 600.0, step_order=3),
    ],
)
```

Voir les fonctions `build_running_workout`, `build_tempo_run_workout` et
`build_run_walk_workout` dans `garmin_workouts.py` comme exemples complets.

## Développement

```bash
git clone https://github.com/VincentG3R/garmin-connect-running.git
cd garmin-connect-running
pip install -e ".[dev]"
pytest -v
```

La CI GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) fait
tourner cette même suite de tests sur Python 3.9 à 3.12 à chaque push/PR.

## Notes techniques (vérifiées empiriquement)

- `Garmin(email, password).login(token_store)` met en cache la session ; `client.connectapi(path, method=..., json=...)`
  fait des requêtes authentifiées vers `https://connectapi.garmin.com{path}`.
- Création d'entraînement : `POST /workout-service/workout`.
- `targetType` ne contient que `workoutTargetTypeId`/`workoutTargetTypeKey` —
  `targetValueOne`/`targetValueTwo`/`zoneNumber` sont des champs **frères** de
  `targetType` sur l'étape, pas nichés dedans (schéma confirmé par test croisé
  avec [mkuthan/garmin-workouts](https://github.com/mkuthan/garmin-workouts) et
  [ThomasRondof/GarminWorkoutAItoJSON](https://github.com/ThomasRondof/GarminWorkoutAItoJSON)).
- `pace.zone` est stocké en m/s, pas en min/km : conversion `1000 / (min_par_km * 60)`.
- **Pas encore confirmé par `--dump-workout` sur un vrai entraînement** — teste
  avec un entraînement jetable avant de t'y fier pour de vrai, puis
  supprime-le (`--delete-workout`).

Voir les commentaires en tête de `garmin_workouts.py` pour le détail complet.

## Avertissement

API interne non officielle : peut casser si Garmin change son backend. Ne committe
jamais tes identifiants Garmin ni le contenu de `~/.garminconnect` (déjà exclu par
`.gitignore`).
