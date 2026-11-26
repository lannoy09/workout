# Workout Tracker Work Notes

## Source files reviewed

- `index.html` — original marathon tracker and its workout data.
- `index-2.html` — companion marathon plan with recovery mobility details.

The new plan uses equipment mentioned in the source plans: Yukon/rotating bar, hex bar, multi-grip bench, landmine, cable row and lat pulldown stations, EZ bar, rope attachment, resistance bands, sliders/gliders, bike trainer, and rower.

## New version

Created `strength-cardio.html`, a 12-week strength and cardio tracker beginning November 23, 2026. It keeps the existing tracker interface and includes:

- Morning strength sessions with a short bike or row warmup.
- Longer, easy aerobic workouts in the evening.
- Saturday trail runs that build gradually, with deload weeks.
- Recovery activity on Sundays and lighter deload weeks.
- Separate workout and log storage keys so it does not reuse the marathon tracker's saved plan or progress.

## Individual lift logging fix

Each strength exercise is displayed as its own card. The user can open a lift and enter sets, reps, weight, and notes; the saved weight and set/rep details appear on that lift's card.

A classification bug initially treated individual lift objects as cardio because they do not have a session-level `exercises` property. `isCardioEntry` now identifies cardio sessions by their explicit type or session shape, so individual lifts open the strength logger and save independently.
