select
    to_number(to_char(data_referencia, 'YYYYMMDD')) as data_key,
    data_referencia as data,
    year(data_referencia) as ano,
    month(data_referencia) as mes,
    date_trunc('month', data_referencia)::date as inicio_mes,
    dayofweekiso(data_referencia) as dia_semana_iso
from {{ ref('stg_carga_diaria') }}
group by data_referencia

