# HackTerm

![Game](https://imgur.com/a/j3kEPdw)

A Hacknet-style terminal hacking game built with Python and pygame.

```
HackTerm v0.1  —  Network Infiltration Terminal
────────────────────────────────────────────────────
[SYS]  System boot complete.
[SYS]  2 nodes online: home, mail.

[INFO] Connect to mail for contracts and exploit market.
[INFO] Type 'help' for commands.
$
```

## Overview

You are a freelance hacker operating through a command-line terminal. Accept contracts from your mail server, infiltrate target networks, exploit vulnerabilities, and earn eurodollars. Watch out — corporate servers from the five megacorps actively trace intrusions and will seize your funds if you're too slow.

## Installation

Requires [uv](https://github.com/astral-sh/uv).

```bash
git clone <repo>
cd game_course_3
uv sync
uv run python main.py
```

## Gameplay

### Getting started

1. Click **mail** on the node map or type `connect 192.168.0.1`
2. Run `tasks` to receive a hack contract — a red target node appears on the map
3. Navigate to the target: `connect <ip>`
4. Scan it: `probe`
5. Exploit its vulnerabilities (e.g. `ssh_brute 22`)
6. Gain root: `hack`
7. Collect your reward and repeat

### Commands

| Command | Description |
|---|---|
| `help` | Show all commands |
| `connect {ip\|name}` | Connect to a node by IP or hostname |
| `probe` | Scan current node for vulnerabilities |
| `bgp` | Discover neighboring nodes *(requires root)* |
| `ssh_brute {port}` | Bruteforce SSH credentials |
| `ftp_brute {port}` | Bruteforce FTP credentials |
| `smtp_relay {port}` | Exploit open SMTP relay |
| `rdp_brute {port}` | Bruteforce RDP credentials |
| `web_exploit {port}` | SQL injection via web interface |
| `stack_flood {port}` | Stack overflow flood attack |
| `hack` | Escalate to root once all vulns are cracked |
| `tasks` | Receive or view active contract *(mail only)* |
| `market` | Browse the exploit shop *(mail only)* |
| `market buy {cmd}` | Purchase a new exploit tool |

**Navigation:** `PgUp` / `PgDn` — scroll log &nbsp;·&nbsp; `↑` / `↓` — command history

### Exploit progression

You start with only SSH bruteforce. Buy additional tools from the market:

| Tool | Price |
|---|---|
| `ssh_brute` | free |
| `ftp_brute` | €$1,500 |
| `smtp_relay` | €$2,000 |
| `rdp_brute` | €$2,500 |
| `web_exploit` | €$3,500 |
| `stack_flood` | €$4,000 |

### Corporate servers

Five megacorps operate servers hidden throughout task networks:

| Corporation | Colour |
|---|---|
| **Arasaka** | crimson |
| **Militech** | olive |
| **Kang Tao** | teal |
| **Biotechnica** | green |
| **Zetatech** | violet |

Corp servers always have **one more vulnerability** than your current toolkit — you'll need to return after buying the next exploit.

Running `probe` on a corp server triggers a **trace countdown** (28–60 s). Complete the hack before it expires. If the timer runs out:
- All vulnerabilities are patched remotely
- The corporation **seizes your entire balance**

Successfully hacking a corp server earns a bonus bounty of **€$1,000–5,000** — the shorter the trace window, the higher the payout.

### Node map

| Colour | Meaning |
|---|---|
| Cyan | Your home node |
| Amber | Mail server |
| Steel blue | Unknown server |
| Purple | Hacked node |
| Bright red | Task target (IP hidden) |
| Dim red | Unknown IP |
| *Company colour* | Corporate server |

## Project structure

```
src/
├── core/
│   └── game.py          # Main game loop, all commands
├── network/
│   ├── exploits.py      # Exploit definitions and unlock prices
│   ├── generator.py     # Procedural network generation
│   ├── node.py          # Node dataclass
│   ├── connection.py    # Connection dataclass
│   ├── vulnerability.py # Vulnerability dataclass
│   └── task.py          # Task dataclass
├── ui/
│   ├── console.py       # Terminal UI
│   └── node_view.py     # Node map renderer
└── utils/
    └── colors.py        # Colour palette
```

## Tech

- **Python 3.10+**
- **pygame 2.6** — rendering, input
- **uv** — dependency management
