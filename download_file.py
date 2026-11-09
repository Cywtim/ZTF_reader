"""Download finished ZTF light curves."""

from src.download_file import download_product, finished_products, job_rows, main, pending_snapshots


__all__ = ["download_product", "finished_products", "job_rows", "main", "pending_snapshots"]


if __name__ == "__main__":
    main()
