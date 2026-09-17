"""Capture startup/import errors even in PyInstaller's no-console executable."""
from pathlib import Path
import sys
import traceback


def main():
    smoke = "--smoke-test" in sys.argv
    log = None
    if smoke:
        index = sys.argv.index("--smoke-log") if "--smoke-log" in sys.argv else -1
        log = Path(sys.argv[index + 1]) if index >= 0 else Path(sys.executable).with_name("smoke-test.log")
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("START: packaged Python entry point\n", encoding="utf-8")
    try:
        import reader
        reader.main()
    except BaseException:
        if log:
            with log.open("a", encoding="utf-8") as stream:
                stream.write("FAIL\n" + traceback.format_exc())
            return 1
        raise
    if log:
        with log.open("a", encoding="utf-8") as stream:
            stream.write("PASS\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
