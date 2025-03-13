# Log Message Processor

This Python script processes log messages from multiple pipelines, reconstructing their sequences in reverse order based on `id` and `next_id`. Keep in mind that due to an issue in the original implementation, the order of log messages is randomized. The goal is to parse and process these logs to reconstruct meaningful information.

Assuming each log message is given in a new line, following the format:

```bash
pipeline_id id encoding [body] next_id
```

**Where**:

-   **pipeline_id**: The id of the pipeline that this message originates from.
-   **id**: The id of this message, unique within a pipeline.
-   **encoding**: An integer to show the encoding of the body. 0 is used for ASCII encoded body, e.g., "text". 1 is used for body encoded in hexadecimal, e.g., "74657874".
-   **body**: The actual message.
-   **next_id**: The id of the next message for this pipeline. A value of -1 is used to mark that no next message exists.

**Constraints**

-   Messages originating from the same pipeline have the same pipeline_id.
-   The messages within a pipeline, identified by id, are unique.

## Example Usage

**Default Log File**:

```bash
python3 src/log_processor.py < input.txt
```

-   Errors go to a file like error_log_YYYYMMDD_HHMMSS.txt

**Custom Log File**:

```bash
python3 src/log_processor.py --log-file my_errors.txt < input.txt
```

## Sample Input and Output

**Input**:

```bash
Pipeline1 0 0 [some text] 1
Pipeline1 1 0 [another text] 2
Pipeline1 2 0 [body] -1
Pipeline2 3 0 [OK] 99
Pipeline2 99 0 [OK] -1
bad line
Pipeline3 4 0 [loop] 5
Pipeline3 5 0 [back] 4
```

**Console Output**:

```bash
Pipeline Pipeline1
2| body
1| another text
0| some text
Pipeline Pipeline2
99| OK
3| OK
Error: Wrong format on the log at line 6: Expected 3 fields before '[body]', got 1 - 'bad line'
Error: Cycle detected in pipeline Pipeline3 involving id 4
```

**Log File (error_log_20250313_143045.txt)**:

```bash
2025-03-13 14:30:45 - ERROR - Wrong format on the log at line 6: Expected 3 fields before '[body]', got 1 - 'bad line'
2025-03-13 14:30:45 - ERROR - Cycle detected in pipeline Pipeline3 involving id 4
```

**Testing**

Run the test suite to verify functionality:

```bash
python3 -m unittest tests/test_log_processor.py
```
