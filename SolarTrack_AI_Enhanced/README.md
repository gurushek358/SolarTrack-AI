# SolarTrack AI — Ultimate Interactive Demo

A FastAPI-based solar intelligence dashboard with a polished responsive interface. This is a separate upgraded copy; it does not overwrite earlier project folders.

## Run on Windows / VS Code
1. Extract this ZIP.
2. Open the `SolarTrack_AI+` folder in VS Code.
3. Open Terminal in VS Code.
4. Install dependencies: `python -m pip install -r requirements.txt`
5. Start the app: `python -m uvicorn app.main:app --reload`
6. Open `http://127.0.0.1:8000` (API docs: `http://127.0.0.1:8000/docs`).

## Existing features retained
- Simulated live generation, household load, grid import/surplus, battery SOC and backup estimate
- Panel technology selector and representative module specifications
- Solar tracking angle guidance, household appliance estimates, notifications, reset and pause/resume
- Eight interactive charts, fault injection, rule-based assistant, PDF and CSV exports
- Responsive module navigation and visual feedback

## New in this build
- Interactive 24-module virtual solar array with clickable module inspection and fault-responsive status display
- Rule-based performance investigation with an illustrative health score, evidence cards, severity, and recommended checks
- Refined dark solar-operations theme, improved responsive layout, and clearer module hierarchy

## Important limitations
All telemetry, array module states, forecasts, fault labels, scores, costs and alerts are simulated. The investigation is rule-based, not a trained AI model or validated fault classifier. No real PV modules, inverter, smart meter, weather API, email/SMS, or physical tracker is connected. Never use this demo to make electrical safety decisions.
