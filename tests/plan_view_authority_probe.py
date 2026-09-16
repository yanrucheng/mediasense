"""Hash all retained Dataset files/tables; optionally isolate existing open bookkeeping."""

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3


def digest(workspace, normalize_open_time=False):
    workspace = workspace.resolve()
    result = {}

    def hash_value(value):
        data = json.dumps(
            value, sort_keys=True, default=lambda b: {"bytes": b.hex()}
        ).encode()
        return hashlib.sha256(data).hexdigest()

    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.name.endswith(("-wal", "-shm", "-journal")):
            continue
        name = str(path.relative_to(workspace))
        if path.suffix != ".sqlite3":
            result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            continue
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
            result[name + ":schema"] = hash_value(
                db.execute(
                    "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
                ).fetchall()
            )
            for (table,) in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ):
                quoted = '"' + table.replace('"', '""') + '"'
                query = db.execute("SELECT * FROM " + quoted)
                columns = [c[0] for c in query.description]
                rows = [list(r) for r in query]
                if (
                    normalize_open_time
                    and name == "precheck/work.sqlite3"
                    and table == "datasets"
                ):
                    index = columns.index("updated_at")
                    for row in rows:
                        row[index] = "<existing Dataset open bookkeeping>"
                result[name + ":" + table] = hash_value(
                    [columns, sorted(rows, key=repr)]
                )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--normalize-open-time", action="store_true")
    args = parser.parse_args()
    print(json.dumps(digest(args.workspace, args.normalize_open_time), sort_keys=True))
