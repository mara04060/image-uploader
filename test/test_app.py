import tempfile
import sys
import types
import unittest
import os
from contextlib import nullcontext
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

try:
    import psycopg
except ImportError:
    psycopg = types.ModuleType("psycopg")
    psycopg.Error = Exception
    psycopg.connect = MagicMock()
    psycopg.Connection = object
    sys.modules["psycopg"] = psycopg

import app


class MultipartMockHandler:
    def __init__(self, body: bytes, content_type: str):
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(body)),
        }
        self.rfile = BytesIO(body)


class MockDatabaseTransaction:
    def __init__(self, records, commit_error=None):
        self.records = records
        self.commit_error = commit_error
        self.snapshot = None
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        self.snapshot = list(self.records)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self.rollback()
        elif not self.committed:
            self.committed = True
        return False

    def commit(self):
        if self.commit_error is not None:
            raise self.commit_error
        self.committed = True

    def rollback(self):
        self.records[:] = self.snapshot
        self.rolled_back = True


class AppUnitTests(unittest.TestCase):
    @staticmethod
    def make_image(extension="jpg"):
        from PIL import Image

        output = BytesIO()
        image_format = "JPEG" if extension in {"jpg", "jpeg"} else extension.upper()
        Image.new("RGB", (2, 2), color="red").save(output, format=image_format)
        return output.getvalue()

    def make_multipart_handler(self, files):
        boundary = b"unit-test-boundary"
        body = bytearray()
        for filename, data in files:
            body.extend(b"--" + boundary + b"\r\n")
            body.extend(
                b'Content-Disposition: form-data; name="file"; filename="'
                + filename.encode("ascii")
                + b'"\r\nContent-Type: application/octet-stream\r\n\r\n'
            )
            body.extend(data)
            body.extend(b"\r\n")
        body.extend(b"--" + boundary + b"--\r\n")
        return MultipartMockHandler(
            bytes(body),
            "multipart/form-data; boundary=unit-test-boundary",
        )

    def test_allowed_extensions_match_readme_defaults_and_normalize_config(self):
        self.assertEqual(
            app.parse_allowed_extensions(" JPG, png,,GIF, jpeg "),
            {"jpg", "png", "gif", "jpeg"},
        )

    def test_app_config_decorator_accepts_valid_environment(self):
        @app.validate_app_config
        def get_config():
            return app.APP_PORT, app.POSTGRES_PORT, app.MAX_FILE_SIZE

        with patch.dict(
            os.environ,
            {
                "APP_PORT": "8001",
                "POSTGRES_PORT": "5433",
                "MAX_FILE_SIZE": "10",
                "ALLOWED_EXTENSIONS": " jpg, png ",
                "POSTGRES_PASSWORD": "test-password",
            },
            clear=True,
        ):
            config = get_config()

        self.assertEqual(
            config,
            (8001, 5433, 10 * 1024 * 1024),
        )
        self.assertEqual(app.ALLOWED_EXTENSIONS, {"jpg", "png"})

    def test_app_config_rejects_invalid_integer(self):
        @app.validate_app_config
        def get_config():
            return app.POSTGRES_PORT

        for name, value in (
            ("POSTGRES_PORT", "abc"),
            ("POSTGRES_PORT", "0"),
            ("POSTGRES_PORT", "-1"),
            ("POSTGRES_PORT", "65536"),
            ("MAX_FILE_SIZE", "-5"),
            ("APP_PORT", "70000"),
        ):
            with (
                patch.dict(
                    os.environ,
                    {"POSTGRES_PASSWORD": "test", name: value},
                    clear=True,
                ),
                self.assertRaises(app.ConfigurationError),
            ):
                get_config()

    def test_app_config_rejects_empty_extension_list(self):
        @app.validate_app_config
        def get_config():
            return app.ALLOWED_EXTENSIONS

        with (
            patch.dict(
                os.environ,
                {
                    "ALLOWED_EXTENSIONS": " , , ",
                    "POSTGRES_PASSWORD": "test",
                },
                clear=True,
            ),
            self.assertRaises(app.ConfigurationError),
        ):
            get_config()

    def test_get_file_extension_is_case_insensitive(self):
        self.assertEqual(app.get_file_extension("PHOTO.JPEG"), "jpeg")
        self.assertEqual(app.get_file_extension("photo"), "")

    def test_validate_file_accepts_allowed_file(self):
        with patch.object(app, "ALLOWED_EXTENSIONS", {"jpg", "png"}):
            name, extension, size = app.validate_file(
                "photo.JPG", self.make_image("jpg")
            )

        self.assertEqual(name, "photo.JPG")
        self.assertEqual(extension, "jpg")
        self.assertEqual(size, len(self.make_image("jpg")))

    def test_validate_file_rejects_disallowed_extension(self):
        with patch.object(app, "ALLOWED_EXTENSIONS", {"jpg", "png"}):
            with self.assertRaises(app.ImageValidationError) as context:
                app.validate_file("document.txt", b"text")

        self.assertIn("Unsupported file extension: txt", str(context.exception))

    def test_validate_file_rejects_empty_and_oversized_files(self):
        with self.assertRaises(app.ImageValidationError):
            app.validate_file("photo.jpg", b"")

        with patch.object(app, "MAX_FILE_SIZE", 3):
            with self.assertRaises(app.ImageValidationError):
                app.validate_file("photo.jpg", b"1234")

    def test_validate_file_rejects_non_image_content(self):
        with patch.object(app, "ALLOWED_EXTENSIONS", {"jpg", "png"}):
            with self.assertRaises(app.ImageValidationError) as context:
                app.validate_file("photo.jpg", b"plain text")

        self.assertIn("invalid or corrupted image content", str(context.exception))

    def test_validate_file_rejects_corrupted_image_content(self):
        data = bytearray(self.make_image("png"))
        data[-10:] = b"\x00" * 10

        with patch.object(app, "ALLOWED_EXTENSIONS", {"png"}):
            with self.assertRaises(app.ImageValidationError):
                app.validate_file("photo.png", bytes(data))

    def test_validate_file_rejects_extension_mismatch(self):
        with patch.object(app, "ALLOWED_EXTENSIONS", {"jpg", "png"}):
            with self.assertRaises(app.ImageValidationError) as context:
                app.validate_file("photo.jpg", self.make_image("png"))

        self.assertIn("does not match extension", str(context.exception))

    def test_validate_file_rejects_unknown_format(self):
        image = MagicMock()
        image.format = "BMP"
        image_context = MagicMock()
        image_context.__enter__.return_value = image
        image_context.__exit__.return_value = False

        with patch.object(app.Image, "open", return_value=image_context):
            with self.assertRaises(app.ImageValidationError) as context:
                app.validate_image_content("photo.jpg", b"unknown-format")

        self.assertIn("unsupported image content", str(context.exception))

    def test_validate_file_rejects_decompression_bomb(self):
        with patch.object(
            app.Image,
            "open",
            side_effect=app.DecompressionBombError("bomb"),
        ):
            with self.assertRaises(app.ImageValidationError) as context:
                app.validate_image_content("bomb.png", b"image")

        self.assertIn("too large for safe image decoding", str(context.exception))

    def test_validate_file_rejects_zero_dimensions(self):
        image = MagicMock()
        image.format = "PNG"
        image.size = (0, 100)
        image.n_frames = 1
        image_context = MagicMock()
        image_context.__enter__.return_value = image
        image_context.__exit__.return_value = False

        with patch.object(app.Image, "open", return_value=image_context):
            with self.assertRaises(app.ImageValidationError) as context:
                app.validate_image_content("zero.png", b"image")

        self.assertIn("invalid image dimensions", str(context.exception))

    def test_multipart_parser_supports_multiple_files(self):
        body = (
            b"--test-boundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="one.jpg"\r\n\r\n'
            b"first\r\n"
            b"--test-boundary\r\n"
            b'Content-Disposition: form-data; name="file"; filename="two.png"\r\n\r\n'
            b"second\r\n"
            b"--test-boundary--\r\n"
        )
        handler = MultipartMockHandler(
            body, 'multipart/form-data; boundary="test-boundary"'
        )

        files = app.extract_file_data(handler)

        self.assertEqual(files, [("one.jpg", b"first"), ("two.png", b"second")])

    def test_multipart_parser_rejects_missing_boundary(self):
        with self.assertRaises(app.MultipartError):
            app._extract_boundary("multipart/form-data")

    def test_request_body_size_overflow_is_rejected_before_reading(self):
        handler = SimpleNamespace(
            headers={"Content-Length": "11"},
            rfile=MagicMock(),
        )
        with patch.object(app, "MAX_REQUEST_SIZE", 10):
            with self.assertRaises(app.RequestError):
                app._read_body(handler)

        handler.rfile.read.assert_not_called()

    def test_get_page_defaults_and_validates_page_number(self):
        self.assertEqual(app.get_page({}), 1)
        self.assertEqual(app.get_page({"page": ["2"]}), 2)

        with self.assertRaises(app.PaginationError):
            app.get_page({"page": ["1", "2"]})
        with self.assertRaises(app.PaginationError):
            app.get_page({"page": ["abc"]})
        with self.assertRaises(app.PaginationError):
            app.get_page({"page": ["0"]})

    def test_save_and_delete_file_use_mock_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(app, "UPLOAD_DIR", Path(directory)):
                saved = app.save_file("mock-image.jpg", b"image")
                self.assertEqual(saved.read_bytes(), b"image")

                app.delete_file("mock-image.jpg")
                self.assertFalse(saved.exists())

    def test_partial_file_write_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "partial.jpg"
            mock_file = MagicMock()
            mock_file.__enter__.return_value.write.side_effect = OSError("disk full")
            mock_file.__exit__.return_value = False

            with (
                patch.object(app, "UPLOAD_DIR", Path(directory)),
                patch.object(Path, "open", return_value=mock_file),
                patch.object(Path, "unlink", autospec=True) as unlink,
            ):
                with self.assertRaises(app.ImageFileWriteError):
                    app.save_file("partial.jpg", b"partial")

            unlink.assert_called_once()

    def test_save_second_file_failure_cleans_first_saved_file(self):
        first = Path("first.jpg")
        with (
            patch.object(
                app,
                "save_file",
                side_effect=[
                    first,
                    app.ImageFileWriteError("second write failed"),
                ],
            ),
            patch.object(Path, "unlink", autospec=True) as unlink,
        ):
            with self.assertRaises(app.ImageFileWriteError):
                app._save_uploaded_files(
                    [
                        ("first.jpg", "first.jpg", "jpg", 1, b"a"),
                        ("second.jpg", "second.jpg", "jpg", 1, b"b"),
                    ]
                )

        unlink.assert_called_once()

    def test_cleanup_retries_unlink_of_first_and_second_files(self):
        saved_paths = [Path("first.jpg"), Path("second.jpg")]
        unlink_error = OSError("unlink failed")

        with patch.object(
            app,
            "save_file",
            side_effect=[
                saved_paths[0],
                saved_paths[1],
                app.ImageFileWriteError("third write failed"),
            ],
        ):
            with patch.object(
                Path,
                "unlink",
                autospec=True,
                side_effect=[unlink_error, unlink_error],
            ) as unlink:
                with self.assertRaises(app.ImageFileWriteError):
                    app._save_uploaded_files(
                        [
                            ("first.jpg", "first.jpg", "jpg", 1, b"a"),
                            ("second.jpg", "second.jpg", "jpg", 1, b"b"),
                            ("third.jpg", "third.jpg", "jpg", 1, b"c"),
                        ]
                    )

        self.assertEqual(unlink.call_count, 2)

    def test_unlink_os_error_rolls_back_delete_transaction(self):
        connection = MagicMock()
        with (
            patch.object(
                app,
                "get_db_connection",
                return_value=nullcontext(connection),
            ),
            patch.object(app, "get_image_file_name", return_value="uuid.jpg"),
            patch.object(app, "delete_image", return_value="uuid.jpg"),
            patch.object(
                app,
                "delete_file",
                side_effect=app.ImageFileDeleteError("unlink failed"),
            ),
        ):
            with self.assertRaises(app.ImageFileDeleteError):
                app.delete_image_transaction(7)

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()

    def test_database_helpers_use_mock_connection(self):
        connection = MagicMock()
        with patch.object(app, "db_function", return_value=[{"id": 1}]) as db:
            items = app.get_images(connection, 2)

        self.assertEqual(items, [{"id": 1}])
        db.assert_called_once_with(connection, "public.get_images", 2, 10)

    def test_insert_uploaded_files_mocks_database_service(self):
        connection = MagicMock()
        files = [("uuid.jpg", "original.jpg", "jpg", 5, b"image")]

        with patch.object(app, "insert_image", return_value=7) as insert:
            names = app._insert_uploaded_files(connection, files)

        self.assertEqual(names, ["uuid.jpg"])
        insert.assert_called_once_with(
            connection, "uuid.jpg", "original.jpg", 5, "jpg"
        )

    def test_insert_second_database_record_failure_cleans_saved_files(self):
        connection = MagicMock()
        files = [
            ("first.jpg", "first.jpg", "jpg", 1, b"a"),
            ("second.jpg", "second.jpg", "jpg", 1, b"b"),
        ]

        with (
            patch.object(app, "insert_image", side_effect=[7, Exception("DB insert failed")]),
            patch.object(app, "get_db_connection", return_value=nullcontext(connection)),
            patch.object(
                app,
                "_save_uploaded_files",
                return_value=[Path("first.jpg"), Path("second.jpg")],
            ),
            patch.object(Path, "unlink", autospec=True) as unlink,
        ):
            with self.assertRaises(Exception):
                app.upload_files.__wrapped__.__wrapped__(
                    SimpleNamespace(),
                    files,
                )

        self.assertEqual(unlink.call_count, 2)

    def test_multipart_upload_persists_file_and_metadata_in_one_mock_transaction(self):
        records = []
        transaction = MockDatabaseTransaction(records)
        handler = self.make_multipart_handler(
            [
                ("first.jpg", self.make_image("jpg")),
                ("second.png", self.make_image("png")),
            ]
        )

        def insert_record(connection, filename, original_name, size, file_type):
            connection.records.append(
                {
                    "filename": filename,
                    "original_name": original_name,
                    "size": size,
                    "file_type": file_type,
                }
            )
            return len(connection.records)

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(app, "UPLOAD_DIR", Path(directory)),
                patch.object(app, "get_db_connection", return_value=transaction),
                patch.object(app, "insert_image", side_effect=insert_record),
                patch.object(app, "send_params") as send_params,
            ):
                transaction.records = records
                app.upload_files(handler)

            self.assertTrue(transaction.committed)
            self.assertFalse(transaction.rolled_back)
            self.assertEqual(len(records), 2)
            for record in records:
                saved_path = Path(directory) / record["filename"]
                self.assertTrue(saved_path.is_file())
                self.assertEqual(saved_path.stat().st_size, record["size"])
            send_params.assert_called_once()
            self.assertEqual(send_params.call_args.args[1], 200)

    def test_multipart_upload_rolls_back_partial_metadata_and_removes_files(self):
        records = []
        transaction = MockDatabaseTransaction(records)
        handler = self.make_multipart_handler(
            [
                ("first.jpg", self.make_image("jpg")),
                ("second.png", self.make_image("png")),
            ]
        )
        insert_count = 0

        def insert_record(connection, filename, original_name, size, file_type):
            nonlocal insert_count
            insert_count += 1
            connection.records.append(filename)
            if insert_count == 2:
                raise psycopg.Error("second insert failed")
            return insert_count

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(app, "UPLOAD_DIR", Path(directory)),
                patch.object(app, "get_db_connection", return_value=transaction),
                patch.object(app, "insert_image", side_effect=insert_record),
                patch.object(app, "send_params") as send_params,
            ):
                transaction.records = records
                app.upload_files(handler)

            self.assertTrue(transaction.rolled_back)
            self.assertFalse(transaction.committed)
            self.assertEqual(records, [])
            self.assertEqual(list(Path(directory).iterdir()), [])
            send_params.assert_called_once()
            self.assertEqual(send_params.call_args.args[1], 500)

    def test_upload_commit_failure_removes_saved_files(self):
        handler = SimpleNamespace()
        files = [("uuid.jpg", "original.jpg", "jpg", 5, b"image")]
        saved_path = Path("uuid.jpg")
        connection_context = MagicMock()
        connection_context.__enter__.return_value = MagicMock()
        connection_context.__exit__.side_effect = psycopg.Error("commit failed")

        with (
            patch.object(app, "_save_uploaded_files", return_value=[saved_path]),
            patch.object(app, "get_db_connection", return_value=connection_context),
            patch.object(app, "_insert_uploaded_files", return_value=["uuid.jpg"]),
            patch.object(Path, "unlink", autospec=True) as unlink,
        ):
            with self.assertRaises(psycopg.Error):
                app.upload_files.__wrapped__.__wrapped__(handler, files)

        unlink.assert_called_once()

    def test_upload_file_workflow_mocks_database_and_storage(self):
        handler = SimpleNamespace()
        files = [("uuid.jpg", "original.jpg", "jpg", 5, b"image")]
        connection = MagicMock()
        connection_context = MagicMock()
        connection_context.__enter__.return_value = connection
        connection_context.__exit__.return_value = False

        with (
            patch.object(app, "_save_uploaded_files", return_value=[Path("uuid.jpg")]),
            patch.object(app, "get_db_connection", return_value=connection_context),
            patch.object(app, "_insert_uploaded_files", return_value=["uuid.jpg"]),
            patch.object(app, "send_params") as send_params,
        ):
            original = app.upload_files.__wrapped__.__wrapped__
            original(handler, files)

        send_params.assert_called_once_with(
            handler,
            200,
            "Файлы успешно загружены",
            ["uuid.jpg"],
        )

    def test_get_images_page_uses_mock_database_service(self):
        connection = MagicMock()
        connection_context = nullcontext(connection)

        with (
            patch.object(app, "get_db_connection", return_value=connection_context),
            patch.object(app, "get_images", return_value=[{"id": 1}]),
            patch.object(
                app,
                "get_pagination",
                return_value={"page": 1, "total_pages": 1},
            ),
        ):
            result = app.get_images_page(1)

        self.assertEqual(result["status"], 200)
        self.assertEqual(result["items"], [{"id": 1}])

    def test_delete_workflow_returns_404_for_missing_image(self):
        handler = SimpleNamespace()
        with (
            patch.object(
                app,
                "delete_image_transaction",
                side_effect=app.ImageNotFoundError("Image not found: 99"),
            ),
            patch.object(app, "send_params") as send_params,
        ):
            app.delete_image_file(handler, 99)

        send_params.assert_called_once_with(
            handler, 404, "Image not found: 99"
        )

    def test_delete_transaction_commits_after_file_removal(self):
        connection = MagicMock()
        with (
            patch.object(
                app,
                "get_db_connection",
                return_value=nullcontext(connection),
            ),
            patch.object(app, "get_image_file_name", return_value="uuid.jpg"),
            patch.object(app, "delete_image", return_value="original.jpg"),
            patch.object(app, "delete_file") as delete_file,
        ):
            file_name = app.delete_image_transaction(7)

        self.assertEqual(file_name, "uuid.jpg")
        delete_file.assert_called_once_with("uuid.jpg")
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()

    def test_delete_transaction_rolls_back_when_file_removal_fails(self):
        connection = MagicMock()
        with (
            patch.object(
                app,
                "get_db_connection",
                return_value=nullcontext(connection),
            ),
            patch.object(app, "get_image_file_name", return_value="uuid.jpg"),
            patch.object(app, "delete_image", return_value="original.jpg"),
            patch.object(
                app,
                "delete_file",
                side_effect=app.ImageFileDeleteError("File not found"),
            ),
        ):
            with self.assertRaises(app.ImageFileDeleteError):
                app.delete_image_transaction(7)

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()

    def test_delete_commit_failure_rolls_back_transaction(self):
        connection = MagicMock()
        connection.commit.side_effect = psycopg.Error("commit failed")

        with (
            patch.object(
                app,
                "get_db_connection",
                return_value=nullcontext(connection),
            ),
            patch.object(app, "get_image_file_name", return_value="uuid.jpg"),
            patch.object(app, "delete_image", return_value="original.jpg"),
            patch.object(app, "delete_file"),
        ):
            with self.assertRaises(psycopg.Error):
                app.delete_image_transaction(7)

        connection.rollback.assert_called_once_with()

    def test_delete_commit_failure_occurs_after_file_has_been_removed(self):
        connection = MagicMock()
        connection.commit.side_effect = psycopg.Error("commit failed")

        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "uuid.jpg"
            image_path.write_bytes(b"existing image")
            with (
                patch.object(app, "UPLOAD_DIR", Path(directory)),
                patch.object(
                    app,
                    "get_db_connection",
                    return_value=nullcontext(connection),
                ),
                patch.object(app, "get_image_file_name", return_value="uuid.jpg"),
                patch.object(app, "delete_image", return_value="uuid.jpg"),
            ):
                with self.assertRaises(psycopg.Error):
                    app.delete_image_transaction(7)

            connection.rollback.assert_called_once_with()
            self.assertFalse(image_path.exists())

    def test_database_delete_failure_rolls_back_and_keeps_file(self):
        transaction = MockDatabaseTransaction([])
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "uuid.jpg"
            image_path.write_bytes(b"existing image")
            with (
                patch.object(app, "UPLOAD_DIR", Path(directory)),
                patch.object(
                    app,
                    "get_db_connection",
                    return_value=transaction,
                ),
                patch.object(
                    app, "get_image_file_name", return_value="uuid.jpg"
                ),
                patch.object(
                    app,
                    "delete_image",
                    side_effect=app.ImageDatabaseDeleteError("database failed"),
                ),
                patch.object(app, "delete_file") as delete_file,
            ):
                with self.assertRaises(app.ImageDatabaseDeleteError):
                    app.delete_image_transaction(7)

            self.assertTrue(transaction.rolled_back)
            self.assertFalse(transaction.committed)
            delete_file.assert_not_called()
            self.assertTrue(image_path.is_file())

    def test_delete_missing_file_is_not_found_and_does_not_commit(self):
        connection = MagicMock()
        with (
            patch.object(
                app,
                "get_db_connection",
                return_value=nullcontext(connection),
            ),
            patch.object(
                app,
                "get_image_file_name",
                side_effect=app.ImageNotFoundError("Image not found: 404"),
            ),
        ):
            with self.assertRaises(app.ImageNotFoundError):
                app.delete_image_transaction(404)

        connection.commit.assert_not_called()
        connection.rollback.assert_not_called()

    def test_repeat_delete_is_rejected_as_not_found(self):
        connection = MagicMock()
        first_context = nullcontext(connection)
        second_context = nullcontext(connection)

        with (
            patch.object(
                app,
                "get_db_connection",
                side_effect=[first_context, second_context],
            ),
            patch.object(
                app,
                "get_image_file_name",
                side_effect=[
                    "uuid.jpg",
                    app.ImageNotFoundError("Image not found: 7"),
                ],
            ),
            patch.object(app, "delete_image", return_value="uuid.jpg"),
            patch.object(app, "delete_file"),
        ):
            self.assertEqual(app.delete_image_transaction(7), "uuid.jpg")
            with self.assertRaises(app.ImageNotFoundError):
                app.delete_image_transaction(7)

    def test_delete_file_raises_when_file_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(app, "UPLOAD_DIR", Path(directory)):
                with self.assertRaises(app.ImageFileDeleteError):
                    app.delete_file("missing.jpg")


if __name__ == "__main__":
    unittest.main()
