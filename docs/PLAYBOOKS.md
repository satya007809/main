# Investigation playbooks

Playbooks hold the investigation logic. They are YAML documents stored in the database with full version
history and edited from the app (Settings → Administration → Investigation playbooks). No code change or
redeployment is needed to improve them. Defaults ship in `backend/app/playbooks/defaults/` and are seeded on
first start.

## How they are applied

```
global_rules (always)  +  category playbook (from case type)  +  aspect playbooks (selected or detected)
```

* **global_rules** – your standing reporting instructions: evidence standards, classification of findings,
  the ban on fabricated or unverified external checks, policy-clause analysis, opinion wording, style.
* **Category playbooks** – `own_damage`, `pa_injury`, `pa_death`, `theft`, `fire`, `road_accident`, `general`.
* **Aspect playbooks** – `hire_and_reward`, `close_proximity`, `vehicle_modification`, `policy_breach`, and
  `road_accident` as an aspect. Select them on the case, or the engine reports them under *detected aspects*
  so you can add them and rerun.

Each analysis run stores the exact `{key, version}` list it used (visible in Findings → Run details and in
the audit trail).

## Structure

```yaml
key: theft                      # do not change
name: Vehicle Theft
kind: category                  # global | category | aspect
report_template: theft          # which report layout to use
related_aspects: [policy_breach, hire_and_reward]
objective: >
  One paragraph: what the investigation must establish.
document_checklist:             # drives the "missing documents" list and the checklist in findings
  - {id: fir, label: FIR, doc_types: [fir], required: true}
investigation_questions:        # each is answered with sources in Findings → Evidence
  - When was the vehicle last seen and by whom?
evidence_verification: [...]    # cross-checks to perform
chronology_checks: [...]        # time gaps / sequences to examine
policy_verification: [...]      # clauses and conditions to examine in the supplied wording
red_flags_to_examine: [...]     # indicators to test – never conclusions
report_instructions: [...]      # how findings should be written in the report
```

Validation on save: valid YAML, `key` unchanged, `kind` valid, `objective` present, list fields are lists,
checklist items have `id` and `label`. Invalid edits are rejected with the reason; the active version is
untouched.

## Tips

* Write questions as things to *establish*, not presumed answers ("Was the driver's licence valid on the
  accident date?" rather than "Driver had no licence").
* Put insurer-specific requirements in `report_instructions` of the category playbook, or create an
  `instruction` note on an individual case for one-off directions.
* To roll back, open the playbook, find the earlier version in History and tap **Activate**.
* Report section headings are in `backend/app/reports/templates/*.yaml`; adjust them to match your reference
  report headings.
