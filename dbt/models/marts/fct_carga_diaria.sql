select
    d.data_key,
    s.subsistema_key,
    c.carga_mwmed,
    c.atualizado_em
from {{ ref('stg_carga_diaria') }} c
join {{ ref('dim_data') }} d on c.data_referencia = d.data
join {{ ref('dim_subsistema') }} s on c.id_subsistema = s.subsistema_key

