# Philips UART Extractor — Saleae Logic 2 HLA

A High-Level Analyzer (HLA) for Saleae Logic 2 that decodes the `FE FF`-framed
UART protocol used by Philips / MUJI (Versuni) air purifiers — e.g. the MUJI
`AC0650/10`. See [`devices/philips-600-series`](../../devices/philips-600-series)
for the protocol reverse-engineering notes.

> This is a **different protocol** from Levoit — use the
> [`levoit_uart`](../levoit_uart) HLA for Levoit devices.

## Protocol

Frames start with the sync bytes `FE FF`, then a little-endian command, a
single length byte, the data, and a 2-byte checksum:

```
FE FF  <cmd LE16>  <len>  [data...]  <checksum LE16>
```

| `cmd` | Label | Direction | `data` |
|-------|-------|-----------|--------|
| `0x0001` / `0x0002` | HS1 / HS2 | both | handshake / ack at boot |
| `0x0003` | SET | module → MCU | `03 <dpid> 01 <val> 00` — write a datapoint |
| `0x0004` | QUERY | module → MCU | `<group> 00` — read a datapoint group |
| `0x0007` | STATUS | MCU → module | `00 <group> … TLVs …` — status report |

Decoded frames are displayed as:

```
[module->MCU] QUERY(0x0004)  GROUP=02  |  LEN=2  |  DATA=02 00  |  CRC=7B 6D
[MCU->module] STATUS(0x0007)  |  LEN=13  |  DATA=00 02 01 02 00 00 02 01 04 03 01 01 00  |  CRC=7C 69
[module->MCU] SET(0x0003)  |  LEN=5  |  DATA=03 02 01 01 00  |  CRC=16 B7
```

## Installation

1. Open **Logic 2**
2. Go to **Extensions** (puzzle piece icon) → **Load Existing Extension**
3. Select the `philips_uart` folder (the one containing `extension.json`)

## Settings

| Setting | Options | Description |
|---------|---------|-------------|
| Channel | module->MCU / MCU->module / - | Labels each frame with the traffic direction |
| Include Raw Bytes | No / Yes | Appends the full raw hex bytes (incl. sync + CRC) to each frame |

## Usage

1. Tap the **MCU ↔ Wi-Fi-module UART** (not the ESP debug console / flash header).
2. Capture at **115200 baud, 8N1**, on both TX lines with shared GND.
3. Add an **Async Serial** analyzer on the **module TX** channel, then a
   **Philips UART Extractor** HLA on top with **Channel** = `module->MCU`.
4. Add a second **Async Serial** on the **MCU TX** channel, then a second
   **Philips UART Extractor** HLA with **Channel** = `MCU->module`.

Both HLAs run side by side to show the full request/response exchange.

## What to Capture

Control events are sparse and the module polls ~5×/second, so **capture one
action per dump** (a short window around each button press). The frames that
matter are the **`SET (0x0003)`** commands and the **`STATUS (0x0007)`** report
that immediately follows.

| Dump | Action |
|------|--------|
| `bootup` | Power on → wait for the device-info report (`AirPurifier` / model / fw) |
| `speed_app` | One capture per fan speed change via the app |
| `mode_sleep` / `mode_med` / `mode_turbo` | One capture per fan mode (Sleep / Medium / Turbo) |
| `power_on_off` | Toggle power |
| `air_quality` | Let it idle so PM/air-quality reports (group `0x05`) stream |

Use **Export Data** in Logic 2 to export the HLA results as text/CSV. Trim out
the repeating idle poll frames so the actual control events aren't lost.
