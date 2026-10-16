# Coding Conventions & Engineering Standards

## 1. Naming Conventions
- **Folders & Modules**: `snake_case` (ví dụ: `local_bronze_writer.py`, `ingest_daily_window.py`).
- **Classes, Entities & Value Objects**: `PascalCase` (ví dụ: `BronzeManifest`, `IngestionWindow`, `PostgresRunRepository`).
- **Ports (Interfaces)**: `PascalCase` kết thúc bằng hậu tố `Port` sử dụng `typing.Protocol` (ví dụ: `SourcePort`, `BronzePort`, `RunRepositoryPort`).
- **Functions, Methods & Variables**: `snake_case` (ví dụ: `complete_if_running`, `verify_run`).
- **Constants & Enums**: `UPPER_SNAKE_CASE` (ví dụ: `RunStatus.IN_PROGRESS`, `VerificationStatus.VERIFIED`, `PROJECT_ROOT`).
- **Database Objects**:
  - Schema: Chữ thường (ví dụ: `control`).
  - Table: `snake_case`, danh từ số nhiều (ví dụ: `ingestion_runs`).
  - Check Constraints: `ck_<table>_<condition>` (ví dụ: `ck_ingestion_runs_status`).
  - Indexes: `ix_<table>_<columns>` (ví dụ: `ix_ingestion_runs_resource_day`).

## 2. Type Safety & Domain Modeling Standards
- **Strict Typing**: Mọi module phải thỏa mãn cấu hình `pyright` nghiêm ngặt, type hinting 100% cho hàm và thuộc tính.
- **Data Structures**:
  - Ưu tiên `dataclass(frozen=True, slots=True)` cho value objects không thay đổi (immutable).
  - Sử dụng `__post_init__` để thực thi triệt để validation và fail-fast các invariants.
  - Sử dụng `date` và `datetime` (bắt buộc timezone-aware, UTC) cho các trường thời gian.
- **Port Abstraction**: Sử dụng `typing.Protocol` không kế thừa trực tiếp để đạt Loose Coupling thực sự.

## 3. Error Handling Standards
- **Domain Layer**:
  - Ném ngoại lệ chuẩn (`ValueError`, `TypeError`) ngay lập tức khi phát hiện dữ liệu không thỏa mãn nghiệp vụ.
- **Application Layer**:
  - Bắt toàn bộ lỗi bất ngờ khi gọi Adapter, đảm bảo cập nhật trạng thái `run.fail()` và persist vào Database.
  - Sử dụng `logger.exception()` để ghi lại đầy đủ stack trace trước khi re-raise.
  - Không nuốt ngoại lệ (exception swallowing) làm mất dấu vết luồng chạy.
- **Adapters & Repositories**:
  - Sử dụng Context Manager (`with session_factory.begin() as session:`) để đảm bảo rollback tự động khi có lỗi database.
- **CLI Layer**:
  - Chuyển đổi ngoại lệ thành thông báo thân thiện cho terminal bằng `typer.BadParameter` hoặc `typer.Exit(code=1)`.

## 4. Testing Standards
- **Phân định rõ 2 tầng test**:
  - **Unit Tests (`tests/unit/`)**:
    - Mục tiêu: Chạy cực nhanh (< 2s), không I/O đĩa thật, không network, không database thật.
    - Phương pháp: Mock toàn bộ Ports thông qua `unittest.mock.MagicMock`.
    - Kiểm thử kỹ: Happy path, failure path, rollback state, edge cases của domain validation.
  - **Integration Tests (`tests/integration/`)**:
    - Mục tiêu: Kiểm tra tích hợp thực tế với hệ thống bên ngoài (PostgreSQL, filesystem).
    - Phải đánh dấu bằng `@pytest.mark.integration`.
    - Quản lý vòng đời database engine qua session-scoped fixtures.
- **Fixtures**:
  - Định nghĩa fixture dùng chung trong `tests/conftest.py`, có type annotations đầy đủ.
  - Tên fixture rõ nghĩa với tiền tố `sample_*` (ví dụ: `sample_window`, `sample_run_id`).

## 5. Technical Debt History (Resolved)
> [!NOTE]
> Codebase đã được chuẩn hóa đồng bộ 100%:
> 1. Thư mục Composition Root: `src/vn_procurement_lakehouse/bootstrap/`.
> 2. File Use Case phục hồi Ingestion: `recover_ingestion_run.py`.
