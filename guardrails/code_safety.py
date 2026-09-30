import re
_FORBIDDEN = re.compile(
    r"\b(drop|delete|truncate|alter|attach|copy|install|pragma|update|insert)\b",
    re.I
)

def assert_sql_safe(sql: str) -> None:
    body = sql.strip().lower()
    if ";" in body:
        raise ValueError("Guardrail: multiple statements not allowed")
    if _FORBIDDEN.search(body):
        raise ValueError("Guardrail: forbidden SQL keyword.")
    if not re.match(r"^\s*(with|select)\b", body, re.I):
        raise ValueError("Guardrail: only SELECT/CTE allowed.")