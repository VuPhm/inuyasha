# InuYasha Workspace Rules

- Keep every source file (`.py`, `.java`, `.js`, `.ts`, `.lua`) strictly under **450 KiB (`460,800` bytes)** so files remain well below the Antigravity IDE **512 KiB** diff-preview truncation limit and never trigger truncated auto-saves.
- Implement new `ProfileStore` RPC groups as dedicated Mixin modules (`server/*_handlers.py`) inheriting into `ProfileStore` and registered in `build_server_bundle_zip()` inside `poc/build_standalone_apk.py`, rather than growing `server/emulator.py`.
- Never use `edit_file` directly on any file >= `450 KiB`; split it into modules via an AST script first.
