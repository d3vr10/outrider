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
    "-e",
    "--env-file",
    multiple=True,
    type=click.Path(exists=True),
    help="Load environment variables from file (can be used multiple times)",
)
@click.option(
    "--skip-host-verification",
    is_flag=True,
    help="Skip SSH host key verification (insecure, only for testing)",
)
@click.option(
    "--max-concurrent-uploads",
    type=int,
    default=2,
    show_default=True,
    help="Maximum number of concurrent uploads (1-10)",
)
@click.option(
    "--skip-cache",
    is_flag=True,
    help="Skip SHA256 cache validation and re-compress images",
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help="Clear cache before deployment",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Force re-upload even if file already exists on target (bypass resume checks)",
)
@click.pass_context
def deploy(ctx, config: str, verbose: bool, env_file: tuple, skip_host_verification: bool,
           max_concurrent_uploads: int, skip_cache: bool, clear_cache: bool, no_cache: bool):
    """Deploy OCI images to remote systems

    Examples:
        outrider deploy -c config.yaml
        outrider deploy -c config.yaml -e .env.prod -e .env.secrets
        outrider deploy -c config.yaml --max-concurrent-uploads 4
    """
    if verbose or ctx.obj.get("debug"):
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate and clamp max_concurrent_uploads
    max_concurrent_uploads = max(1, min(10, max_concurrent_uploads))

    try:
        # Convert tuple to list for Config
        env_files = list(env_file) if env_file else None

        cfg = Config(config, env_files=env_files)
        orchestrator = Orchestrator(
            cfg,
            skip_host_verification=skip_host_verification,
            max_concurrent_uploads=max_concurrent_uploads,
            skip_cache=skip_cache,
            clear_cache=clear_cache,
            no_cache=no_cache
        )

        if skip_host_verification:
            click.echo("⚠️  WARNING: SSH host key verification is disabled!")

        if skip_cache:
            click.echo("⚠️  Cache validation skipped - will re-compress images")

        if no_cache:
            click.echo("⚠️  Remote cache disabled - will force re-upload even if file exists")

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
@click.option(
    "-e",
    "--env-file",
    multiple=True,
    type=click.Path(exists=True),
    help="Load environment variables from file (can be used multiple times)",
)
def validate(config: str, env_file: tuple):
    """Validate configuration file

    Examples:
        outrider validate -c config.yaml
        outrider validate -c config.yaml -e .env.prod
    """
    try:
        # Convert tuple to list for Config
        env_files = list(env_file) if env_file else None

        cfg = Config(config, env_files=env_files)

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


@cli.command()
@click.option(
    "--clear-all",
    is_flag=True,
    help="Clear entire cache",
)
def cache(clear_all: bool):
    """Manage SHA256 tar file cache

    Examples:
        outrider cache --show-stats
        outrider cache --clear-all
    """
    from outrider.core.cache import CacheManager

    try:
        cache_mgr = CacheManager()

        if clear_all:
            cache_mgr.clear()
            click.echo("✓ Cache cleared")
        else:
            stats = cache_mgr.get_stats()
            click.echo("Cache Statistics:")
            click.echo(f"  Directory: {stats['cache_dir']}")
            click.echo(f"  Entries: {stats['num_entries']}")
            click.echo(f"  Total size: {stats['total_size_mb']} MB")

            if stats['entries']:
                click.echo("\n  Cached files:")
                for entry in stats['entries'].values():
                    click.echo(f"    - {entry['file_path']} ({entry['file_size'] // 1024 // 1024} MB)")

        sys.exit(0)

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--cleanup-old",
    is_flag=True,
    help="Remove resume files older than 7 days",
)
def resume(cleanup_old: bool):
    """Manage resumable transfer progress

    Examples:
        outrider resume --show-stats
        outrider resume --cleanup-old
    """
    from outrider.transport.resume import ResumeManager

    try:
        resume_mgr = ResumeManager()

        if cleanup_old:
            resume_mgr.cleanup()
            click.echo("✓ Old resume files cleaned up")
        else:
            stats = resume_mgr.get_stats()
            click.echo("Resume Statistics:")
            click.echo(f"  Directory: {stats['resume_dir']}")
            click.echo(f"  Pending transfers: {stats['pending_transfers']}")

            if stats['files']:
                click.echo("\n  Pending transfers:")
                for filename in stats['files']:
                    click.echo(f"    - {filename}")

        sys.exit(0)

    except Exception as e:
        click.echo(f"✗ Error: {e}")
        sys.exit(1)


def main():
    """Entry point for CLI"""
    cli()


if __name__ == "__main__":
    main()
