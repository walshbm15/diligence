"""Command-line entry point for the diligence pipeline."""

import argparse

from diligence import __version__


def main() -> None:
    parser = argparse.ArgumentParser(prog="diligence")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("generate", help="Generate a synthetic data room")
    args = parser.parse_args()

    if args.command == "generate":
        from diligence.dataroom.build import main as generate_main

        generate_main()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
