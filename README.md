#  AOSP patches for Galaxian

Required AOSP patches for building AOSP-based ROMs for **Nothing Phone (3a) Lite (Galaxian)**.

Galaxian is MediaTek-based and ships with a fenrir-patched LK (bootchain). Vanilla AOSP assumes a standard Pixel-like verified-boot flow and has no MediaTek camera HAL quirks handling, so these patches are required for boot, flashing, and 60 FPS video recording to work.

Source repo: `https://github.com/samakshkambxj/patches`

## Layout

Each top-level directory maps to an AOSP project path, with `__` used in place of `/`:

```
frameworks__base            ->  frameworks/base
packages__apps__Aperture  ->  packages/apps/Aperture
system__core              ->  system/core
system__fs__fs_mgr        ->  system/fs/fs_mgr
```

`apply.py` resolves the target automatically, e.g. `system__fs__fs_mgr/*.patch` is applied inside `$ANDROID_ROOT/system/fs/fs_mgr` via `git am`.

## Patches

### 1. `packages__apps__Aperture/0001-Aperture-Enable-MediaTek-HFPS-Mode-for-60-FPS-video-.patch`

**Target:** `packages/apps/Aperture`
**File:** `app/src/main/java/org/lineageos/aperture/ext/CaptureRequestOptionsBuilder.kt`
**Original:** bengris32 `<bengris32@protonmail.ch>`, 2024-03-09, `I1e027dcacc48f139c067e4e3ae1d5750d29e65a5`

**Problem:** On MediaTek, requesting a 60 FPS `CONTROL_AE_TARGET_FPS_RANGE` alone is not enough. The camera HAL requires the vendor session parameter `com.mediatek.streamingfeature.hfpsMode=1`, otherwise 60 FPS requests are silently dropped and video records at 30 FPS.

**Fix:**
- Adds `FPS60_MTK_KEY_SESSION_PARAMETER` (`CaptureRequest.Key<Int>`).
- Reworks `setFrameRate()` into an `apply` block that always sets the FPS range, plus sets `hfpsMode=1` when `FrameRate.FPS_60` is selected.

Tested upstream on Xiaomi 12T, POCO X4 GT, OnePlus Nord 3 5G; required on Galaxian for 60 FPS video.

### 2. `packages__apps__Aperture/0002-Aperture-Force-16-9-aspect-ratio-when-60-FPS-is-requ.patch`

**Target:** `packages/apps/Aperture`
**File:** `app/src/main/java/org/lineageos/aperture/CameraActivity.kt`
**Original:** sreelekshman `<sreelekshmanchunakara@gmail.com>`, 2026-07-09, `Ib9ed853afb8f40f00d4eacc25d21daf9974aac48`

**Problem:** MediaTek HAL drops 60 FPS requests if the preview/video streams default to 4:3. Aperture's default `ResolutionSelector` can therefore prevent 60 FPS even with patch 1 applied.

**Fix:**
- When `videoFrameRate == FPS_60`, sets `previewResolutionSelector` to `RATIO_16_9_FALLBACK_AUTO_STRATEGY` before configuring `videoCaptureQualitySelector`.
- Restores the photo aspect-ratio strategy for `IMAGE_CAPTURE`.
- Clears the override for `IMAGE_ANALYSIS`.

Must be applied on top of patch 1.

### 3. `system__core/0001-fastbootd-Always-return-false-for-GetDeviceLockStatu.patch`

**Target:** `system/core`
**File:** `fastboot/device/utility.cpp`
**Original:** Mashopy `<eliasgheeraert@gmail.com>`, 2026-09-28, `Ica59dab533555af1d12c62b9cc71de55d5b51146`

**Problem:** `GetDeviceLockStatus()` returns `ro.boot.verifiedbootstate != "orange"`. On fenrir-patched LKs (which can still flash via bootloader/fastboot) this misreports lock state inside fastbootd and breaks flashing workflows.

**Fix:**
```cpp
bool GetDeviceLockStatus() {
-    return android::base::GetProperty("ro.boot.verifiedbootstate", "") != "orange";
+    return false;
}
```

### 4. `system__fs__fs_mgr/0001-libfs_avb-Allow-LKs-patched-with-fenrir-to-boot-on-A.patch`

