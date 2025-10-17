"""Module entry-point to run the ProofOrigin development server."""
from __future__ import annotations

from . import create_app


def main() -> None:
    app = create_app()
    app.run(debug=True)


if __name__ == "__main__":
    main()
