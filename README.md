# InuYasha: Seek Jade — Preservation & Local/Hybrid Tooling

Personal technical research and server/client preservation tooling for *InuYasha: Seek Jade*.

## Architecture

| Directory | Purpose |
|---|---|
| `server/` | Local HTTP RPC emulator (`emulator.py`), combat simulator (`combat_sim.py`), modular RPC handler mixins, Hybrid Sync client (`hybrid_sync.py`), and in-game OTA engine (`ota_updater.py`). |
| `android/` | Android standalone lifecycle supervisor (`LocalBackendManager` / `LocalBackendService` Java + Smali) and native launcher source. |
| `poc/` | APK patch/build pipeline (`build_standalone_apk.py`, `patch_vn_apk.py`), OTA release publisher (`publish_ota.py`), and APK verification tests. |
| `deploy/cloudflare_sync/` | Lightweight Cloudflare Workers + D1 Sync Hub for cross-device save sync, async social/PvP peers, and OTA release manifests. |

## Common Commands

### Run Tests
```bash
PYTHONPATH=server python3 -m unittest server/test_r816_ota.py server/test_r82_hybrid_sync.py server/test_emulator.py
node --test deploy/cloudflare_sync/test_sync_hub.mjs
PYTHONPATH=poc python3 -m unittest poc/test_r87_modern_sdk.py
```

### Build Standalone Hybrid APK
Requires the base VN `.xapk`/`.apk` in `originals/` and Android signing keystore outside the repo:
```bash
python3 poc/build_standalone_apk.py \
  --version-code 875 \
  --version-name 5.0.4.98-r8.16-hybrid \
  --app-label "InuYasha Hybrid" \
  --out com.cmn.inuyasha.revival_r8_16_875_hybrid.apk
```

### Publish an In-Game OTA Update
Hotfix patches (`server/*.py`, Lua `.lua`/`.luac`, or UI assets) upload to GitHub Releases and publish a lightweight manifest to Cloudflare Sync Hub:
```bash
python3 poc/publish_ota.py \
  --patch-version r8.16.1 \
  --min-apk-code 875 \
  --latest-apk-code 875 \
  --server-files gddh_handlers.py \
  --changelog "Mô tả ngắn bản vá"
```

When Android-native changes (`AndroidManifest.xml`, Java/Smali, or `.so`) require a new APK:
```bash
python3 poc/publish_ota.py \
  --patch-version r8.17.0 \
  --release-tag r8.17 \
  --min-apk-code 876 \
  --latest-apk-code 876 \
  --latest-apk-name 5.0.4.98-r8.17-hybrid \
  --apk-file analysis/vn/patched/com.cmn.inuyasha.revival_r8_17_876_hybrid.apk \
  --changelog "Cập nhật phần Android"
```

## Notes
- Non-commercial personal research project. Original copyrighted game binaries, OBBs, and extracted assets (`originals/`, `analysis/`, `*.apk`) are excluded from this repository.
