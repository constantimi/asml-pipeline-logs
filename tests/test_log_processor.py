import unittest
from unittest.mock import patch, Mock
from io import StringIO
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from log_processor import parse_line, decode_body, process_logs

class TestLogProcessor(unittest.TestCase):

    def test_parse_line_valid(self):
        line = "Pipeline1 0 0 [some text] 1"
        expected = {
            'pipeline_id': 'Pipeline1',
            'id': '0',
            'encoding': 0,
            'body': 'some text',
            'next_id': '1'
        }
        result, error = parse_line(line)
        self.assertIsNone(error)
        self.assertEqual(result, expected)

    def test_parse_line_missing_brackets(self):
        line = "Pipeline1 0 0 some text 1"
        result, error = parse_line(line)
        self.assertIsNone(result)
        self.assertEqual(error, "Missing opening '[' or closing ']' brackets")

    def test_parse_line_invalid_encoding(self):
        line = "Pipeline1 0 2 [text] 1"
        result, error = parse_line(line)
        self.assertIsNone(result)
        self.assertEqual(error, "Encoding must be 0 or 1, got 2")

    def test_decode_body_encoding_0(self):
        result = decode_body(0, "plain text")
        self.assertEqual(result, "plain text")

    @patch('log_processor.logging.error')
    def test_decode_body_encoding_1_valid(self, mock_error):
        result = decode_body(1, "48656C6C6F")  # "Hello" in hex
        self.assertEqual(result, "Hello")
        mock_error.assert_not_called()

    @patch('log_processor.logging.error')
    def test_decode_body_encoding_1_invalid_hex(self, mock_error):
        result = decode_body(1, "GG")  # Invalid hex
        self.assertIsNone(result)
        mock_error.assert_called_once_with("Invalid hexadecimal string in body: 'GG'")

    @patch('log_processor.logging.error')
    def test_decode_body_encoding_1_non_ascii(self, mock_error):
        result = decode_body(1, "FF")  # Valid hex, but not ASCII
        self.assertIsNone(result)
        mock_error.assert_called_once_with("Body 'FF' cannot be decoded to ASCII")

    @patch('sys.stderr', new_callable=StringIO)
    def test_process_logs_sample_input(self, mock_stderr):
        input_lines = [
            "Pipeline1 0 0 [some text] 1",
            "Pipeline1 1 0 [another text] 2",
            "Pipeline1 2 0 [body] -1",
            "Pipeline2 3 0 [OK] 99",
            "Pipeline2 99 0 [OK] -1",
            "bad line",
            "Pipeline3 4 0 [loop] 5",
            "Pipeline3 5 0 [back] 4"
        ]
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            process_logs(input_lines)
            expected_output = (
                "Pipeline Pipeline1\n"
                "2| body\n"
                "1| another text\n"
                "0| some text\n"
                "Pipeline Pipeline2\n"
                "99| OK\n"
                "3| OK\n"
            )
            self.assertEqual(mock_stdout.getvalue(), expected_output)
            stderr_output = mock_stderr.getvalue()
            self.assertIn("Wrong format on the log at line 6", stderr_output)
            self.assertIn("Cycle detected in pipeline Pipeline3", stderr_output)

if __name__ == "__main__":
    unittest.main()