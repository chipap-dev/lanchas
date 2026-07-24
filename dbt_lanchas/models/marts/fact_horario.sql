with stg as (

    select * from {{ ref('stg_lanchas_horarios') }}

),

dim_empresa as (

    select * from {{ ref('dim_empresa') }}

),

dim_linea as (

    select * from {{ ref('dim_linea') }}

),

dim_via as (

    select * from {{ ref('dim_via') }}

),

dim_tipo_dia as (

    select * from {{ ref('dim_tipo_dia') }}

)

select
    dl.linea_id,
    dv.via_id,
    dtd.tipo_dia_id,
    stg.servicio_nombre,
    stg.servicio_tipo,
    stg.hora,
    stg.direccion,
    stg.fecha_carga
from stg
inner join dim_empresa as de
    on stg.empresa_slug = de.empresa_slug
inner join dim_linea as dl
    on de.empresa_id = dl.empresa_id
    and stg.linea_numero = dl.linea_numero
inner join dim_via as dv
    on stg.via_nombre = dv.via_nombre
inner join dim_tipo_dia as dtd
    on stg.tipo_dia = dtd.tipo_dia
