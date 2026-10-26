"""Baixa, valida e carrega a carga diária por subsistema do ONS."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


BASE_URL = "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/carga_energia_di"
COLUNAS = {"id_subsistema", "nom_subsistema", "din_instante", "val_cargaenergiamwmed"}
SUBSISTEMAS = {"N", "NE", "S", "SE"}


def ano_corrente() -> int:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).year


@dataclass(frozen=True)
class Leitura:
    subsistema: str
    nome: str
    dia: date
    carga_mwmed: Decimal


def url_ano(ano: int) -> str:
    if ano < 2000 or ano > ano_corrente():
        raise ValueError(f"Ano fora da série disponível: {ano}")
    return f"{BASE_URL}/CARGA_ENERGIA_{ano}.csv"


def baixar_ano(ano: int) -> bytes:
    request = Request(url_ano(ano), headers={"User-Agent": "ons-carga-energia/0.1"})
    with urlopen(request, timeout=45) as response:
        conteudo = response.read(5_000_001)
    if len(conteudo) > 5_000_000:
        raise ValueError("Arquivo maior que o limite esperado de 5 MB")
    return conteudo


def validar_csv(conteudo: bytes, ano: int) -> list[Leitura]:
    try:
        texto = conteudo.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV não está em UTF-8") from exc
    leitor = csv.DictReader(io.StringIO(texto, newline=""), delimiter=";")
    if not leitor.fieldnames or set(leitor.fieldnames) != COLUNAS:
        raise ValueError(f"Colunas inesperadas: {leitor.fieldnames}")

    leituras: list[Leitura] = []
    chaves: set[tuple[date, str]] = set()
    codigos_por_dia: dict[date, set[str]] = defaultdict(set)
    for numero, linha in enumerate(leitor, start=2):
        try:
            codigo = linha["id_subsistema"].strip()
            nome = linha["nom_subsistema"].strip()
            dia = date.fromisoformat(linha["din_instante"].strip())
            carga = Decimal(linha["val_cargaenergiamwmed"].strip())
        except (AttributeError, ValueError, InvalidOperation, KeyError) as exc:
            raise ValueError(f"Linha {numero}: formato inválido") from exc
        if codigo not in SUBSISTEMAS or not nome or dia.year != ano:
            raise ValueError(f"Linha {numero}: subsistema, nome ou ano inválido")
        if not carga.is_finite() or carga <= 0:
            raise ValueError(f"Linha {numero}: carga deve ser positiva e finita")
        chave = (dia, codigo)
        if chave in chaves:
            raise ValueError(f"Linha {numero}: chave diária duplicada: {chave}")
        chaves.add(chave)
        codigos_por_dia[dia].add(codigo)
        leituras.append(Leitura(codigo, nome, dia, carga))

    if not leituras:
        raise ValueError("CSV vazio")
    primeiro, ultimo = min(codigos_por_dia), max(codigos_por_dia)
    if primeiro != date(ano, 1, 1):
        raise ValueError(f"Série começa em {primeiro}, não em 1º de janeiro")
    dia = primeiro
    while dia <= ultimo:
        if codigos_por_dia.get(dia) != SUBSISTEMAS:
            raise ValueError(f"Dia ausente ou incompleto: {dia}")
        dia += timedelta(days=1)
    if ano < ano_corrente() and ultimo != date(ano, 12, 31):
        raise ValueError(f"Ano histórico incompleto: {ano} termina em {ultimo}")
    return leituras


def arquivar(conteudo: bytes, ano: int, pasta: Path) -> tuple[Path, str]:
    digest = hashlib.sha256(conteudo).hexdigest()
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"CARGA_ENERGIA_{ano}_{digest[:12]}.csv"
    if not destino.exists():
        destino.write_bytes(conteudo)
    return destino, digest


def conectar_snowflake():
    import snowflake.connector

    obrigatorias = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_ROLE", "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE")
    ausentes = [nome for nome in obrigatorias if not os.getenv(nome)]
    if ausentes:
        raise ValueError(f"Variáveis Snowflake ausentes: {', '.join(ausentes)}")
    parametros = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "role": os.environ["SNOWFLAKE_ROLE"],
        "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
        "database": os.environ["SNOWFLAKE_DATABASE"],
        "schema": "RAW",
    }
    metodo = os.getenv("SNOWFLAKE_AUTH_METHOD", "externalbrowser")
    if metodo == "externalbrowser":
        parametros["authenticator"] = "externalbrowser"
    elif metodo == "pat":
        token = os.getenv("SNOWFLAKE_PAT")
        if not token:
            raise ValueError("SNOWFLAKE_PAT é obrigatório no modo pat")
        parametros["password"] = token
    else:
        raise ValueError(f"Método de autenticação inválido: {metodo}")
    return snowflake.connector.connect(**parametros)


def carregar_no_snowflake(leituras: list[Leitura], ano: int, digest: str) -> None:
    with conectar_snowflake() as conexao:
        cursor = conexao.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS RAW.CARGA_ENERGIA_DIARIA (
                    ID_SUBSISTEMA VARCHAR(3) NOT NULL,
                    NOM_SUBSISTEMA VARCHAR(60) NOT NULL,
                    DIN_INSTANTE DATE NOT NULL,
                    VAL_CARGAENERGIAMWMED NUMBER(38, 13) NOT NULL,
                    SOURCE_YEAR INTEGER NOT NULL,
                    SOURCE_SHA256 VARCHAR(64) NOT NULL,
                    LOADED_AT TIMESTAMP_TZ NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TEMPORARY TABLE CARGA_LOTE (
                    ID_SUBSISTEMA VARCHAR(3), NOM_SUBSISTEMA VARCHAR(60),
                    DIN_INSTANTE DATE, VAL_CARGAENERGIAMWMED NUMBER(38, 13)
                )
            """)
            dados = [(r.subsistema, r.nome, r.dia.isoformat(), str(r.carga_mwmed)) for r in leituras]
            cursor.executemany("INSERT INTO CARGA_LOTE VALUES (%s, %s, %s, %s)", dados)
            cursor.execute("""
                MERGE INTO RAW.CARGA_ENERGIA_DIARIA AS alvo
                USING CARGA_LOTE AS origem
                ON alvo.DIN_INSTANTE = origem.DIN_INSTANTE
                   AND alvo.ID_SUBSISTEMA = origem.ID_SUBSISTEMA
                WHEN MATCHED AND (
                    alvo.NOM_SUBSISTEMA <> origem.NOM_SUBSISTEMA OR
                    alvo.VAL_CARGAENERGIAMWMED <> origem.VAL_CARGAENERGIAMWMED
                ) THEN UPDATE SET
                    NOM_SUBSISTEMA = origem.NOM_SUBSISTEMA,
                    VAL_CARGAENERGIAMWMED = origem.VAL_CARGAENERGIAMWMED,
                    SOURCE_SHA256 = %s,
                    LOADED_AT = CURRENT_TIMESTAMP()
                WHEN NOT MATCHED THEN INSERT (
                    ID_SUBSISTEMA, NOM_SUBSISTEMA, DIN_INSTANTE,
                    VAL_CARGAENERGIAMWMED, SOURCE_YEAR, SOURCE_SHA256, LOADED_AT
                ) VALUES (
                    origem.ID_SUBSISTEMA, origem.NOM_SUBSISTEMA, origem.DIN_INSTANTE,
                    origem.VAL_CARGAENERGIAMWMED, %s, %s, CURRENT_TIMESTAMP()
                )
            """, (digest, ano, digest))
            conexao.commit()
        finally:
            cursor.close()


def processar_ano(ano: int, pasta: Path, arquivo: Path | None = None, dry_run: bool = False) -> int:
    conteudo = arquivo.read_bytes() if arquivo else baixar_ano(ano)
    leituras = validar_csv(conteudo, ano)
    caminho, digest = arquivar(conteudo, ano, pasta)
    print(f"{ano}: {len(leituras)} linhas válidas; {min(r.dia for r in leituras)} a {max(r.dia for r in leituras)}; snapshot {caminho.name}")
    if not dry_run:
        carregar_no_snowflake(leituras, ano, digest)
    return len(leituras)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, nargs="+", help="Anos a carregar (padrão: START_YEAR até o ano atual)")
    parser.add_argument("--file", type=Path, help="CSV local; requer exatamente um ano")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--dry-run", action="store_true", help="Valida e arquiva sem conectar ao Snowflake")
    args = parser.parse_args()
    anos = args.years or list(range(int(os.getenv("START_YEAR", "2024")), ano_corrente() + 1))
    if args.file and len(anos) != 1:
        parser.error("--file requer exatamente um ano em --years")
    for ano in anos:
        processar_ano(ano, args.data_dir, args.file, args.dry_run)


if __name__ == "__main__":
    main()

