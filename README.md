# Bincom Election Results

Flask app for the Bincom Software Developer assessment.

**Live site:** https://BoazAyuk.pythonanywhere.com/

## Features
- `/` : View party results for a selected polling unit
- `/lga` : Total score per party for a selected LGA, calculated by joining `polling_unit` with `announced_pu_results` (the `announced_lga_results` table is not used)
- `/new` : Form to add a new polling unit and save scores for all nine parties (ACN, ANPP, CDC, CPP, DPP, JP, LABO, PDP, PPA)

## Tech
Python 3, Flask, SQLite (`bincom.db`, converted from the original Bincom MySQL dump for hosting on PythonAnywhere)

## Run locally
1. `pip install flask`
2. Place `bincom.db` in the same folder as `flask_app.py`
3. `python flask_app.py`
4. Open http://127.0.0.1:5000

## Notes
- Labour is stored as `LABO` because `party_abbreviation` is CHAR(4) in the original schema.
- The original dataset was preserved; no rows were changed.
