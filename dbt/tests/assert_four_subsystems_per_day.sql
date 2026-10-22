select data_key
from {{ ref('fct_carga_diaria') }}
group by data_key
having count(distinct subsistema_key) <> 4

