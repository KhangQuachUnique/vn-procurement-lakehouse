import hashlib
import json
import os
import re
from collections.abc import Iterable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from vn_procurement_lakehouse.modules.ingestion.application.ports import (
    RawPayload,
)
from vn_procurement_lakehouse.modules.ingestion.domain.batch import (
    PublishedBatch,
)
from vn_procurement_lakehouse.modules.ingestion.domain.manifest import (
    BronzeManifest,
)
from vn_procurement_lakehouse.modules.ingestion.domain.run import (
    IngestionRun,
)
from vn_procurement_lakehouse.modules.ingestion.domain.verifications import (
    VerificationResult,
    VerificationStatus,
)
from vn_procurement_lakehouse.modules.ingestion.domain.window import (
    IngestionWindow,
)


class LocalBronzeWriter:
    def __init__(self, base_path: Path) -> None:
        self.base_path = base_path

    def write(
        self,
        window: IngestionWindow,
        records: Iterable[RawPayload],
        *,
        run_id: UUID,
    ) -> PublishedBatch:
        # 1. Xây dựng đường dẫn Bronze
        if re.fullmatch(r"[a-zA-Z0-9_-]+", window.resource) is None:
            raise ValueError("Invalid resource name")

        run_dir = (
            self.base_path
            / window.resource
            / f"date={window.start_date.isoformat()}"
            / "runs"
            / str(run_id)
        )

        # Không sử dụng lại thư mục của run đã tồn tại
        run_dir.mkdir(parents=True, exist_ok=False)

        temp_data = run_dir / "part-000.jsonl.tmp"
        final_data = run_dir / "part-000.jsonl"

        temp_manifest = run_dir / "manifest.json.tmp"
        final_manifest = run_dir / "manifest.json"

        # 2. Ghi records và tính checksum
        count, checksum = self._write_records(
            temp_data,
            records,
        )

        # 3. Publish data file
        os.replace(temp_data, final_data)

        # 4. Tạo domain manifest
        manifest = BronzeManifest(
            schema_version=1,
            run_id=run_id,
            resource=window.resource,
            window_start=window.start_date,
            window_end_exclusive=window.end_date_exclusive,
            record_count=count,
            data_file=final_data.name,
            sha256=checksum,
            created_at=datetime.now(UTC),
        )

        # 5. Publish manifest CUỐI CÙNG
        self._publish_manifest(
            temp_manifest,
            final_manifest,
            manifest,
        )

        # 6. Trả thông tin cho application
        return PublishedBatch(
            run_id=run_id,
            record_count=count,
            storage_uri=str(final_data),
        )

    def _write_records(
        self,
        path: Path,
        records: Iterable[RawPayload],
    ) -> tuple[int, str]:
        count = 0
        digest = hashlib.sha256()

        with path.open("xb") as file:
            for record in records:
                line = (
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")

                file.write(line)
                digest.update(line)
                count += 1

            file.flush()
            os.fsync(file.fileno())

        return count, digest.hexdigest()

    def _publish_manifest(
        self,
        temp_path: Path,
        final_path: Path,
        manifest: BronzeManifest,
    ) -> None:
        # Convert dataclass -> JSON-compatible dict
        payload = asdict(manifest)

        payload["run_id"] = str(manifest.run_id)
        payload["window_start"] = manifest.window_start.isoformat()
        payload["window_end_exclusive"] = manifest.window_end_exclusive.isoformat()
        payload["created_at"] = manifest.created_at.isoformat()

        with temp_path.open("x", encoding="utf-8") as file:
            json.dump(
                payload,
                file,
                ensure_ascii=False,
                indent=2,
            )
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_path, final_path)

    def verify(self, run: IngestionRun) -> VerificationResult:
        run_dir = (
            self.base_path
            / run.window.resource
            / f"date={run.window.start_date.isoformat()}"
            / "runs"
            / str(run.run_id)
        )

        manifest_path = run_dir / "manifest.json"
        data_path = run_dir / "part-000.jsonl"

        if not manifest_path.exists():
            return VerificationResult(
                run_id=run.run_id,
                status=VerificationStatus.MISSING,
                reason="Manifest file is missing.",
            )

        if not data_path.exists():
            return VerificationResult(
                run_id=run.run_id,
                status=VerificationStatus.MISSING,
                reason="Data file is missing.",
            )

        with manifest_path.open("r", encoding="utf-8") as file:
            manifest_data = json.load(file)

        expected_checksum = manifest_data.get("sha256")
        if expected_checksum is None:
            return VerificationResult(
                run_id=run.run_id,
                status=VerificationStatus.INVALID,
                reason="Manifest file does not contain a checksum.",
            )

        # Calculate the actual checksum of the data file
        digest = hashlib.sha256()
        with data_path.open("rb") as file:
            for chunk in iter(lambda: file.read(8192), b""):
                digest.update(chunk)

        actual_checksum = digest.hexdigest()

        if actual_checksum != expected_checksum:
            return VerificationResult(
                run_id=run.run_id,
                status=VerificationStatus.INVALID,
                reason="Checksum mismatch between manifest and data file.",
            )

        return VerificationResult(
            run_id=run.run_id,
            status=VerificationStatus.VERIFIED,
            record_count=manifest_data.get("record_count"),
        )
