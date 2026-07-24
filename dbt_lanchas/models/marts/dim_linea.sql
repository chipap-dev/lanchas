with distintos as (

    select distinct
        stg.empresa_slug,
        stg.linea_numero
    from {{ ref('stg_lanchas_horarios') }} as stg

),

con_empresa as (

    select
        d.linea_numero,
        e.empresa_id
    from distintos as d
    inner join {{ ref('dim_empresa') }} as e
        on d.empresa_slug = e.empresa_slug

)

select
    row_number() over (order by empresa_id, linea_numero) as linea_id,
    empresa_id,
    linea_numero
from con_empresa
