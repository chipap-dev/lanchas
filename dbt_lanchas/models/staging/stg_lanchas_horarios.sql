with fuente as (

    select *
    from {{ source('lanchas_raw', 'horarios') }}

)

select
    trim(empresa_nombre) as empresa_nombre,
    trim(empresa_slug) as empresa_slug,
    trim(linea_numero) as linea_numero,
    trim(servicio_nombre) as servicio_nombre,
    trim(servicio_tipo) as servicio_tipo,
    trim(via_nombre) as via_nombre,
    trim(tipo_dia) as tipo_dia,
    hora,
    trim(direccion) as direccion,
    fecha_carga
from fuente
