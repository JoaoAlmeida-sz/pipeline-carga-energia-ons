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
        from datetime import date
        from ons_carga.ingest import processar_ano

        inicio = int(os.getenv("START_YEAR", "2024"))
        pasta = Path(os.getenv("DATA_DIR", "/opt/airflow/data/raw"))
        for ano in range(inicio, date.today().year + 1):
            processar_ano(ano, pasta)

    @task(retries=1)
    def modelar_e_testar() -> None:
        subprocess.run(
            ["dbt", "build", "--project-dir", "/opt/airflow/dbt", "--profiles-dir", "/opt/airflow/dbt"],
            check=True,
        )

    ingerir() >> modelar_e_testar()


ons_carga_diaria()

