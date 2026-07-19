# Dataset manifest templates

Copy, rename and replace every `REPLACE_WITH_*` value before use. Do not edit a
template into a misleading partially approved manifest.

- `retrieval.template.yaml`: train/retrieval material; indexing may be enabled.
- `pilot_validation.template.yaml`: tuning and retrieval-pipeline validation;
  indexing is forbidden.
- `final_benchmark.template.yaml`: final reporting only; indexing and tuning are
  forbidden.

`source_split` describes where the source came from. `usage_role` describes how
the experiment may use it. They are intentionally independent fields.
