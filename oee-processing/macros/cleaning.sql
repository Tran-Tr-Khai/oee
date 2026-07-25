{% macro clean_text(column_name) -%}
    nullif(trim(cast({{ column_name }} as varchar)), '')
{%- endmacro %}

{% macro standardize_machine(column_name) -%}
    case
        when {{ clean_text(column_name) }} is null then null
        when regexp_matches(upper({{ clean_text(column_name) }}), '^WEV[0-9]+$') then
            'WEV' || lpad(regexp_extract(upper({{ clean_text(column_name) }}), '([0-9]+)', 1), 3, '0')
        when regexp_matches(upper({{ clean_text(column_name) }}), '^[0-9]+(\\.0)?$') then
            'WEV' || lpad(cast(cast(cast({{ clean_text(column_name) }} as double) as bigint) as varchar), 3, '0')
        when regexp_matches(upper({{ clean_text(column_name) }}), '^M-[0-9]+$') then
            upper({{ clean_text(column_name) }})
        else upper({{ clean_text(column_name) }})
    end
{%- endmacro %}

{% macro clean_code(column_name) -%}
    upper({{ clean_text(column_name) }})
{%- endmacro %}
