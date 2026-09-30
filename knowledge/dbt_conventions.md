# dbt staging conventions
- One staging model per raw source table, named stg_<source>.
- Rename every column to snake_case business names; never keep raw API names like "url".
- Cast ids to BIGINT and timestamps to TIMESTAMP explicitly.
- Never use SELECT *; list columns.
- Staging models are views; they only read from the raw schema.