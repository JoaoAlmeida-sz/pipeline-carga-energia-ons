select
    d.ano,
    d.mes,
    d.inicio_mes,
    s.subsistema_key,
    s.subsistema,
    count(*) as dias_observados,
    avg(f.carga_mwmed) as carga_media_mwmed,
    min(f.carga_mwmed) as carga_minima_mwmed,
    max(f.carga_mwmed) as carga_maxima_mwmed
from {{ ref('fct_carga_diaria') }} f
join {{ ref('dim_data') }} d on f.data_key = d.data_key
join {{ ref('dim_subsistema') }} s on f.subsistema_key = s.subsistema_key
group by d.ano, d.mes, d.inicio_mes, s.subsistema_key, s.subsistema

