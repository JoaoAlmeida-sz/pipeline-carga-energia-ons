select
    id_subsistema as subsistema_key,
    nom_subsistema as subsistema
from {{ ref('stg_carga_diaria') }}
qualify row_number() over (
    partition by id_subsistema
    order by data_referencia desc, atualizado_em desc
) = 1

