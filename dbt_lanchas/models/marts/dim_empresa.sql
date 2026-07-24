with distintos as (

    select distinct
        empresa_slug,
        empresa_nombre
    from {{ ref('stg_lanchas_horarios') }}

)

select
    row_number() over (order by empresa_slug) as empresa_id,
    empresa_slug,
    empresa_nombre
from distintos
