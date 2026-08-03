# garmin-connect-running

Crée des entraînements **course à pied** dans Garmin Connect via l'API interne
utilisée par connect.garmin.com — non documentée officiellement, mais stable et
déjà utilisée par plusieurs outils communautaires.

Permet de scripter des séances course à pied (avec cibles allure, FC, cadence,
vitesse) sans passer par le créateur d'entraînement web de Garmin Connect.

## Installation

```bash
python3 -m pip install garminconnect
```

## Authentification

```bash
export GARMIN_EMAIL="ton.email@example.com"
export GARMIN_PASSWORD="ton mot de passe"
python3 garmin_workouts.py --running
```

Sans variables d'environnement, le script les demande de façon interactive
(`getpass`, y compris le code MFA si activé). La session est mise en cache dans
`~/.garminconnect` et rafraîchie automatiquement ensuite.

## Utilisation

```bash
python3 garmin_workouts.py --running                          # fractionne 6x400m
python3 garmin_workouts.py --tempo-run                          # sortie tempo (demo cibles allure/FC)
python3 garmin_workouts.py --run-walk                            # marche-course 6x3min

python3 garmin_workouts.py --running --schedule 2026-08-10        # cree + planifie au calendrier Garmin

python3 garmin_workouts.py --list-workouts                         # liste tes entrainements existants
python3 garmin_workouts.py --dump-workout 123456789                  # JSON complet d'un entrainement
python3 garmin_workouts.py --delete-workout 123456789
```

## Composer ses propres séances

Les helpers `duration_step`, `distance_step`, `rest_step` et `repeat_step`, plus
les cibles (`hr_zone_target`, `hr_range_target`, `pace_zone_target`,
`pace_range_target`, `speed_range_target`, `cadence_range_target`) permettent de
construire n'importe quelle séance course structurée. Voir les trois fonctions
`build_*_workout` dans `garmin_workouts.py` comme exemples, et
`build_workout(name, steps)` pour assembler le tout.

## Notes techniques (vérifiées empiriquement)

- `Garmin(email, password).login(token_store)` met en cache la session ; `client.connectapi(path, method=..., json=...)`
  fait des requêtes authentifiées vers `https://connectapi.garmin.com{path}`.
- Création d'entraînement : `POST /workout-service/workout`.
- Cibles (`pace.zone`, `heart.rate.zone`, `cadence.zone`, `speed.zone`) : schéma
  relu dans le code source de deux projets communautaires
  ([mkuthan/garmin-workouts](https://github.com/mkuthan/garmin-workouts),
  [ThomasRondof/GarminWorkoutAItoJSON](https://github.com/ThomasRondof/GarminWorkoutAItoJSON)),
  **pas encore confirmé par `--dump-workout` sur un vrai entraînement** — teste avec un
  entraînement jetable avant de t'y fier, puis supprime-le (`--delete-workout`).
- `pace.zone` est stocké en m/s, pas en min/km : conversion `1000 / (min_par_km * 60)`.

Voir les commentaires en tête de `garmin_workouts.py` pour le détail complet.

## Avertissement

API interne non officielle : peut casser si Garmin change son backend. Ne committe
jamais tes identifiants Garmin ni le contenu de `~/.garminconnect` (déjà exclu par
`.gitignore`).
