"""Submit ZTF forced-photometry requests."""

from src.submit_ztf import main, parse_position


__all__ = ["main", "parse_position"]


if __name__ == "__main__":
    main()
