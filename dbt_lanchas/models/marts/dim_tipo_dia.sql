with distintos as (

    select distinct
        tipo_dia
    from {{ ref('stg_lanchas_horarios') }}

)

select
    row_number() over (order by tipo_dia) as tipo_dia_id,
    tipo_dia
from distintos
