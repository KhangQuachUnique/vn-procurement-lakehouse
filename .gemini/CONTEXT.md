# Project Context: Vietnam Procurement Lakehouse

## 1. Product Overview & Core Mission
- **System**: Data Lakehouse for Vietnam Public Procurement data (Hệ thống Mạng Đấu thầu Quốc gia / Muasamcong).
- **Core Mission**: Thu thập, kiểm định toàn vẹn, lưu trữ và chuyển đổi dữ liệu đấu thầu công thành kho dữ liệu phân tích minh bạch, phục vụ truy vết, báo cáo và phòng chống gian lận thầu.
- **Design Philosophy**: **First-Principles Engineering First, Modern Tools Second**. Tự tay lập trình và làm chủ các cơ chế cốt lõi (hợp đồng dữ liệu, atomic write, checksum manifest, state tracking, failure recovery) trước khi tích hợp các công cụ chuyên dụng.

## 2. Tech Stack & Key Libraries
- **Language & Runtime**: Python `>=3.12`, package & environment quản lý bởi `uv`.
- **Typing & Validation**: `pydantic` v2, `pydantic-settings`, immutable `dataclasses(slots=True, frozen=True)`.
- **Database & Control Plane**: PostgreSQL 17 (qua Docker Compose), SQLAlchemy 2.0 (declarative mapped columns), `psycopg[binary]>=3.3.6`.
- **Database Migrations**: `alembic` (quản lý schema `control`).
- **Storage Layer (Bronze)**: Local filesystem JSONL + SHA-256 Manifest JSON (thiết kế theo Port sẵn sàng chuyển sang S3/MinIO/GCS).
- **CLI Framework**: `typer` (CLI `procurement`).
- **Quality & Testing**: `pytest` (unit & integration), `pytest-cov`, `ruff` (linter & formatter), `pyright` (static type checking).

## 3. Architecture Rules & Design Patterns

### 3.1. Phân tầng kiến trúc (Hexagonal / Ports & Adapters)
- **Domain Layer (`modules/*/domain/`)**:
  - Không phụ thuộc bất kỳ framework/thư viện ngoài nào ngoại trừ standard library và Pydantic dataclasses.
  - Chứa Domain Entities, Value Objects, Business Invariants và State Machine.
  - Bắt buộc kiểm tra ràng buộc nghiệp vụ (invariants) ngay trong `__post_init__`.
- **Application Layer (`modules/*/application/`)**:
  - Chứa Use Cases (`IngestDailyWindow`, `IngestDateRange`, `VerifyBronze`, `RecoverIngestionRun`).
  - Định nghĩa abstraction thông qua `Protocol` trong `ports.py` (`SourcePort`, `BronzePort`, `RunRepositoryPort`).
  - Điều phối luồng dữ liệu, quản lý chuyển dịch trạng thái của Run, không chứa logic I/O trực tiếp.
- **Adapters Layer (`modules/*/adapters/`)**:
  - Triển khai cụ thể các `Port` đã định nghĩa:
    - Source: `FakeTenderSource` (mô phỏng nguồn dữ liệu `tbmt`).
    - Storage: `LocalBronzeWriter` (ghi dữ liệu Bronze và manifest).
    - Database: `PostgresRunRepository` (quản trị trạng thái qua PostgreSQL).
- **Composition Root / Bootstrap (`boostrap/`)**:
  - Quản lý Dependency Injection bằng Generator Context Managers (`*_scope()`).
  - Đảm bảo vòng đời tài nguyên (tạo DB Engine, SessionFactory và tự động `dispose()` khi hoàn thành).
- **Entrypoints (`entrypoints/cli.py`)**:
  - Giao tiếp bên ngoài qua Typer CLI, gọi use case qua context manager scope.

### 3.2. Medallion Storage Pattern (Bronze Layer)
- **Partitioning**: Phân vùng vật lý theo tài nguyên và ngày:
  `<base_path>/<resource>/date=YYYY-MM-DD/runs/<run_id>/`
- **Atomic Write Mechanism**:
  1. Ghi records ra file tạm `part-000.jsonl.tmp`.
  2. Tính toán hàm băm SHA-256 trực tiếp trong quá trình stream dữ liệu.
  3. `file.flush()` và `os.fsync()` đảm bảo dữ liệu ghi hẳn xuống đĩa vật lý.
  4. Đổi tên nguyên tử (`os.replace`) sang `part-000.jsonl`.
  5. Tạo `BronzeManifest` (schema version, run_id, record_count, sha256, created_at UTC) ra file `manifest.json.tmp`.
  6. `os.replace` sang `manifest.json` CUỐI CÙNG làm "dấu mốc hoàn thành" (completion marker).

### 3.3. State Management & Auditability
- **Control Table**: PostgreSQL `control.ingestion_runs`.
- **State Machine**:
  - `PENDING` -> `IN_PROGRESS` -> `COMPLETED` (kèm `record_count >= 0`) hoặc `FAILED`.
  - Database Constraints: Check constraints bảo đảm tính hợp lệ của status, resource regex, daily window (`end_date = start_date + 1`), và record count logic.
- **Idempotency & Failure Recovery**:
  - Mỗi lần chạy sinh ra một `run_id` (UUIDv4) độc lập, không ghi đè dữ liệu cũ.
  - Công cụ `bronze-recover` cho phép rà soát ngoài băng (out-of-band reconciliation): đọc on-disk manifest, xác thực hash SHA-256 đối với file dữ liệu, và cập nhật trạng thái các run bị crash/treo từ `IN_PROGRESS` sang `COMPLETED` hoặc `FAILED`.
