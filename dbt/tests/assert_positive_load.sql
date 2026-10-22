select *
from {{ ref('fct_carga_diaria') }}
where carga_mwmed <= 0

