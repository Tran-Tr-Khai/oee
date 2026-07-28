# oee-processing

dbt project for cleaning raw OEE data into silver tables.

Run from this folder:

```powershell
uv run dbt run --profiles-dir .
uv run dbt test --profiles-dir .
```

Silver tables created:

- `slv_machine_status`
- `slv_complete_beam`
- `slv_textile_days`
- `slv_start_beam`

Gold tables created:

- `gld_date_dim`
- `gld_beam_plan_dim`
- `gld_machine_dim`
- `gld_machine_status_daily_fact`
- `gld_production_daily_fact`
