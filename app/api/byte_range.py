"""HTTP Range header parsing (RFC 9110 §14) for single byte ranges, which is what media players send."""


class RangeNotSatisfiableError(Exception):
    pass


def parse_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Return the inclusive (start, end) byte range to send, or None to send the whole file.

    Headers this server does not handle (other units, several ranges, malformed values) are
    ignored, as RFC 9110 allows; a well-formed range entirely outside the file is an error.
    """
    if not header:
        return None
    unit, _, spec = header.partition("=")
    if unit.strip().lower() != "bytes" or "," in spec:
        return None
    first, dash, last = spec.strip().partition("-")
    if not dash or not (first.isdigit() or first == "") or not (last.isdigit() or last == ""):
        return None

    if first == "":
        # Suffix range: the last N bytes.
        if last == "" or int(last) == 0 or size == 0:
            raise RangeNotSatisfiableError(header)
        return max(0, size - int(last)), size - 1

    start = int(first)
    if last and int(last) < start:
        return None
    if start >= size:
        raise RangeNotSatisfiableError(header)
    end = int(last) if last else size - 1
    return start, min(end, size - 1)
