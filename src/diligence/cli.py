"""Command-line entry point for the diligence pipeline."""

import argparse

from diligence import __version__


def main() -> None:
    import sys

    parser = argparse.ArgumentParser(prog="diligence")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("generate", help="Generate the synthetic data rooms")
    sub.add_parser("extract", help="Extract a data room into the fact table",
                   add_help=False)
    sub.add_parser("report", help="Generate a Red Flag Report",
                   add_help=False)
    sub.add_parser("review", help="Review quarantined low-confidence facts",
                   add_help=False)
    args, _rest = parser.parse_known_args()

    # Sub-commands own their remaining argv
    sys.argv = [f"diligence {args.command}"] + _rest

    if args.command == "generate":
        from diligence.dataroom.build import main as generate_main

        generate_main()
    elif args.command == "extract":
        from diligence.extraction.pipeline import main as extract_main

        extract_main()
    elif args.command == "report":
        from diligence.report.generate import main as report_main

        report_main()
    elif args.command == "review":
        from diligence.review.flow import main as review_main

        review_main()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
