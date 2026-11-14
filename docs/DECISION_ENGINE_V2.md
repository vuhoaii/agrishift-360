# RiceShift Decision Engine v2 — Task 2 handoff

Completed locally on 2026-11-15 (Asia/Saigon). Scope: Task 2 only. No commit, push or deployment.

## Outcome and scientific status

The water component now responds continuously to rainfall deficit magnitude and seasonal dry-day frequency. Average temperature and hot-day counts are evaluated separately in the explanations and structured risk indicators. They deliberately receive **no numerical penalty**: the archive does not establish exposure during crop growth stages, and a defensible crop response function is unavailable.

This is an **experimental preference-screening model**, not validated agronomic suitability, a forecast, an irrigation calculation, a yield/profit estimate or a success probability. Greater sensitivity to NASA data does not constitute agronomic validation. The existing three priority weight sets and two crop identifiers remain unchanged.

## Task 1 data inspection and preservation

The active payload is `RiceShift/data/processed/climate_payload_latest.json`. It reports 2006-01-01 through 2025-12-31, 7,305 daily records, and 59 complete eligible seasons: 19 Đông Xuân, 20 Hè Thu and 20 Thu Đông. Đông Xuân is labeled by its ending year, so its eligible labels are 2007–2025. The engine uses 151 or 152 days for these analog seasons, 122 for Hè Thu and 92 for Thu Đông.

P50/P25 select a **single complete historical season nearest the empirical rainfall percentile**. All indicators belong to that same analog; they are not independently sampled percentiles. The normal analog's rainfall is the denominator, not the exact empirical median value. These are historical comparisons, not next-season forecasts.

| Season | Scenario / analog year | Rain mm | Mean °C | Tmax >35°C days | Rain <1 mm days |
| --- | --- | ---: | ---: | ---: | ---: |
| Đông Xuân | P50 / 2025 | 218.73 | 27.60 | 48 | 113 |
| Đông Xuân | P25 / 2008 | 162.66 | 27.58 | 54 | 119 |
| Hè Thu | P50 / 2006 | 594.07 | 28.34 | 25 | 35 |
| Hè Thu | P25 / 2013 | 487.83 | 28.56 | 21 | 52 |
| Thu Đông | P50 / 2011 | 581.63 | 26.69 | 0 | 22 |
| Thu Đông | P25 / 2010 | 505.49 | 26.99 | 0 | 23 |

For example, Hè Thu P25 is slightly warmer on average but has fewer hot days than P50. No inference from lower rainfall to higher heat is made.

All nine files under `RiceShift/data` retained identical SHA-256 hashes during this task. Neither NASA observations nor the pipeline/updater were edited.

Active payload SHA-256:
`7c55e90171591b391143377295366a4fcc02d6b22096d8a16fc4028225fa5f1f`

## Scoring formula and rationale

For selected rainfall R, same-season normal-analog rainfall R0, dry-day count n and actual analog-season length N:

```text
D = max(0, 1 - R/R0)                       # relative rainfall deficit, 0–1
F = n/N                                   # fraction of days with rain <1 mm
Q = 0.5*D + 0.5*F                         # bounded historical water-pressure proxy
W = clamp(B - E*C*Q, 0, 2)                # higher means less screening pressure
score = round(50 * sum(weight * component), 1)
```

| Parameter | Available irrigation | Limited irrigation |
| --- | ---: | ---: |
| B, starting water component | 2 | 1 |
| E, climate exposure multiplier | 0.25 | 1 |

C is 1 for rice and 0.5 for sesame. Diversity remains 0 for rice and 2 for sesame; continuity remains 2 for rice and 0 for sesame.

**Every point mapping, starting level, multiplier, equal share and goal weight is an unvalidated experimental assumption.** In particular, C = 0.5 is not a measured water-demand ratio, and E = 0.25 is not a measured irrigation protection factor. Qualitative evidence motivates their directions only. There are no fitted yield curves or tuned winner targets.

