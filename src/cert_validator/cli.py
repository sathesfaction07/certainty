import json
import logging
from pathlib import Path

import click

from .backends import ConsensusBackend, get_backend
from .core.pipeline import export_csv, validate_batch, validate_certificate
from .core.rules import list_categories

logging.basicConfig(
    level="INFO",
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(module)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)


@click.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--category", default=None, help="Product category. Omit to auto-detect.")
@click.option(
    "--backend",
    "backend_name",
    default="claude",
    type=click.Choice(["claude", "textract", "google"]),
    help="Processing backend",
)
@click.option(
    "--consensus",
    default=None,
    help="Use consensus of two backends (e.g., 'claude,textract'). Overrides --backend.",
)
@click.option("--region", default="us-east-1", help="AWS region (for claude/textract backends)")
@click.option(
    "--output", "output_path", default=None, type=click.Path(), help="Output file (.json or .csv)"
)
@click.option(
    "--list-categories", "show_categories", is_flag=True, help="List available categories and exit"
)
@click.option("--verbose", is_flag=True)
def main(path, category, backend_name, region, output_path, show_categories, verbose, consensus):
    if verbose:
        logging.getLogger("cert_validator").setLevel("DEBUG")

    if show_categories:
        for cat in list_categories():
            click.echo(f"  {cat}")
        return

    if consensus:
        parts = consensus.split(",")
        if len(parts) != 2:
            click.echo("Error: --consensus requires exactly two backends (e.g., 'claude,textract')")
            return
        primary = get_backend(parts[0].strip(), region=region)
        secondary = get_backend(parts[1].strip(), region=region)
        backend = ConsensusBackend(primary, secondary)
        click.echo(f"Using consensus: {parts[0]} + {parts[1]}")
    else:
        backend = get_backend(backend_name, region=region)
    input_path = Path(path)

    if input_path.is_dir():
        results = validate_batch(input_path, category, backend=backend)
    else:
        results = [validate_certificate(input_path, category, backend=backend)]

    if output_path:
        out = Path(output_path)
        if out.suffix == ".csv":
            export_csv(results, out)
        else:
            with open(out, "w") as f:
                json.dump(results, f, indent=2)
        click.echo(f"Results written to {output_path}")
    else:
        for result in results:
            _print_result(result)


def _print_result(result: dict) -> None:
    if "error" in result and "valid" not in result:
        click.secho(f"\nERROR: {result['error']}", fg="red")
        return

    file_name = result.get("file", "unknown")
    status = "PASS" if result.get("valid") else "FAIL"
    color = "green" if result.get("valid") else "red"

    matched = result.get("matched", 0)
    required = result.get("required", 0)
    click.secho(f"\n[{file_name}] {status}: {matched}/{required} standards found", fg=color)

    if result.get("category_auto_detected"):
        click.echo(f"  Category (auto-detected): {result.get('category')}")
    if result.get("lab_name"):
        click.echo(f"  Lab: {result['lab_name']}")
    if result.get("date"):
        click.echo(f"  Date: {result['date']}")
    if result.get("missing"):
        click.echo(f"  Missing: {', '.join(result['missing'])}")
    if result.get("matched_details"):
        for m in result["matched_details"]:
            click.echo(f'  Found: {m["standard"]} → "{m["found_as"]}" ({m["confidence"]})')
    if result.get("error"):
        click.secho(f"  Error: {result['error']}", fg="yellow")


if __name__ == "__main__":
    main()
