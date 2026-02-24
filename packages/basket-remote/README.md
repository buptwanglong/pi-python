# pi-remote

Expose a command in a web terminal on a given address and port. Used by **pi-assistant** for `pi --remote` so you can use the assistant from a phone or another machine over ZeroTier or LAN.

## How it works

- **pi-remote** provides a small Python API that runs [ttyd](https://github.com/tsl0922/ttyd) as a subprocess. ttyd gives you a browser-based terminal; each connection runs the command you pass (e.g. `pi --tui`).
- You do **not** run pi-remote directly. Install it as an optional dependency of pi-assistant and use `pi --remote` from the assistant.

## Requirements

- **ttyd** must be installed on the system (not a Python dependency).

  Install:

  - **macOS:** `brew install ttyd`
  - **Linux:** see [ttyd installation](https://github.com/tsl0922/ttyd#installation) (e.g. package manager or build from source)
  - **Windows:** `choco install ttyd` or download from [GitHub releases](https://github.com/tsl0922/ttyd/releases)

## ZeroTier usage

1. Install [ZeroTier](https://www.zerotier.com/) on your computer and on your phone (or other device). Create a network at my.zerotier.com and join both devices.
2. On the computer, get your ZeroTier IP (e.g. `zerotier-cli listnetworks` or the ZeroTier UI).
3. Install pi-remote and ttyd, then run the coding agent in remote mode, binding to that IP:

   ```bash
   cd packages/pi-assistant
   poetry add pi-remote
   poetry run pi --remote --bind <your.ZeroTier.IP> --port 7681
   ```

4. On your phone (on the same ZeroTier network), open a browser and go to `http://<your.ZeroTier.IP>:7681`. You get a web terminal running `pi --tui`.

Binding to the ZeroTier IP (instead of `0.0.0.0`) limits the server to the virtual network. For LAN-only use, you can use `--bind 0.0.0.0` and connect via your machine’s LAN IP.

## API

- **`run_serve(bind="0.0.0.0", port=7681, command=None)`**  
  Runs ttyd with the given bind address, port, and command. Blocks until ttyd exits. Raises `RuntimeError` if ttyd is not found.  
  `command` must be a list of strings (e.g. `[sys.executable, "-m", "pi_assistant.main", "--tui"]`). Callers (like pi-assistant) are responsible for passing the desired command.

## License

MIT
