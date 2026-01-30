"""CLI interface for outrider"""

import logging
import sys
import warnings

import click

from outrider.core.config import Config
from outrider.core.orchestrator import Orchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@click.group()
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode with verbose output and warnings",
)
@click.version_option()
@click.pass_context
def cli(ctx, debug):
    """Outrider - OCI Image Transfer Tool

    Automate pulling OCI images and deploying them to air-gapped or remote systems.
    """
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug

    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        # Suppress deprecation warnings in production mode
        warnings.filterwarnings("ignore", category=DeprecationWarning)


@cli.command()
@click.option(
    "-c",
    "--config",
    required=True,
    type=click.Path(exists=True),
    help="Path to configuration YAML file",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Enable verbose logging",
)
@click.option(
    "--skip-host-verification",
    is_flag=True,
    help="Skip SSH host key verification (insecure, only for testing)",
)
@click.option(
    "--max-concurrent-uploads",
    type=int,
    default=3,
    show_default=True,
    help="Maximum number of concurrent uploads (1-10)",
)
@click.pass_context
def deploy(ctx, config: str, verbose: bool, skip_host_verification: bool,
           max_concurrent_uploads: int):
    """Deploy OCI images to remote systems

    Example:
        outrider deploy -c config.yaml
    """
    if verbose or ctx.obj.get("debug"):
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate and clamp max_concurrent_uploads
    max_concurrent_uploads = max(1, min(10, max_concurrent_uploads))

    try:
        cfg = Config(config)
        orchestrator = Orchestrator(cfg, skip_host_verification=skip_host_verification,
                                   max_concurrent_uploads=max_concurrent_uploads)

        if skip_host_verification:
            click.echo("⚠️  WARNING: SSH host key verification is disabled!")

        if orchestrator.run():
            click.echo("\n✓ Deployment completed successfully")
            sys.exit(0)
        else:
            click.echo("\n✗ Deployment failed")
            sys.exit(1)

    except Exception as e:
        click.echo(f"\n✗ Error: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option(
    "-c",
    "--config",
    required=True,
    type=click.Path(exists=True),
    help="Path to configuration YAML file",
)
def validate(config: str):
    """Validate configuration file

    Example:
        outrider validate -c config.yaml
    """
    try:
        cfg = Config(config)

        if not cfg.validate():
            click.echo("✗ Configuration validation failed")
            sys.exit(1)

        click.echo("✓ Configuration is valid")
        click.echo(f"  Images: {len(cfg.images)}")
        click.echo(f"  Targets: {len(cfg.targets)}")

        if cfg.post_instructions:
            plugin = cfg.post_instructions.get("plugin", "unknown")
            click.echo(f"  Post-instruction plugin: {plugin}")

        sys.exit(0)

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        sys.exit(1)


def main():
    """Entry point for CLI"""
    cli()


if __name__ == "__main__":
    main()