Rain above the normal analog receives no extra numerical benefit. This avoids assuming indefinitely increasing rainfall improves suitability. Drainage screening and warnings address potential wet-field concerns; seasonal rainfall cannot establish waterlogging. The dry-day term is an occurrence-frequency proxy, not crop drought. It counts all days below 1 mm, not consecutive dry days. Equal weighting bounds the combined contribution; it does not eliminate correlation between rainfall totals and dry-day frequency.

Components retain full precision for scoring. Only the final score is rounded to one decimal; the component display uses three decimals. Comparison uses the displayed scores, conservatively treating equal displayed scores as a tie. Sorting remains deterministic by option ID, and ties never produce a leader.

| User priority | Water | Diversity | Continuity |
| --- | ---: | ---: | ---: |
| save_water | 0.70 | 0.10 | 0.20 |
| protect_soil | 0.25 | 0.60 | 0.15 |
| keep_practice | 0.25 | 0.10 | 0.65 |

Mean temperature is reported with its same-season P50-analog difference. The Tmax >35°C count is separately reported for both crops. A positive count prompts checking rice flowering dates. The existing pipeline's 35°C cutoff is an exposure indicator, not a universally valid injury threshold. No equivalent sesame injury threshold or temperature-to-score relationship is invented. Zero hot days does not establish that all heat risks are absent.

## Screening and hard-blocking review

| Condition | v2 treatment | Evidence / interpretation |
| --- | --- | --- |
| Unknown irrigation | Both options need information; no scores | Essential water-management information missing |
| Unknown or unconfirmed planting calendar | Both need information; no scores | Conservative prototype completeness policy; pilot season may not match crop duration or variety |
| Unknown salinity | Both need information; no scores | Conservative policy; absence of a measurement is not evidence of safety |
| Reported salinity | Both require local verification; no scores | A yes/no flag supplies neither ECe nor ECw, exposure duration or variety response |
| Poor sesame drainage | Sesame requires local verification/improvement; no score | Waterlogging sensitivity is established, but the categorical input does not measure actual saturation |
| Unknown sesame drainage | Sesame needs information; no score | Essential sesame site information missing |
| Missing pH | Checklist item; optional, as before | Does not invent an optimum or silently certify soil suitability |
| Sesame pH outside 5.5–7.0 | Reference-range warning; no automatic exclusion | Regional extension guidance, with limited optimal-pH research |
| Invalid/missing rainfall, or nonpositive normal rainfall | Translatable ValueError; JSON route returns 400 | Cannot calculate a meaningful rainfall comparison |
| Missing/invalid mean temperature, hot/dry counts or analog year in either selected or normal record | Both unranked; report remains valid with null scores | Explicit **experimental completeness policy**, including advisory thermal fields; missing evidence must not appear safe |

Poor drainage and salinity previously hard-blocked sesame. They now use `needs_info` with machine-readable `local_verification` classifications. Biological sesame waterlogging sensitivity is established; a categorical field is not an established field-specific exclusion criterion. None of the current inputs establish a universal hard exclusion, so v2 does not emit `blocked` automatically. The website retains support for that legacy status. This does **not** authorize planting sesame in waterlogged conditions.

An individually scored rice option is not declared the winner when sesame cannot be ranked. A leader requires both options to have scores.

Climate values must be finite JSON numbers; booleans and numeric strings are not treated as observations. Counts must be whole numbers between zero and the actual season length. Broad temperature data-quality bounds of −100 to 100°C reject fill values; these are technical sanity checks, not agronomic thresholds. Invalid indicators are reported explicitly rather than replaced with zero.

## Old-model sensitivity and comparison matrix

The old model used water = 2 for both crops with available irrigation. With limited irrigation, rice switched instantly from 1 to 0 for any negative rainfall difference, while sesame remained at 1. Temperature, hot days and dry days did not affect scoring. Thus a tiny negative anomaly could change a leader, while a large further decrease had no effect.

Before editing the engine, 144 results were captured from v1, identified by SHA-256:
`c094a2703b593a1847a6f48b6e2ca7f7c9ca7e13d6307569bbde6330e79da15f`

