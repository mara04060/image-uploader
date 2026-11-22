import importlib
import logging
import sys
import types
import unittest
from contextlib import nullcontext
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch


def load_app_without_optional_services():
    psycopg = types.ModuleType("psycopg")
    psycopg.Error = type("Error", (Exception,), {})
    psycopg.Connection = object
    psycopg.connect = Mock()

    image = SimpleNamespace(open=Mock())
    pil = types.ModuleType("PIL")
    pil.Image = image

    with patch.dict(sys.modules, {"psycopg": psycopg, "PIL": pil}), \
         patch.object(Path, "mkdir"), \
         patch.object(logging, "FileHandler", return_value=logging.NullHandler()):
        sys.modules.pop("app", None)
        return importlib.import_module("app")


app = load_app_without_optional_services()


class MockUploadService:
    def __init__(self):
        self.save_file = Mock()
        self.save_metadata = Mock()
        self.remove_file = Mock()
        self.connect = Mock(return_value=nullcontext())


class FileValidationTests(unittest.TestCase):
    def test_rejects_empty_file_without_image_processing(self):
        with patch.object(app, "is_real_image") as process_image:
            result = app.validate_file("photo.jpg", b"")

        self.assertEqual(result, "Empty file")
        process_image.assert_not_called()

    def test_rejects_oversized_file_before_image_processing(self):
        with patch.object(app, "MAX_FILE_SIZE", 4), \
             patch.object(app, "is_real_image") as process_image:
            result = app.validate_file("photo.jpg", b"12345")

        self.assertIn("File too large", result)
        process_image.assert_not_called()

    def test_rejects_disallowed_extension_before_image_processing(self):
        with patch.object(app, "ALLOWED_EXTENSIONS", {"jpg", "png", "gif"}), \
             patch.object(app, "is_real_image") as process_image:
            result = app.validate_file("document.txt", b"content")

        self.assertIn("Непідтримуваний формат", result)
        process_image.assert_not_called()

    def test_rejects_invalid_image_content(self):
        with patch.object(app, "is_real_image", return_value=False) as process_image:
            result = app.validate_file("photo.jpg", b"mock-image")

        self.assertIn("Image is not correct", result)
        process_image.assert_called_once_with("jpg", b"mock-image")

    def test_rejects_extension_content_mismatch(self):
        with patch.object(app, "is_real_image", return_value="png"):
            result = app.validate_file("photo.jpg", b"mock-image")

        self.assertIn("Image type mismatch", result)

    def test_accepts_supported_image_formats(self):
        cases = (("photo.jpg", "jpeg"), ("photo.jpeg", "jpeg"),
                 ("photo.png", "png"), ("photo.gif", "gif"))
        with patch.object(app, "ALLOWED_EXTENSIONS", {"jpg", "jpeg", "png", "gif"}):
            for filename, image_format in cases:
                with self.subTest(filename=filename), \
                     patch.object(app, "is_real_image", return_value=image_format):
                    self.assertIsNone(app.validate_file(filename, b"mock-image"))

    def test_image_processor_recognizes_jpeg(self):
        image_object = Mock(format="JPEG")
        image_context = Mock()
        image_context.__enter__ = Mock(return_value=image_object)
        image_context.__exit__ = Mock(return_value=False)
        with patch.object(app, "ALLOWED_EXTENSIONS", {"jpg"}), \
             patch.object(app.Image, "open", return_value=image_context) as open_image:
            result = app.is_real_image("jpg", b"mock-image")

        self.assertEqual(result, "jpeg")
        open_image.assert_called_once()
        image_object.verify.assert_called_once()

    def test_image_processor_rejects_unknown_format(self):
        image_object = Mock(format="TIFF")
        image_context = Mock()
        image_context.__enter__ = Mock(return_value=image_object)
        image_context.__exit__ = Mock(return_value=False)
        with patch.object(app, "ALLOWED_EXTENSIONS", {"jpg", "png"}), \
             patch.object(app.Image, "open", return_value=image_context):
            self.assertFalse(app.is_real_image("jpg", b"mock-image"))

    def test_image_processor_returns_false_when_decoder_raises(self):
        with patch.object(app.Image, "open", side_effect=ValueError("invalid image")):
            self.assertFalse(app.is_real_image("jpg", b"mock-image"))

    def test_extracts_file_extension_case_insensitively(self):
        self.assertEqual(app.get_file_ext("Photo.JPG"), "jpg")


