# Command coordination and responder operations

**Development owner: Sanjay S M.** This is assigned responsibility; completed contributions should be described only after verification.

This feature helps commanders review incidents at arrival time, assign suitable teams and collect responder feedback. It owns the ranked command API, assignment optimizer, deterministic field summaries, seven-team/eleven-site demo and site evidence history.

## Code

| File | Responsibility |
| --- | --- |
| `routes.py` | Command/office/responder shared shell, ranked sites, site history and photos, teams, dispatch, field updates and seed endpoint |
| `service.py` | Read incident observations, recompute through intelligence, apply compound proximity flags, add guidance/navigation and sort priority |
| `dispatch.py` | Check projected arrival feasibility and maximize decreasing benefit using rectangular SciPy assignment |
| `dispatch_reference.py` | Spec Appendix B scenario for ETA ×1 and ×2 regression tests |
| `guidance.py` | Deterministic situation/deadline/hazard/action/uncertainty summaries |
| `seed.py` | Eleven explicitly simulated flood/collapse/damaged-building incidents and seven rescue teams |
| `models.py` | Dispatch parameters, team registration and field updates |

Shared frontend files in [`../static/`](../static/) include `index.html`, `app.js`, `location.js`, `upload.js`, `waterline-mark.svg` and `style.css`. One authenticated shell supports office, command and responder navigation; shared visual and upload utilities are deliberately not copied between feature folders.

## Workflow and interface

1. Open `/command` as an authenticated admin. Choose an alert and inspect the ranked site queue/map.
2. Change nominal ETA scale to recompute severity, deadlines and priority. Open a site card for depth paths, uncertainty, collapse zones, hazards, evidence and navigation links.
3. Use `/api/dispatch/run` to allocate one available team per site. The objective values earlier-arrival benefit rather than higher severity caused by delay. Projected site depth and flow constrain vehicles, foot teams and boats; route conditions remain unknown.
4. Open `/responders` or `/field/{team_id}`. Review the current assignment, upload assignment-bound observations/photos through the shared intake, change status and record measured depth or confirmed rescued count.
5. Command evidence history combines photo reports and field observations. Recorded measurements can support benchmark calculations; a missing hazard flag never clears entry.

Primary APIs are `/api/incidents`, `/api/incidents/{incident_id}`, `/api/incidents/{incident_id}/reports`, `/api/reports/{report_id}/photos/{index}`, `/api/teams`, `/api/dispatch/run`, `/api/incidents/{incident_id}/field_update` and `/api/seed`.

## Demo and safeguards

Seed replaces the demo alert and its related data, leaving unrelated alert data intact. The scenario includes rising/deep/receding water, conflicting references, rooftop refuge, electrical hazards, lean-to/pancake collapse, a damaged standing structure with a HOLD flag, and nearby flood/rubble compound risk. All seeded measurements and occupancy are synthetic assumptions.

Field updates and photos require a matching assignment. Navigation uses Google/Apple/geo links, not validated rescue routing. All cards say that estimates carry uncertainty and the incident commander decides.

## Verification and limits

Run `python -m pytest tests/test_dispatch.py tests/test_field_reports.py tests/test_api.py -q`. Golden ETA tests preserve the scenario where delaying arrival makes a 4×4 assignment infeasible. Current gaps include multi-capability slots, medical staging, active-assignment conflict management, separate responder accounts, real route closures/equipment inventory and a professionally reviewed full rescue playbook.
