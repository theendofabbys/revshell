# revshell-generator

Interactive reverse shell generator. Starts a [bore](https://github.com/ekzhang/bore)
tunnel to expose a local port, then prints a ready-to-paste payload for the target.

## Requirements

- Python 3.7+
- `bore` in PATH (`cargo install bore-cli`)
- `nc` / `ncat` / `python3 -m http.server` for the listener

## Usage

```bash
python3 main.py


    Enter the local port to expose.

    Pick a template from the menu.

    Copy the listener command into another terminal.

    Paste the payload on the target.

Non-interactive

python3 main.py -l 1337 -s bash_tcp
python3 main.py --list

Flags:
-l, --local-port INT    local port to expose through bore
-b, --bore-server STR   bore server (default: bore.pub)
-p, --bore-port INT     requested remote port
-s, --select NAME       template name, skips the menu
--list                  list templates and exit



