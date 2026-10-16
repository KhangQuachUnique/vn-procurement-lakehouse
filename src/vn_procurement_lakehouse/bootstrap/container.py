from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from vn_procurement_lakehouse.bootstrap.config import load_settings
from vn_procurement_lakehouse.modules.ingestion.adapters.composite_source import (
    CompositeSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.local_bronze_writer import (
    LocalBronzeWriter,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.bid_opening_api import (
    BidOpeningApi,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.bid_opening_source import (
    BidOpeningSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.client import (
    MuasamcongClient,
    RetryPolicy,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.khlcnt_api import (
    KhlcntApi,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.khlcnt_source import (
    KhlcntSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.kqlcnt_api import (
    KqlcntApi,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.kqlcnt_source import (
    KqlcntSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.project_api import (
    ProjectApi,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.project_source import (
    ProjectSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.tbmt_api import (
    TbmtApi,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.tbmt_source import (
    TbmtSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.postgres.run_repository import (
    PostgresRunRepository,
)
from vn_procurement_lakehouse.modules.ingestion.application.ingest_daily_range import (
    IngestDateRange,
)
from vn_procurement_lakehouse.modules.ingestion.application.ingest_daily_window import (
    IngestDailyWindow,
)
from vn_procurement_lakehouse.modules.ingestion.application.recover_ingestion_run import (
    RecoverIngestionRun,
)
from vn_procurement_lakehouse.modules.ingestion.application.verify_bronze import VerifyBronze


@dataclass(frozen=True)
class IngestionService:
    ingestion_daily: IngestDailyWindow
    ingestion_range: IngestDateRange


@dataclass(frozen=True)
class VerifyBronzeService:
    verify_bronze: VerifyBronze


@dataclass(frozen=True)
class RecoverIngestionRunService:
    recover_ingestion_run: RecoverIngestionRun


@contextmanager
def ingestion_scope() -> Generator[IngestionService]:
    settings = load_settings()

    engine = create_engine(settings.database_url, pool_pre_ping=True)

    base_url = settings.muasamcong_base_url or "https://muasamcong.mpi.gov.vn/"
    token = (
        settings.muasamcong_token.get_secret_value() if settings.muasamcong_token else "fakeToken"
    )

    client = MuasamcongClient(
        base_url=base_url,
        token=token,
        timeout=httpx.Timeout(
            connect=settings.muasamcong_connect_timeout,
            read=settings.muasamcong_read_timeout,
            write=settings.muasamcong_write_timeout,
            pool=settings.muasamcong_pool_timeout,
        ),
        retry_policy=RetryPolicy(
            max_attempts=settings.muasamcong_retry_attempts,
            base_delay_seconds=settings.muasamcong_retry_base_delay,
            max_delay_seconds=settings.muasamcong_retry_max_delay,
        ),
        max_connections=settings.muasamcong_max_connections,
        max_keepalive_connections=settings.muasamcong_max_keepalive_connections,
    )

    try:
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        run_repository = PostgresRunRepository(session_factory=session_factory)

        project_api = ProjectApi(client=client)
        project_source = ProjectSource(api=project_api, page_size=settings.muasamcong_page_size)

        khlcnt_api = KhlcntApi(client=client)
        khlcnt_source = KhlcntSource(api=khlcnt_api, page_size=settings.muasamcong_page_size)

        tbmt_api = TbmtApi(client=client)
        tbmt_source = TbmtSource(api=tbmt_api, page_size=settings.muasamcong_page_size)

        kqlcnt_api = KqlcntApi(client=client)
        kqlcnt_source = KqlcntSource(api=kqlcnt_api, page_size=settings.muasamcong_page_size)

        bid_opening_api = BidOpeningApi(client=client)
        bid_opening_source = BidOpeningSource(
            api=bid_opening_api, page_size=settings.muasamcong_page_size
        )

        source = CompositeSource(
            sources={
                "project": project_source,
                "khlcnt": khlcnt_source,
                "tbmt": tbmt_source,
                "kqlcnt": kqlcnt_source,
                "bid_opening": bid_opening_source,
            }
        )
        writer = LocalBronzeWriter(base_path=settings.bronze_base_path)

        ingestion_daily = IngestDailyWindow(
            source=source,
            writer=writer,
            run_repository=run_repository,
        )

        ingestion_range = IngestDateRange(ingest_daily=ingestion_daily)

        yield IngestionService(
            ingestion_daily=ingestion_daily,
            ingestion_range=ingestion_range,
        )
    finally:
        client.close()
        engine.dispose()


@contextmanager
def verify_bronze_scope() -> Generator[VerifyBronzeService]:
    settings = load_settings()

    engine = create_engine(settings.database_url, pool_pre_ping=True)

    try:
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        run_repository = PostgresRunRepository(session_factory=session_factory)

        writer = LocalBronzeWriter(base_path=settings.bronze_base_path)

        verify_bronze = VerifyBronze(
            repository=run_repository,
            bronze=writer,
        )

        yield VerifyBronzeService(
            verify_bronze=verify_bronze,
        )
    finally:
        engine.dispose()


@contextmanager
def recover_ingestion_scope() -> Generator[RecoverIngestionRunService]:
    settings = load_settings()

    engine = create_engine(settings.database_url, pool_pre_ping=True)

    try:
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        run_repository = PostgresRunRepository(session_factory=session_factory)

        writer = LocalBronzeWriter(base_path=settings.bronze_base_path)

        recover_ingestion_run = RecoverIngestionRun(
            run_repository=run_repository,
            bronze=writer,
        )

        yield RecoverIngestionRunService(
            recover_ingestion_run=recover_ingestion_run,
        )
    finally:
        engine.dispose()
