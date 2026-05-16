# 🔍 SubEnum

A very simple script to enumerate subdomains of a domain, and write them into a file.

## Features

- **Multithreaded** — up to N concurrent probes (default: 20 threads)
- **HTTPS → HTTP fallback** — retries over HTTP on SSL errors
- **Retry logic** — automatic retry on server-side errors (5xx) with backoff
- **Live output** — results written to file immediately as they're found
- **Colored terminal output** — suppressed automatically when piped to a file
- **Scan summary** — found count, error count, elapsed time, and req/s rate

## Requirements

```
pip install requests
```

Python 3.10+ required (uses `list[str]` type hints).

## Usage

```bash
python3 subdomain_enum.py --domain <domain> --wordlist <wordlist> --output <output_file> [options]
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `--domain` | ✅ | Target domain (e.g. `example.com`) |
| `--wordlist` | ✅ | Path to wordlist file |
| `--output` | ✅ | Output file for found subdomains |
| `--threads` | ➖ | Number of concurrent threads (default: `20`) |
| `--timeout` | ➖ | Request timeout in seconds (default: `3`) |
| `--retries` | ➖ | Retry attempts on server errors (default: `1`) |
| `--verbose` | ➖ | Also print missed subdomains |
| `--version` | ➖ | Show version and exit |

### Examples

Basic scan:
```bash
python3 subdomain_enum.py --domain google.fr --wordlist wordlist.txt --output found.txt
```

Faster scan with more threads:
```bash
python3 subdomain_enum.py --domain google.fr --wordlist wordlist.txt --output found.txt --threads 50
```

Verbose mode (show misses too):
```bash
python3 subdomain_enum.py --domain google.fr --wordlist wordlist.txt --output found.txt --verbose
```

## Output

Found subdomains are written to the specified output file in real time:

```
# Subdomain scan — google.fr — 2025-05-16 14:32:01

https://mail.google.fr  [200]
https://api.google.fr   [301]  -> https://developers.google.fr/
```

## Wordlists

Any DNS/subdomain wordlist works. A few good sources:

- [SecLists](https://github.com/danielmiessler/SecLists/tree/master/Discovery/DNS) — `subdomains-top1million-5000.txt` is a solid starting point
- [assetnote wordlists](https://wordlists.assetnote.io/)

## Disclaimer

This tool is intended for **authorized security testing only**. Do not use it against targets you don't have explicit permission to test.