The frozen fixture records both options' statuses, scores, water components and the leader. The reproducible matrix is:

- All 3 seasons × 2 scenarios × 3 goals × 8 farming profiles = 144 cases / 288 option rows.
- Every profile uses pH 6.5.
- Profiles: good drainage/limited irrigation; good drainage/available irrigation; poor drainage; unknown drainage; unknown irrigation; reported salinity; unknown salinity; unconfirmed calendar.
- Unless explicitly varied: drainage good, irrigation limited, salinity no, calendar confirmed.
- Both versions use the same corrected payload. The comparison script rejects a different payload hash.

Artifacts:

- [Full comparison CSV](decision-engine-v2-comparison.csv)
- [Frozen v1 baseline](../RiceShift/tests/fixtures/decision_engine_v1_baseline.json)
- [Reproduction script](../RiceShift/scripts/compare_decision_engines.py)

Observed results:

- 108 option rows have numerical scores in both versions; all 108 scores differ.
- 126 option statuses differ, principally from the revised verification gates.
- 39 case leaders differ: 36 become unranked because of unknown salinity or an unconfirmed calendar, and 3 fully specified cases change from sesame to rice under save_water/P25/limited irrigation.
- Among all 36 fully specified cases, save_water and keep_practice lead with rice; protect_soil leads with sesame. This is an observed consequence of the retained assumptions, not evidence of crop suitability.

Representative save_water cases, good drainage, no reported salinity, pH 6.5, calendar confirmed:

| Season / scenario | Irrigation | v1 rice / sesame | v2 rice / sesame |
| --- | --- | --- | --- |
| Đông Xuân / P50 | limited | 55.0 / 45.0 | 41.9 / 38.5 |
| Đông Xuân / P25 | limited | 20.0 / 45.0 | 36.8 / 35.9 |
| Hè Thu / P50 | limited | 55.0 / 45.0 | 50.0 / 42.5 |
| Hè Thu / P25 | limited | 20.0 / 45.0 | 44.4 / 39.7 |
| Thu Đông / P50 | limited | 55.0 / 45.0 | 50.8 / 42.9 |
| Thu Đông / P25 | limited | 20.0 / 45.0 | 48.3 / 41.7 |
| Hè Thu / P50 | available | 90.0 / 80.0 | 88.7 / 79.4 |
| Hè Thu / P25 | available | 90.0 / 80.0 | 87.4 / 78.7 |

The CSV attributes changes to the continuous rainfall rule and the new dry-day term, with unrounded component contributions. For Hè Thu/P25/limited/save_water, rice receives +31.870 points from replacing the old all-or-nothing rainfall rule and −7.459 from dry-day frequency: 20.0 becomes 44.4 after rounding. Sesame receives −1.565 and −3.730: 45.0 becomes 39.7. Temperature/hot-day numerical contributions are explicitly zero; their changes affect explanations.

Isolated sensitivity experiments use in-memory copies of Hè Thu/P25 with all other fields fixed. They do not edit NASA data or represent new historical observations:

| Perturbation | v2 rice / sesame | Interpretation |
| --- | --- | --- |
| None: rain 487.83 mm, mean 28.56°C, hot days 21, dry days 52 | 44.4 / 39.7 | Reference |
| Rain alone becomes 594.07 mm | 47.5 / 41.3 | Continuous water improvement |
| Rain alone becomes 594.0699 mm | 47.5 / 41.3 | Raw components differ slightly; rounded scores agree near P50 |
| Rain alone becomes 300 mm | 38.9 / 36.9 | Larger deficit changes both water components |
| Mean temperature alone increases 2°C | 44.4 / 39.7 | Mean-temperature explanation changes; no invented penalty |
| Hot-day count alone becomes 40 | 44.4 / 39.7 | Exposure indicator changes independently; no invented penalty |
| Dry-day count alone becomes 72 | 41.5 / 38.3 | Dry-day component changes independently of rainfall total |

