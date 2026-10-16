# Project Roadmap: Vietnam Procurement Lakehouse

Lộ trình phát triển được thiết kế theo triết lý: **Tự tay giải quyết bằng First-Principles trước -> Thấu hiểu bản chất -> Áp dụng Modern Tools/Frameworks tương ứng sau.**

---

## Phase 1: Ingestion & Bronze Layer (Handcrafted Core) - Hiện tại

Mục tiêu: Xây dựng nền móng kiến trúc Hexagonal vững chắc, tự tay làm cơ chế phân vùng, atomic write, checksum manifest và quản lý trạng thái run trên PostgreSQL.

- [x] **Ingestion Domain Model**: `IngestionWindow` (ràng buộc nghiêm ngặt cửa sổ 1 ngày), `IngestionRun` (state machine), `BronzeManifest` (schema v1, SHA-256), `PublishedBatch`, `VerificationResult`.
- [x] **Application Ports**: `SourcePort`, `BronzePort`, `RunRepositoryPort` sử dụng `typing.Protocol`.
- [x] **Use Cases**:
  - [x] `IngestDailyWindow`: Điều phối 1 ngày, quản lý run lifecycle.
  - [x] `IngestDateRange`: Duyệt qua dải ngày theo từng cửa sổ 1 ngày độc lập.
  - [x] `VerifyBronze`: Xác thực tính toàn vẹn on-disk bronze đối chiếu với manifest.
  - [x] `RecoverIngestionRun`: Phục hồi thủ công các run bị crash hoặc treo ở `IN_PROGRESS`.
- [x] **Adapters (Handcrafted)**:
  - [x] `FakeTenderSource`: Giả lập payload tài nguyên `tbmt`.
  - [x] `LocalBronzeWriter`: Atomic file write (`.tmp` -> `os.replace`), tính toán digest SHA-256, ghi manifest JSON.
  - [x] `PostgresRunRepository`: SQLAlchemy 2.0 ORM kết nối PostgreSQL schema `control`.
- [x] **Control DB & Migrations**: PostgreSQL 17 Docker Compose, Alembic migration cho bảng `control.ingestion_runs`.
- [x] **CLI Entrypoint**: Typer CLI `procurement` (`ingest`, `ingest-range`, `bronze-verify-run`, `bronze-verify-window`, `bronze-recover`).
- [x] **Test & Quality Suite**: 59 unit tests (mock 100% I/O), integration test suite với Postgres, Ruff linter/formatter, Pyright strict type check.
- [x] **Refactoring Technical Debt**:
  - [x] Đổi tên thư mục `boostrap/` -> `bootstrap/`.
  - [x] Đổi tên file `recover_ingention_run.py` -> `recover_ingestion_run.py`.

---

## Phase 2: Real Data Ingestion (Muasamcong API & Crawling Engine)

Mục tiêu: Thay thế `FakeTenderSource` bằng nguồn dữ liệu thật từ Hệ thống Mạng Đấu thầu Quốc gia (dauthau.gpc.gov.vn / vbid).

- [ ] **Tự viết tay (Handcrafted)**:
  - [ ] `MuasamcongHttpSource`: Client HTTP sử dụng `httpx`, xử lý request/response JSON của portal thầu.
  - [ ] Xử lý rate limiting cơ bản (token bucket / fixed window) và exponential backoff khi gặp HTTP 429/503.
  - [ ] Phân trang (Pagination) và duyệt theo ngày đăng tải (`tbmt`).
- [ ] **Mở rộng các loại tài nguyên**:
  - [ ] `kqlcnt`: Kết quả lựa chọn nhà thầu.
  - [ ] `khlcnt`: Kế hoạch lựa chọn nhà thầu.
  - [ ] `nhathau`: Hồ sơ năng lực nhà thầu.
  - [ ] `chudautu`: Danh mục bên mời thầu / chủ đầu tư.
- [ ] **Đối chiếu & Đánh giá công cụ**:
  - *Tooling*: `playwright` / `scrapy` (cho dynamic JS rendering hoặc scraping phức tạp), `tenacity` (retry engine chuyên nghiệp).

