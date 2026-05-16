#!/usr/bin/env python3
"""
Subdomain Enumerator - Fast, concurrent subdomain discovery tool
"""

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ─── Constants ────────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 3
DEFAULT_THREADS = 20
DEFAULT_RETRIES = 1
VERSION = "2.0.0"

COLORS = {
    "green":  "\033[92m",
    "red":    "\033[91m",
    "yellow": "\033[93m",
    "cyan":   "\033[96m",
    "bold":   "\033[1m",
    "reset":  "\033[0m",
    "dim":    "\033[2m",
}


# ─── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class ScanResult:
    url: str
    status_code: int
    redirect_url: Optional[str] = None

@dataclass
class ScanStats:
    total: int = 0
    found: int = 0
    errors: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    @property
    def rate(self) -> float:
        return self.total / self.elapsed if self.elapsed > 0 else 0


# ─── Helpers ──────────────────────────────────────────────────────────────────

def c(color: str, text: str) -> str:
    """Colorize text if stdout is a TTY."""
    if not sys.stdout.isatty():
        return text
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def make_session(retries: int, timeout: int) -> requests.Session:
    """Build a requests Session with retry logic and connection pooling."""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=50,
        pool_maxsize=100,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": f"SubEnum/{VERSION}"})
    return session


def load_wordlist(path: str) -> list[str]:
    """Load and sanitize a wordlist file."""
    file = Path(path)
    if not file.exists():
        sys.exit(c("red", f"[!] Wordlist not found: {path}"))
    if not file.is_file():
        sys.exit(c("red", f"[!] Wordlist path is not a file: {path}"))

    words = [
        line.strip()
        for line in file.read_text(errors="ignore").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if not words:
        sys.exit(c("red", "[!] Wordlist is empty."))
    return words


def validate_output_path(path: str) -> Path:
    """Ensure the output file's parent directory exists."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    return output


# ─── Core logic ───────────────────────────────────────────────────────────────

def probe(subdomain: str, domain: str, session: requests.Session, timeout: int) -> Optional[ScanResult]:
    """
    Probe a single subdomain over HTTPS then HTTP.
    Returns a ScanResult on success, None otherwise.
    """
    for scheme in ("https", "http"):
        url = f"{scheme}://{subdomain}.{domain}"
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            redirect = resp.url if resp.url != url else None
            return ScanResult(url=url, status_code=resp.status_code, redirect_url=redirect)
        except requests.exceptions.SSLError:
            continue  # try http fallback
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return None
        except requests.exceptions.RequestException:
            return None
    return None


def scan(
    domain: str,
    wordlist: list[str],
    output: Path,
    threads: int,
    timeout: int,
    retries: int,
    verbose: bool,
) -> ScanStats:
    """Run the concurrent subdomain scan and write results."""
    stats = ScanStats(total=0)
    session = make_session(retries=retries, timeout=timeout)
    total = len(wordlist)

    print(
        c("bold", f"\n  Target   : ") + c("cyan", domain) + "\n" +
        c("bold", f"  Wordlist : ") + f"{total:,} entries\n" +
        c("bold", f"  Output   : ") + str(output) + "\n" +
        c("bold", f"  Threads  : ") + str(threads) + "\n" +
        c("bold", f"  Timeout  : ") + f"{timeout}s\n"
    )

    with open(output, "w") as out_file:
        out_file.write(f"# Subdomain scan — {domain} — {datetime.now()}\n\n")

        with ThreadPoolExecutor(max_workers=threads) as executor:
            future_to_sub = {
                executor.submit(probe, sub, domain, session, timeout): sub
                for sub in wordlist
            }

            for future in as_completed(future_to_sub):
                stats.total += 1
                subdomain = future_to_sub[future]
                progress = f"[{stats.total:>{len(str(total))}}/{total}]"

                try:
                    result = future.result()
                except Exception as exc:
                    stats.errors += 1
                    if verbose:
                        print(c("dim", f"  {progress} {subdomain}.{domain} — exception: {exc}"))
                    continue

                if result:
                    stats.found += 1
                    redirect_info = (
                        c("dim", f" → {result.redirect_url}") if result.redirect_url else ""
                    )
                    print(
                        c("green", f"  {progress} FOUND") +
                        f"  {c('bold', result.url)}" +
                        f"  [{c('yellow', str(result.status_code))}]" +
                        redirect_info
                    )
                    line = f"{result.url}  [{result.status_code}]"
                    if result.redirect_url:
                        line += f"  -> {result.redirect_url}"
                    out_file.write(line + "\n")
                    out_file.flush()
                elif verbose:
                    print(c("dim", f"  {progress} miss    {subdomain}.{domain}"))

    return stats


# ─── Entry point ──────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="subdomain_enum",
        description="Fast, concurrent subdomain enumerator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Example:\n  python3 subdomain_enum.py --domain example.com --wordlist subs.txt --output found.txt",
    )
    parser.add_argument("--domain",   required=True,              help="Target domain (e.g. example.com)")
    parser.add_argument("--wordlist", required=True,              help="Path to wordlist file")
    parser.add_argument("--output",   required=True,              help="Output file for found subdomains")
    parser.add_argument("--threads",  type=int, default=DEFAULT_THREADS,  help=f"Concurrent threads (default: {DEFAULT_THREADS})")
    parser.add_argument("--timeout",  type=int, default=DEFAULT_TIMEOUT,  help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--retries",  type=int, default=DEFAULT_RETRIES,  help=f"Retry attempts on server errors (default: {DEFAULT_RETRIES})")
    parser.add_argument("--verbose",  action="store_true",        help="Show misses and extra debug info")
    parser.add_argument("--version",  action="version", version=f"%(prog)s {VERSION}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    wordlist = load_wordlist(args.wordlist)
    output   = validate_output_path(args.output)

    print(c("bold", c("cyan", f"\n  ══ SubEnum {VERSION} ══")))

    try:
        stats = scan(
            domain=args.domain,
            wordlist=wordlist,
            output=output,
            threads=args.threads,
            timeout=args.timeout,
            retries=args.retries,
            verbose=args.verbose,
        )
    except KeyboardInterrupt:
        print(c("yellow", "\n\n  [!] Interrupted by user."))
        sys.exit(0)

    # ── Summary ──
    print(
        c("bold", f"\n  ── Summary ──────────────────────────────\n") +
        f"  Probed   : {stats.total:,} subdomains\n" +
        c("green", f"  Found    : {stats.found:,}\n") +
        c("red",   f"  Errors   : {stats.errors:,}\n") +
        f"  Elapsed  : {stats.elapsed:.1f}s  ({stats.rate:.1f} req/s)\n" +
        f"  Output   : {output}\n" +
        c("bold", f"  ─────────────────────────────────────────\n")
    )


if __name__ == "__main__":
    main()
