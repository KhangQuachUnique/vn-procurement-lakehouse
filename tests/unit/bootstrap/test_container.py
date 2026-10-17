from unittest.mock import MagicMock, patch

from vn_procurement_lakehouse.bootstrap.container import (
    CoverageService,
    IngestionService,
    RecoverIngestionRunService,
    VerifyBronzeService,
    coverage_scope,
    ingestion_scope,
    recover_ingestion_scope,
    verify_bronze_scope,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.composite_source import (
    CompositeSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.local_bronze_writer import (
    LocalBronzeWriter,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.bid_opening_source import (
    BidOpeningSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.khlcnt_source import (
    KhlcntSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.kqlcnt_source import (
    KqlcntSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.project_source import (
    ProjectSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.muasamcong.tbmt_source import (
    TbmtSource,
)
from vn_procurement_lakehouse.modules.ingestion.adapters.postgres.run_repository import (
    PostgresRunRepository,
)


@patch("vn_procurement_lakehouse.bootstrap.container.MuasamcongClient")
@patch("vn_procurement_lakehouse.bootstrap.container.create_engine")
def test_ingestion_scope_wires_composite_sources_and_disposes(
    mock_create_engine: MagicMock,
    mock_client_cls: MagicMock,
) -> None:
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    with ingestion_scope() as service:
        assert isinstance(service, IngestionService)
        assert isinstance(service.ingestion_daily.source, CompositeSource)
        assert isinstance(service.ingestion_daily.source._sources["project"], ProjectSource)
        assert isinstance(service.ingestion_daily.source._sources["khlcnt"], KhlcntSource)
        assert isinstance(service.ingestion_daily.source._sources["tbmt"], TbmtSource)
        assert isinstance(service.ingestion_daily.source._sources["kqlcnt"], KqlcntSource)
        assert isinstance(service.ingestion_daily.source._sources["bid_opening"], BidOpeningSource)
        assert isinstance(service.ingestion_daily.writer, LocalBronzeWriter)
        assert isinstance(service.ingestion_daily.run_repository, PostgresRunRepository)
        assert service.ingestion_range.ingest_daily is service.ingestion_daily

    mock_client.close.assert_called_once()
    mock_engine.dispose.assert_called_once()


@patch("vn_procurement_lakehouse.bootstrap.container.create_engine")
def test_verify_bronze_scope_wires_and_disposes(mock_create_engine: MagicMock) -> None:
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    with verify_bronze_scope() as service:
        assert isinstance(service, VerifyBronzeService)
        assert isinstance(service.verify_bronze.bronze, LocalBronzeWriter)
        assert isinstance(service.verify_bronze.repository, PostgresRunRepository)

    mock_engine.dispose.assert_called_once()


@patch("vn_procurement_lakehouse.bootstrap.container.create_engine")
def test_recover_ingestion_scope_wires_and_disposes(mock_create_engine: MagicMock) -> None:
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    with recover_ingestion_scope() as service:
        assert isinstance(service, RecoverIngestionRunService)
        assert isinstance(service.recover_ingestion_run.bronze, LocalBronzeWriter)
        assert isinstance(service.recover_ingestion_run.run_repository, PostgresRunRepository)

    mock_engine.dispose.assert_called_once()


@patch("vn_procurement_lakehouse.bootstrap.container.create_engine")
def test_coverage_scope_wires_and_disposes(mock_create_engine: MagicMock) -> None:
    mock_engine = MagicMock()
    mock_create_engine.return_value = mock_engine

    with coverage_scope() as service:
        assert isinstance(service, CoverageService)
        assert isinstance(service.data_coverage.bronze, LocalBronzeWriter)
        assert isinstance(service.data_coverage.repository, PostgresRunRepository)

    mock_engine.dispose.assert_called_once()