For all negative-rainfall perturbations, v1 would retain 20/45; it ignores the other three indicators. At rainfall equal to the normal analog it jumps to 55/45.

### Remaining priority dominance

For comparable options, before rounding:

`rice score − sesame score = 100*(continuity_weight − diversity_weight) − 25*water_weight*E*Q`.

With 0 ≤ Q ≤ 1, protect_soil always favors sesame and keep_practice always favors rice under these fixed weights. Available-irrigation save_water also always favors rice. Limited-irrigation save_water crosses only when Q > 4/7; none of the six actual analogs reaches that experimental boundary. This is an algebraic ranking boundary, not an agronomic threshold. Coefficients were not adjusted to create flips or preserve old winners. These invariants remain a material limitation of the preference design.

## Evidence and interpretation limits

References support qualitative mechanisms and specific reference definitions, **not the numerical v2 scoring coefficients**.

| Reference | Supported use and limit |
| --- | --- |
| [NASA POWER methodology](https://power.larc.nasa.gov/docs/methodology/) | Meteorological products combine gridded model/satellite information; they do not measure the selected farm. |
| [FAO, Irrigation Water Needs, §4.4](https://www.fao.org/4/S2022E/s2022e08.htm) | Paddy water management includes crop evapotranspiration, land saturation, seepage/percolation and a water layer. Seasonal rain alone is insufficient for an irrigation requirement. |
| [NC State Extension, Sesame Production Fact Sheet](https://content.ces.ncsu.edu/sesame-production-fact-sheet) | Sesame is relatively drought tolerant, needs establishment moisture and is sensitive to saturated conditions. Its 5.5–7 pH guidance explicitly notes limited optimal-pH research. North Carolina recommendations are not automatically calibrated for An Giang. |
| [Jagadish et al. 2007, Journal of Experimental Botany, DOI 10.1093/jxb/erm003](https://pubmed.ncbi.nlm.nih.gov/17431025/) | Controlled rice experiments studied anthesis exposure, including tissue temperatures of 33.7 and 36.2°C. They support stage-specific heat caution, not a damage percentage from seasonal grid-cell Tmax counts. |
| [IRRI, Rice feels the heat](https://ricetoday.irri.org/rice-feels-the-heat/) | Rice heat effects depend on stage, duration and water conditions. Checking stage overlap is justified; a season-wide injury diagnosis is not. |
| [FAO, Water Quality for Agriculture, §2.4.3](https://www.fao.org/4/t0234e/t0234e03.htm) | Salinity interpretation requires defined soil-extract ECe and/or irrigation-water ECw measures and context. No new EC threshold or yield penalty is implemented from a yes/no answer. |
| [ETCCDI indices definitions](https://etccdi.pacificclimate.org/list_27_indices.shtml) | Rain below 1 mm is a climatological dry-day convention. The pipeline counts seasonal occurrences; it does not compute ETCCDI's maximum consecutive dry spell. |

Remaining limitations: one location and two analogs per season; pilot crop calendars; no effective-rainfall, evapotranspiration, soil-water-storage or flood model; no flowering dates, canopy temperature, heat-duration or night-temperature exposure; no local variety calibration, measured EC inputs, observed crop outcomes or market economics. Rainfall and dry-day terms may partially double-count moisture conditions. Thermal indicators are explanatory only. Generic water-demand assumptions do not model rice management systems such as alternate wetting and drying. Diversity and continuity remain fixed preference proxies. pH warnings and reported good drainage are not certifications of suitability.

## API, language and frontend compatibility

`evaluate_rotation()` and `compare_scenarios()`, their public arguments and input identifiers remain available. Existing result keys and the three component/weight keys are preserved. Diagnostics and provenance are additive. `compare_scenarios()` reads one local snapshot for both evaluations.

`web.py`, route URLs, form identifiers and export headers are unchanged. JSON exports retain the existing canonical, language-independent source-message contract: legacy source strings remain alongside new English source messages. UI translation is handled by `presentation_messages.py`, including new parameterized explanations and validation errors. JSON reports are not newly localized based on `lang`; VI/EN exports remain identical.

The six-view layout is preserved. Only methodology/help text, source labels and component decimal formatting changed. No third crop, slider or frontend redesign was added.

## Commands and actual results

Commands below were run locally; no dependency installation was performed.

Baseline:
```powershell
.\RiceShift\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s RiceShift -p 'test_*.py'
```
Result before changes: **20 unittest cases passed** in 7.157 s; the old scoring module also executed its top-level assertions. Without `-X utf8`, its Vietnamese success print failed under the host cp1258 console. The global Python environment also lacked Flask, so it was not used for web tests.

Final complete suite:
```powershell
.\RiceShift\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s RiceShift -p 'test_*.py'
```
Result: **53 tests passed** in 9.021 s.

The existing virtual environment has Python 3.12.10, Flask 3.1.3, pandas 3.1.1, NumPy 2.5.4 and requests 2.34.2. Its pandas version exceeds the root requirements' <3 bound. To check the unchanged data code using an installed version inside that bound, these were also run with global Python/pandas 2.3.3:
```powershell
python -B -X utf8 -m unittest discover -s RiceShift -p 'test_climate*.py'
python -B -X utf8 -m unittest discover -s RiceShift -p 'test_historical_dataset.py'
```
Results: **6 + 6 tests passed**, in 6.328 s and 0.532 s. Global requests emitted an existing dependency-version warning; these offline tests passed.

After formatting translation entries, the web/scoring suite was rerun from `D:\agrishift-360\RiceShift`:
```powershell
.\.venv\Scripts\python.exe -B -X utf8 -m unittest test_scoring_engine test_frontend
```
Result: **41 tests passed** in 2.144 s. These include the comparison tests, full scoring/farm matrix, six views in both languages, translated errors, missing thermal/dry indicators, health, POST, downloads and language-independent JSON.

Comparison generation from the repository root:
```powershell
.\RiceShift\.venv\Scripts\python.exe -B -X utf8 RiceShift/scripts/compare_decision_engines.py --output docs/decision-engine-v2-comparison.csv --summary
```
Result: **144 cases, 288 rows, 108 comparable scored rows, 108 score changes, 126 status changes, 39 leader changes**. Attribution reconstruction's largest difference from a displayed score delta was 0.0482582 points, within final rounding. The script and tests verify deterministic output and reject a changed payload.

All nine NASA-data file hashes were compared before/after: **0 changed files**. No pipeline update or live NASA download was performed.

## Files changed and deployment readiness

Modified:

- `RiceShift/services/scoring_engine.py`: continuous water component, separate exposure indicators, validation, verification gates, diagnostics and provenance.
- `RiceShift/test_scoring_engine.py`: replaces forced-winner script assertions with unittest coverage and comparison checks.
- `RiceShift/presentation_messages.py`: complete VI/EN explanation and error coverage.
- `RiceShift/frontend_i18n.py`: accurate methodology/help text and reference labels.
- `RiceShift/test_frontend.py`: Flask, bilingual, incomplete-data and JSON regressions.
- `RiceShift/templates/views/comparison.html`: display continuous components to three decimals.

Added:

- `RiceShift/scripts/compare_decision_engines.py`
- `RiceShift/tests/fixtures/decision_engine_v1_baseline.json`
- `docs/decision-engine-v2-comparison.csv`
- `docs/DECISION_ENGINE_V2.md` (this handoff)

The Flask source is ready for review and a controlled prototype deployment: local routes/templates/exports pass, no new runtime dependency is introduced, and the engine reads local data using the standard library. The configured Linux Gunicorn/Render process was not run on this Windows host; production deployment behavior has not been certified. The pre-existing virtual-environment dependency drift is documented above. Scientific deployment as a validated agronomic recommendation service is **not** supported.

This workspace has no `.git` directory, so Git status/diff could not be used. The file inventory, frozen baseline and data hashes provide the local review trail. README translation and unrelated frontend assets were left untouched. Stop here: Task 2 is complete; no commit, push or deployment was performed.
