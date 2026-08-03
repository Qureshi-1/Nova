import * as Crypto from "expo-crypto";
import * as FileSystem from "expo-file-system";
import { log } from "./bootlog";

log("downloads.js loaded");

export const BRAIN_DIR = FileSystem.documentDirectory + "brain/";
export const MODULES_DIR = BRAIN_DIR + "modules/";

const GITHUB_RELEASE_URL =
  "https://api.github.com/repos/Qureshi-1/Nova/releases/latest";

export const BRAIN_MODULES = [
  {
    id: "python-runtime",
    archive: "python-runtime.tar.gz",
    sha256: "REPLACE_WITH_SHA256_OF_PYTHON_RUNTIME_ARCHIVE",
    sizeMB: 40,
  },
  {
    id: "airllm-core",
    archive: "airllm-core.tar.gz",
    sha256: "REPLACE_WITH_SHA256_OF_AIRLLM_CORE_ARCHIVE",
    sizeMB: 600,
  },
  {
    id: "model-weights",
    archive: "model-weights.tar.gz",
    sha256: "REPLACE_WITH_SHA256_OF_MODEL_WEIGHTS_ARCHIVE",
    sizeMB: 900,
  },
];

export async function getBrainAssetUrl(archiveName) {
  try {
    const res = await fetch(GITHUB_RELEASE_URL);
    if (!res.ok) return null;
    const release = await res.json();
    const asset = (release.assets || []).find((a) => a.name === archiveName);
    return asset ? asset.browser_download_url : null;
  } catch (error) {
    return null;
  }
}

export async function moduleInstalled(moduleId) {
  const marker = MODULES_DIR + moduleId + "/.installed";
  const info = await FileSystem.getInfoAsync(marker);
  return info.exists;
}

export async function allModulesInstalled() {
  for (const module of BRAIN_MODULES) {
    if (!(await moduleInstalled(module.id))) return false;
  }
  return true;
}

export function sha256Hex(bytes) {
  return Array.from(new Uint8Array(bytes))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function hashFile(uri) {
  try {
    const RNFS = require("react-native-fs").default;
    return await RNFS.hash(uri, "sha256");
  } catch (error) {
    const b64 = await FileSystem.readAsStringAsync(uri, {
      encoding: FileSystem.EncodingType.Base64,
    });
    return Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, b64);
  }
}

export async function downloadModule(module, onProgress, onState) {
  const archiveUri = BRAIN_DIR + module.archive;
  const targetDir = MODULES_DIR + module.id;

  await FileSystem.makeDirectoryAsync(BRAIN_DIR, { intermediates: true });
  await FileSystem.makeDirectoryAsync(targetDir, { intermediates: true });

  onState && onState("downloading");

  const url = await getBrainAssetUrl(module.archive);
  if (!url) throw new Error(`Brain asset not found in release: ${module.archive}`);

  const track = (progress) => {
    const pct = progress.totalBytesExpectedToWrite
      ? Math.round((progress.totalBytesWritten / progress.totalBytesExpectedToWrite) * 100)
      : 0;
    onProgress && onProgress(pct);
  };

  const partial = await FileSystem.getInfoAsync(archiveUri);
  if (partial.exists && partial.size > 0) {
    const resume = FileSystem.createDownloadResumable(url, archiveUri, {}, track);
    try {
      const resumed = await resume.resumeAsync();
      if (resumed && resumed.uri && resumed.totalBytesWritten > 0) {
        await FileSystem.deleteAsync(archiveUri, { idempotent: true });
      }
    } catch (error) {}
  }

  const info = await FileSystem.getInfoAsync(archiveUri);
  if (!info.exists || info.size === 0) {
    const download = FileSystem.createDownloadResumable(url, archiveUri, {}, track);
    const done = await download.downloadAsync();
    if (!done || !done.uri) throw new Error(`Download failed: ${module.archive}`);
  }

  onState && onState("verifying");
  const finalInfo = await FileSystem.getInfoAsync(archiveUri);
  if (!finalInfo.exists || finalInfo.size === 0) {
    throw new Error(`Download incomplete: ${module.archive}`);
  }

  if (module.sha256 && module.sha256.startsWith("sha256-")) {
    const digest = await hashFile(archiveUri);
    if (digest !== module.sha256.replace("sha256-", "")) {
      await FileSystem.deleteAsync(archiveUri, { idempotent: true });
      throw new Error(`Checksum mismatch: ${module.archive}`);
    }
  }

  onState && onState("extracting");
  try {
    await FileSystem.unzipAsync(archiveUri, targetDir);
  } catch (error) {
    const RNFS = require("react-native-zip-archive");
    await RNFS.unzip(archiveUri, targetDir);
  }

  const marker = targetDir + "/.installed";
  await FileSystem.writeAsStringAsync(marker, module.sha256);
  await FileSystem.deleteAsync(archiveUri, { idempotent: true });

  onState && onState("done");
  return targetDir;
}

export async function installBrain(onProgress, onState) {
  let cumulative = 0;
  const totalMB = BRAIN_MODULES.reduce((sum, m) => sum + m.sizeMB, 0);
  for (const module of BRAIN_MODULES) {
    if (await moduleInstalled(module.id)) {
      cumulative += module.sizeMB;
      continue;
    }
    await downloadModule(module, (pct) => {
      onProgress && onProgress(Math.round((cumulative + (pct / 100) * module.sizeMB) / totalMB * 100));
    }, onState);
    cumulative += module.sizeMB;
  }
  return true;
}

export async function getBrainStatus() {
  const list = [];
  for (const module of BRAIN_MODULES) {
    list.push({ id: module.id, installed: await moduleInstalled(module.id) });
  }
  return list;
}
