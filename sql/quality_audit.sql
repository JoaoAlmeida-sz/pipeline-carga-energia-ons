-- Execute no Snowsight após a carga e o dbt build.
-- As contagens descrevem o estado atual; os indicadores de erro devem ser zero.
WITH raw AS (
    SELECT
        COUNT(*) AS linhas,
        COUNT(DISTINCT DIN_INSTANTE) AS dias,
        MIN(DIN_INSTANTE) AS primeiro_dia,
        MAX(DIN_INSTANTE) AS ultimo_dia,
        COUNT(*) - COUNT(DISTINCT TO_VARCHAR(DIN_INSTANTE) || '|' || ID_SUBSISTEMA) AS chaves_duplicadas,
        COUNT_IF(VAL_CARGAENERGIAMWMED <= 0) AS cargas_invalidas
    FROM ONS_ENERGIA.RAW.CARGA_ENERGIA_DIARIA
),
dias_incompletos AS (
    SELECT COUNT(*) AS total
    FROM (
        SELECT DIN_INSTANTE
        FROM ONS_ENERGIA.RAW.CARGA_ENERGIA_DIARIA
        GROUP BY DIN_INSTANTE
        HAVING COUNT(DISTINCT ID_SUBSISTEMA) <> 4
    )
),
modelos AS (
    SELECT
        (SELECT COUNT(*) FROM ONS_ENERGIA.ANALYTICS.DIM_DATA) AS dim_data,
        (SELECT COUNT(*) FROM ONS_ENERGIA.ANALYTICS.DIM_SUBSISTEMA) AS dim_subsistema,
        (SELECT COUNT(*) FROM ONS_ENERGIA.ANALYTICS.FCT_CARGA_DIARIA) AS fato,
        (SELECT COUNT(*) FROM ONS_ENERGIA.ANALYTICS.MART_CARGA_MENSAL) AS mart_mensal
)
SELECT
    raw.linhas AS linhas_raw,
    raw.dias AS dias_raw,
    raw.primeiro_dia,
    raw.ultimo_dia,
    modelos.dim_data,
    modelos.dim_subsistema,
    modelos.fato,
    modelos.mart_mensal,
    dias_incompletos.total AS dias_incompletos,
    DATEDIFF('day', raw.primeiro_dia, raw.ultimo_dia) + 1 - raw.dias AS dias_ausentes,
    raw.chaves_duplicadas,
    COALESCE(raw.cargas_invalidas, 0) AS cargas_invalidas,
    raw.linhas - modelos.fato AS diferenca_raw_fato
FROM raw
CROSS JOIN dias_incompletos
CROSS JOIN modelos;