class MultipartTests(unittest.TestCase):
    def test_extract_boundary(self):
        self.assertEqual(
            app._extract_boundary('multipart/form-data; boundary="test-boundary"'),
            b"test-boundary",
        )

    def test_extract_boundary_missing(self):
        self.assertEqual(app._extract_boundary("application/json"), b"")

    def test_parse_multiple_files(self):
        body = (
            b"--boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"one.jpg\"\r\n\r\n"
            b"one"
            b"\r\n--boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"two.png\"\r\n\r\n"
            b"two"
            b"\r\n--boundary--\r\n"
        )

        self.assertEqual(
            app._parse_multipart_body(body, b"boundary"),
            [("one.jpg", b"one"), ("two.png", b"two")],
        )

    def test_read_body_rejects_missing_content_length(self):
        handler = SimpleNamespace(headers={}, rfile=BytesIO(b"body"))
        with self.assertRaisesRegex(ValueError, "Content-Length"):
            app._read_body(handler)

    def test_read_body_rejects_invalid_content_length(self):
        handler = SimpleNamespace(headers={"Content-Length": "bad"}, rfile=BytesIO())
        with self.assertRaisesRegex(ValueError, "Invalid Content-Length"):
            app._read_body(handler)

    def test_read_body_rejects_empty_body(self):
        handler = SimpleNamespace(headers={"Content-Length": "0"}, rfile=BytesIO())
        with self.assertRaisesRegex(ValueError, "Empty request body"):
            app._read_body(handler)

    def test_read_body_rejects_oversized_request_without_reading(self):
        stream = Mock()
        handler = SimpleNamespace(
            headers={"Content-Length": str(10 * app.MAX_FILE_SIZE + 1)},
            rfile=stream,
        )
        with self.assertRaisesRegex(ValueError, "Request too large"):
            app._read_body(handler)
        stream.read.assert_not_called()


class UploadLogicTests(unittest.TestCase):
    def setUp(self):
        self.service = MockUploadService()
        self.handler = SimpleNamespace()
        self.patches = (
            patch.object(app, "download_file", self.service.save_file),
            patch.object(app, "get_db_connection", self.service.connect),
            patch.object(app, "insert_image", self.service.save_metadata),
            patch.object(app, "delete_file", self.service.remove_file),
            patch.object(app, "send_params"),
            patch.object(app, "validate_file", return_value=None),
            patch.object(app.uuid, "uuid4", return_value=SimpleNamespace(hex="unique-id")),
        )
        for item in self.patches:
            item.start()
        self.addCleanup(self.stop_patches)

    def stop_patches(self):
        for item in reversed(self.patches):
            item.stop()

    def test_saves_valid_upload_through_mock_service(self):
        files = [("photo.jpg", b"mock-image")]

        app.validate_files(self.handler, files)

        self.service.save_file.assert_called_once_with("unique-id.jpg", b"mock-image")
        self.service.save_metadata.assert_called_once_with(
            ANY, "unique-id.jpg", "photo.jpg", len(b"mock-image"), "jpg"
        )
        app.send_params.assert_called_once_with(
            self.handler, 200, "Файли успішно завантажені", ["unique-id.jpg"]
        )

    def test_rejects_invalid_upload_without_calling_services(self):
        app.validate_file.return_value = "invalid"

        app.validate_files(self.handler, [("photo.jpg", b"invalid")])

        self.service.save_file.assert_not_called()
        self.service.connect.assert_not_called()
        self.service.save_metadata.assert_not_called()
        app.send_params.assert_called_once_with(self.handler, 400, "invalid")

    def test_removes_mock_saved_file_when_metadata_service_fails(self):
        self.service.save_metadata.side_effect = app.psycopg.Error("service failure")

        app.validate_files(self.handler, [("photo.jpg", b"mock-image")])

        self.service.remove_file.assert_called_once_with("unique-id.jpg")
        app.send_params.assert_called_once_with(self.handler, 500, "Files not saved")

    def test_post_handler_passes_uploaded_items_to_validation(self):
        handler = SimpleNamespace(path="/upload")
        files = [("photo.jpg", b"mock-image")]
        with patch.object(app, "extract_file_data", return_value=files), \
             patch.object(app, "validate_files") as validate:
            app.Handler.do_POST(handler)

        validate.assert_called_once_with(handler, files)

    def test_post_handler_rejects_wrong_route(self):
        handler = SimpleNamespace(path="/wrong", send_error=Mock())
        app.Handler.do_POST(handler)

        handler.send_error.assert_called_once_with(404)


if __name__ == "__main__":
    unittest.main()