**Target:** `system/fs/fs_mgr`
**File:** `libfs_avb/util.cpp`
**Original:** Mashopy `<eliasgheeraert@gmail.com>`, 2026-09-28, `I75b28942684c736492ee2a605f3f137dd0d89b2e`

**Problem:** Fenrir spoofs `verifiedbootstate` to `green`. `IsDeviceUnlocked()` only treated `orange` as unlocked, so AVB verification failed and the device refused to boot AOSP.

**Fix:**
```cpp
if (fs_mgr_get_boot_config("verifiedbootstate", &verified_boot_state)) {
-        return verified_boot_state == "orange";
+        return (verified_boot_state == "orange" || verified_boot_state == "green");
}
```

Without this, Galaxian does not boot AOSP builds on a fenrir-patched LK.

### 5. `frameworks__base/0001-SystemUI-Optimize-notification-list-rebuilds.patch`

**Target:** `frameworks/base`
**File:** `packages/SystemUI/src/com/android/systemui/statusbar/notification/collection/NotifCollection.java`
**Original:** beingashwani `<ashwanic177@gmail.com>`, 2026-08-13, `fa4b30b9ff366644fb24c6c69f8a1082cda82eac` (Signed-off-by Ghosuto)

**Problem:** Every notification post/remove/ranking/update triggered a synchronous list rebuild, and ongoing progress notifications (downloads, media) spam updates, causing SystemUI jank.

**Fix:**
- Adds `dispatchEventsAndCoalescedRebuildList()` with 32ms `REBUILD_COALESCE_WINDOW_MS` delay for post/group-post/remove/ranking/update paths.
- Throttles `EXTRA_PROGRESS` + ongoing updates to one rebuild per 400ms per key (`PROGRESS_REBUILD_THROTTLE_MS`), with delayed `progressThrottleFlush`.
- Clears per-key throttle state in `tryRemoveNotification()`.

### 6. `frameworks__base/0002-SystemUI-Avoid-redundant-Bind-Updated-events.patch`

**Target:** `frameworks/base`
**File:** `packages/SystemUI/src/com/android/systemui/statusbar/notification/collection/NotifCollection.java`
**Original:** Ghosuto `<clash.raja10@gmail.com>`, 2026-08-13, `af0e51288d8feda1e92252b115afcc6269007e51`

**Problem:** Follow-up to patch 5: throttled progress updates still queued `BindEntryEvent`/`EntryUpdatedEvent` before the throttle check, defeating the optimization.

**Fix:**
- Moves `entry.setSbn()` / `BindEntryEvent` / `EntryUpdatedEvent` below the throttle check.
- Throttled path only refreshes `Sbn`; delayed flush re-emits `Bind` + `Updated` then rebuilds.

Must apply after patch 5.

## How to apply

Requirements: Python 3, `git`, a synced AOSP tree (e.g. `~/android`).

1. Clone this repo alongside your tree:
```bash
git clone https://github.com/samakshkambxj/patches
```

2. Apply all patches:
```bash
python3 patches/apply.py patches ~/android
# usage: apply.py <patches_root> <android_root>
```

What it does:
- Recursively finds `*.patch` sorted alphabetically.
- Maps parent dir `__` -> `/` to find the target project under `<android_root>`.
- Runs `git am <patch>` inside each target project.
- Prints per-patch `✓ Patch Applied` / `✗ Patch Failed` plus a final `Applied: n/total` summary.

Manual apply (equivalent):
```bash
git -C ~/android/frameworks/base am ~/patches/frameworks__base/*.patch
git -C ~/android/packages/apps/Aperture am ~/patches/packages__apps__Aperture/*.patch
git -C ~/android/system/core am ~/patches/system__core/*.patch
git -C ~/android/system/fs/fs_mgr am ~/patches/system__fs__fs_mgr/*.patch
```

On conflict:
```bash
# in the failing project dir:
git am --abort   # or fix files, then:
git am --continue
```

Rerunning `apply.py` after resolving is safe; already-applied patches will fail cleanly with `git am` and be reported.

## Credits

- bengris32 (MediaTek HFPS patch)
- sreelekshman (Aperture 16:9 / 60 FPS patch)
- Mashopy / Elias Gheeraert (fastbootd + libfs_avb fenrir patches)
- beingashwani, Ghosuto (SystemUI NotifCollection coalesce + throttle via Rising)
