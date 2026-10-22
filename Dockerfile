FROM apache/airflow:3.3.2-python3.12

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir "apache-airflow==3.3.2" -r /tmp/requirements.txt

COPY --chown=airflow:root src /opt/airflow/src
COPY --chown=airflow:root dags /opt/airflow/dags
COPY --chown=airflow:root dbt /opt/airflow/dbt
ENV PYTHONPATH=/opt/airflow/src

