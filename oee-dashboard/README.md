# oee-dashboard

Power BI dashboard blueprint for the OEE model built from DuckDB `gold` tables.

Contents:

- `measures/core_measures.dax`: core DAX reference; reporting measures are stored in TMDL
- `theme/oee_bright_theme.json`: importable bright Power BI theme
- `tools/build_overview_pbir.mjs`: reproducible Overview page generator
- `export_gold_to_parquet.py`: exports `gold` tables to Parquet for Power BI
- `oee_dashboard.Report`: version-controlled PBIR report definition
- `oee_dashboard.SemanticModel`: version-controlled TMDL semantic model

Recommended build order in Power BI:

1. Export the `gold` tables to Parquet.
2. Open `oee_dashboard.pbip`.
3. Refresh the semantic model.

Export command:

```powershell
uv run python oee-dashboard/export_gold_to_parquet.py
```

Parquet output folder:

```text
data/exports/powerbi
```

Rebuild the PBIR Overview page:

```powershell
node oee-dashboard/tools/build_overview_pbir.mjs
```

Open the report:

```powershell
oee-dashboard/oee_dashboard.pbip
```

Files exported:

- `gld_date_dim.parquet`
- `gld_machine_dim.parquet`
- `gld_beam_plan_dim.parquet`
- `gld_production_daily_fact.parquet`
- `gld_machine_status_daily_fact.parquet`

Current tables expected in the model:

- `gld_date_dim`
- `gld_machine_dim`
- `gld_beam_plan_dim`
- `gld_production_daily_fact`
- `gld_machine_status_daily_fact`

Suggested Power BI model shape:

- `gld_date_dim` is the shared date dimension
- `gld_machine_dim` contains the 252 status-monitored machines
- `gld_production_daily_fact` is the main production fact
- `gld_machine_status_daily_fact` is the status-hours fact
- `gld_beam_plan_dim` enriches production through `beam_plan_key`