---

## Phase 3: Silver Layer (Cleansing, Structuring & Storage Modernization)

Mục tiêu: Làm sạch dữ liệu JSONL thô ở Bronze, ép kiểu (type coercion), chuẩn hóa schema và lưu trữ dạng cột tối ưu.

- [ ] **Tự viết tay (Handcrafted)**:
  - [ ] Viết use case chuyển đổi Bronze -> Silver bằng Python thuần: đọc JSONL, flatten nested fields, ép kiểu ngày tháng/số tiền VND, loại bỏ duplicate records theo mã thông báo (`notifyNo`).
  - [ ] Xử lý Slowly Changing Dimensions (SCD Type 2) cho thông tin nhà thầu cập nhật theo thời gian.
- [ ] **Đối chiếu & Đánh giá công cụ (Tooling Evolution)**:
  - *Tooling*: Đánh giá **DuckDB** hoặc **Polars** để thay thế xử lý Python thuần (tăng tốc độ xử lý vector x10-x50 lần).
  - *Table Format*: Thay thế lưu trữ file thường bằng **Delta Lake (`delta-rs`)** hoặc **Apache Iceberg** để có ACID transactions, Time Travel, và Schema Enforcement tự động thay vì phải tự viết manifest JSON thủ công.

---

## Phase 4: Gold Layer (Dimensional Modeling & Analytics Serving)

Mục tiêu: Xây dựng kho dữ liệu phân tích phục vụ báo cáo, phân tích hành vi và truy vết rủi ro thầu.

- [ ] **Tự viết tay (Handcrafted)**:
  - [ ] Thiết kế Star Schema (Fact Bidding Events, Dim Vendor, Dim Procuring Entity, Dim Date).
  - [ ] Viết queries phân tích: Tỷ lệ tiết kiệm của gói thầu (`(giá gói thầu - giá trúng thầu) / giá gói thầu`), tần suất tham gia chung của các cặp nhà thầu (cảnh báo quân xanh - quân đỏ).
- [ ] **Đối chiếu & Đánh giá công cụ (Tooling Evolution)**:
  - *Tooling*: Áp dụng **dbt-core** để chuẩn hóa data transformation pipelines, tự động sinh lineage graph và testing tài liệu.

---

## Phase 5: Orchestration & Automation

Mục tiêu: Tự động hóa chu kỳ chạy pipeline hàng ngày, lập lịch backfill và quản lý dependencies giữa các tầng Bronze -> Silver -> Gold.

- [ ] **Tự viết tay (Handcrafted)**:
  - [ ] Tự viết scheduler đơn giản bằng CLI kết hợp Cron/Task queue hoặc daemon process để hiểu rõ bài toán concurrency và dependency.
- [ ] **Đối chiếu & Đánh giá công cụ (Tooling Evolution)**:
  - *Tooling*: Đánh giá **Dagster** (Asset-based orchestration rất hợp với Lakehouse) hoặc **Apache Airflow** (chuẩn Enterprise) để thấy rõ cách framework tự động hóa retry, backfill dải ngày, và vẽ visual pipeline.

---

## Phase 6: Observability, Data Quality & Cloud Deployment

Mục tiêu: Đưa toàn bộ Lakehouse lên môi trường đám mây với hệ thống giám sát và kiểm định chất lượng tự động.

- [ ] **Cloud Storage Adapter**:
  - [ ] Implement `S3BronzeWriter` / `GCSBronzeWriter` (hoặc MinIO) theo đúng `BronzePort` đã thiết kế.
- [ ] **Observability**:
  - [ ] Chuyển đổi sang Structured Logging (`structlog`).
  - [ ] Xuất Prometheus metrics (thời gian chạy run, số record thu nạp, tỷ lệ lỗi) và cảnh báo qua Telegram/Slack.
- [ ] **Data Quality Framework**:
  - *Tooling*: Tích hợp **Great Expectations** hoặc **Soda Core** để kiểm định tự động chất lượng dữ liệu (ngưỡng null, dải giá trị ngân sách hợp lệ, tính duy nhất).
