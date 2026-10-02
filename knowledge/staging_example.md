# Example staging model
Source: raw.users(id, created, email_addr)
select
    cast(id as bigint)              as user_id,
    cast(created as timestamp)      as created_at,
    email_addr                      as email
from raw.users