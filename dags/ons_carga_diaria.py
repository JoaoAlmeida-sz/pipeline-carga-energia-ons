"""Atualiza dados do ONS e reconstrói o esquema estrela no Snowflake."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from airflow.sdk import dag, task


@dag(
    dag_id="ons_carga_diaria",
    schedule="0 22 * * *",
    start_date=datetime(2024, 1, 1, tzinfo=ZoneInfo("America/Sao_Paulo")),
    catchup=False,
    max_active_runs=1,
    tags=["ons", "energia", "snowflake", "dbt"],
)
def ons_carga_diaria():
    @task(retries=2)
    def ingerir() -> None:
        from ons_carga.ingest import ano_corrente, processar_ano

        inicio = int(os.getenv("START_YEAR", "2024"))
        pasta = Path(os.getenv("DATA_DIR", "/opt/airflow/data/raw"))
        for ano in range(inicio, ano_corrente() + 1):
            processar_ano(ano, pasta)

    @task(retries=1)
    def modelar_e_testar() -> None:
        resultado = subprocess.run(
            ["dbt", "build", "--project-dir", "/opt/airflow/dbt", "--profiles-dir", "/opt/airflow/dbt"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        token = os.getenv("SNOWFLAKE_PAT", "")
        saida = resultado.stdout.replace(token, "[REDACTED]") if token else resultado.stdout
        print(saida, flush=True)
        resultado.check_returncode()

    ingerir() >> modelar_e_testar()


ons_carga_diaria()

