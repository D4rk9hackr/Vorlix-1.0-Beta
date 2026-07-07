"""Native messaging host for Vorlix Web Bridge extension."""
import json
import struct
import sys


def read_message() -> dict | None:
    raw = sys.stdin.buffer.read(4)
    if len(raw) < 4:
        return None
    length = struct.unpack("@I", raw)[0]
    return json.loads(sys.stdin.buffer.read(length))


def write_message(msg: dict) -> None:
    data = json.dumps(msg).encode()
    sys.stdout.buffer.write(struct.pack("@I", len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def main():
    while True:
        msg = read_message()
        if msg is None:
            break
        # Future: bridge to Orchestrator.dispatch()
        write_message({"status": "received", "type": msg.get("type")})


if __name__ == "__main__":
    main()
