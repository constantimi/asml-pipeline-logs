import sys
import argparse
import logging
from datetime import datetime

def setup_logging(log_file: str) -> None:
    """Configure logging to write to a specified file with timestamps."""
    logging.basicConfig(
        filename=log_file,
        level=logging.WARNING,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def parse_line(line: str) -> tuple[dict | None, str | None]:
    """
    Parse a log line into a dictionary or return (None, reason) if invalid.
    Returns (dict, None) if valid, or (None, "specific reason") if invalid.
    """
    line = line.strip()
    if not line:
        return (None, "Line is empty or only whitespace")

    first_bracket = line.find('[')
    last_bracket = line.rfind(']')
    if first_bracket == -1 or last_bracket == -1:
        return (None, "Missing opening '[' or closing ']' brackets")
    if first_bracket >= last_bracket:
        return (None, "Opening '[' appears after closing ']'")

    body = line[first_bracket + 1:last_bracket].strip()
    before = line[:first_bracket].strip().split()
    after = line[last_bracket + 1:].strip().split()

    if len(before) != 3:
        return (None, f"Expected 3 fields before '[body]', got {len(before)}")
    if len(after) != 1:
        return (None, f"Expected 1 field after '[body]', got {len(after)}")

    pipeline_id, id_, encoding_str = before
    next_id = after[0]

    try:
        encoding = int(encoding_str)
        if encoding not in (0, 1):
            return (None, f"Encoding must be 0 or 1, got {encoding}")
    except ValueError:
        return (None, f"Encoding '{encoding_str}' is not a valid integer")

    if encoding == 1:
        try:
            bytes.fromhex(body)
        except ValueError:
            return (None, f"Body '{body}' is not valid hexadecimal for encoding 1")

    return ({
        'pipeline_id': pipeline_id,
        'id': id_,
        'encoding': encoding,
        'body': body,
        'next_id': next_id
    }, None)

def decode_body(encoding: int, body: str) -> str | None:
    """Decode the message body based on encoding, handling errors gracefully."""
    if encoding == 0:
        return body
    elif encoding == 1:
        try:
            print(f"Attempting to decode hex: '{body}'")
            byte_data = bytes.fromhex(body)
            print(f"Hex decoded: {byte_data}")
            decoded = byte_data.decode('ascii')
            print(f"Decoded to ASCII: '{decoded}'")
            return decoded
        except UnicodeDecodeError as e:
            print(f"UnicodeDecodeError caught: {e}")
            logging.error(f"Body '{body}' cannot be decoded to ASCII")
            return None
        except ValueError as e:
            print(f"ValueError caught: {e}")
            logging.error(f"Invalid hexadecimal string in body: '{body}'")
            return None
        except Exception as e:
            print(f"Unexpected error caught: {type(e).__name__}: {e}")
            logging.error(f"Unexpected error decoding body '{body}': {e}")
            return None
    return None

def process_logs(input_lines: list[str]) -> None:
    """Process log lines, log errors to file, and print valid sequences to stdout."""
    messages_by_pipeline = {}
    line_number = 0

    for line in input_lines:
        line_number += 1
        msg, error_reason = parse_line(line)
        if msg is None:
            error_msg = f"Wrong format on the log at line {line_number}: {error_reason} - '{line.strip()}'"
            logging.error(error_msg)
            sys.stderr.write(f"Error: {error_msg}\n")
            continue
        pipeline_id = msg['pipeline_id']
        if pipeline_id not in messages_by_pipeline:
            messages_by_pipeline[pipeline_id] = {}
        if msg['id'] in messages_by_pipeline[pipeline_id]:
            error_msg = f"Duplicate message id {msg['id']} in pipeline {pipeline_id} at line {line_number} - '{line.strip()}'"
            logging.error(error_msg)
            sys.stderr.write(f"Error: {error_msg}\n")
            continue
        messages_by_pipeline[pipeline_id][msg['id']] = msg

    for pipeline_id, pipeline_msgs in messages_by_pipeline.items():
        last_msgs = [msg for msg in pipeline_msgs.values() if msg['next_id'] == '-1']
        
        if len(last_msgs) == 0:
            sequence = []
            visited_ids = set()
            start_msg = next(iter(pipeline_msgs.values()))
            current_id = start_msg['id']
            sequence.append((start_msg['id'], start_msg['encoding'], start_msg['body']))
            visited_ids.add(current_id)

            while True:
                next_msgs = [msg for msg in pipeline_msgs.values() if msg['id'] == current_id]
                if not next_msgs:
                    break
                next_msg = next_msgs[0]
                if next_msg['next_id'] not in pipeline_msgs:
                    break
                if next_msg['next_id'] in visited_ids:
                    error_msg = f"Cycle detected in pipeline {pipeline_id} involving id {next_msg['next_id']}"
                    logging.error(error_msg)
                    sys.stderr.write(f"Error: {error_msg}\n")
                    sequence = []
                    break
                sequence.append((next_msg['next_id'], next_msg['encoding'], next_msg['body']))
                visited_ids.add(next_msg['next_id'])
                current_id = next_msg['next_id']

            if not sequence:
                continue
            last_msg = start_msg
        elif len(last_msgs) > 1:
            error_msg = f"Pipeline {pipeline_id} has multiple last messages: {[msg['id'] for msg in last_msgs]}"
            logging.error(error_msg)
            sys.stderr.write(f"Error: {error_msg}\n")
            continue
        else:
            last_msg = last_msgs[0]
            sequence = [(last_msg['id'], last_msg['encoding'], last_msg['body'])]
            visited_ids = {last_msg['id']}
            current_id = last_msg['id']

            while True:
                prev_msgs = [msg for msg in pipeline_msgs.values() if msg['next_id'] == current_id]
                if not prev_msgs:
                    break
                if len(prev_msgs) > 1:
                    error_msg = f"Branching detected in pipeline {pipeline_id} for next_id {current_id}. Messages pointing to it: {[msg['id'] for msg in prev_msgs]}"
                    logging.error(error_msg)
                    sys.stderr.write(f"Error: {error_msg}\n")
                    sequence = []
                    break
                prev_msg = prev_msgs[0]
                if prev_msg['id'] in visited_ids:
                    error_msg = f"Cycle detected in pipeline {pipeline_id} involving id {prev_msg['id']}"
                    logging.error(error_msg)
                    sys.stderr.write(f"Error: {error_msg}\n")
                    sequence = []
                    break
                sequence.append((prev_msg['id'], prev_msg['encoding'], prev_msg['body']))
                visited_ids.add(prev_msg['id'])
                current_id = prev_msg['id']

        if sequence:
            sequence_ids = {id_ for id_, _, _ in sequence}
            all_ids = set(pipeline_msgs.keys())
            orphan_ids = all_ids - sequence_ids
            if orphan_ids:
                warning_msg = f"Orphan messages in pipeline {pipeline_id}: {orphan_ids}"
                logging.warning(warning_msg)
                sys.stderr.write(f"Warning: {warning_msg}\n")
            print(f"Pipeline {pipeline_id}")
            for id_, encoding, body in sequence:
                decoded_body = decode_body(encoding, body)
                if decoded_body is not None:
                    print(f"{id_}| {decoded_body}")

def main():
    """Handle command-line arguments, set up logging, and process logs."""
    parser = argparse.ArgumentParser(description="Process pipeline logs from file or stdin.")
    parser.add_argument(
        'input_file',
        nargs='?',
        help="Input file to process. If omitted, reads from standard input (stdin)."
    )
    parser.add_argument(
        '--log-file',
        default=f'error_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt',
        help="File to store error logs (default: error_log_YYYYMMDD_HHMMSS.txt)"
    )
    args = parser.parse_args()

    setup_logging(args.log_file)

    if args.input_file:
        try:
            with open(args.input_file, 'r') as f:
                input_lines = f.readlines()
        except FileNotFoundError:
            error_msg = f"File '{args.input_file}' not found."
            logging.error(error_msg)
            sys.stderr.write(f"Error: {error_msg}\n")
            sys.exit(1)
        except IOError:
            error_msg = f"Could not read file '{args.input_file}'."
            logging.error(error_msg)
            sys.stderr.write(f"Error: {error_msg}\n")
            sys.exit(1)
    else:
        input_lines = sys.stdin.readlines()

    process_logs(input_lines)

if __name__ == "__main__":
    main()