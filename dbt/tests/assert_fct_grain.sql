select data_key, subsistema_key
from {{ ref('fct_carga_diaria') }}
group by data_key, subsistema_key
having count(*) <> 1

