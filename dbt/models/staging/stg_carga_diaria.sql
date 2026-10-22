select
    trim(id_subsistema) as id_subsistema,
    trim(nom_subsistema) as nom_subsistema,
    din_instante as data_referencia,
    val_cargaenergiamwmed as carga_mwmed,
    loaded_at as atualizado_em
from {{ source('ons', 'carga_energia_diaria') }}

