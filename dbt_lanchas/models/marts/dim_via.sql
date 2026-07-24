with distintos as (

    select distinct
        via_nombre
    from {{ ref('stg_lanchas_horarios') }}

)

select
    row_number() over (order by via_nombre) as via_id,
    via_nombre
from distintos
