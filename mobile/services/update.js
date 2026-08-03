import * as FileSystem from "expo-file-system";
import * as IntentLauncher from "expo-intent-launcher";

import Constants from "expo-constants";

const GITHUB_REPO = "YOUR_USERNAME/nova";
const GITHUB_API = `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`;

export const CURRENT_VERSION = Constants.expoConfig?.version || "1.0.0";

function compareVersions(a, b) {
  const pa = a.split(".").map((n) => parseInt(n, 10) || 0);
  const pb = b.split(".").map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < 3; i++) {
    if ((pa[i] || 0) > (pb[i] || 0)) return 1;
    if ((pa[i] || 0) < (pb[i] || 0)) return -1;
  }
  return 0;
}

export async function checkUpdate() {
  try {
    const res = await fetch(GITHUB_API, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!res.ok) return { available: false, error: true };
    const release = await res.json();
    const apkAsset = (release.assets || []).find((a) => /\.apk$/i.test(a.name));
    const available =
      compareVersions(String(release.tag_name || "0").replace(/^v/i, ""), CURRENT_VERSION) > 0;
    return {
      available,
      error: false,
      version: release.tag_name,
      apkUrl: apkAsset ? apkAsset.browser_download_url : null,
      notes: release.body || "",
    };
  } catch (error) {
    return { available: false, error: true };
  }
}

export async function downloadApk(apkUrl, onProgress) {
  const uri = FileSystem.cacheDirectory + "nova-update.apk";
  await FileSystem.deleteAsync(uri, { idempotent: true });
  const download = FileSystem.createDownloadResumable(apkUrl, uri, {}, (progress) => {
    const pct = progress.totalBytesExpectedToWrite
      ? Math.round((progress.totalBytesWritten / progress.totalBytesExpectedToWrite) * 100)
      : 0;
    onProgress && onProgress(pct);
  });
  const done = await download.downloadAsync();
  if (!done || !done.uri) throw new Error("APK download failed");
  return done.uri;
}

export async function installApk(uri) {
  try {
    await IntentLauncher.startActivityAsync("android.intent.action.VIEW", {
      data: uri,
      flags: 1,
      type: "application/vnd.android.package-archive",
    });
    return true;
  } catch (error) {
    try {
      await IntentLauncher.startActivityAsync("android.intent.action.INSTALL_PACKAGE", {
        data: uri,
        flags: 1,
        type: "application/vnd.android.package-archive",
      });
      return true;
    } catch (error2) {
      return false;
    }
  }
}
