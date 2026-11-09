"""Read or convert downloaded ZTF light curves."""

from src.lightcurve import main, read_ztf_header, read_ztf_lightcurve


__all__ = ["main", "read_ztf_header", "read_ztf_lightcurve"]


if __name__ == "__main__":
    raise SystemExit(main())
