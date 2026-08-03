import * as FileSystem from "expo-file-system";

const TARGETS = [
  "/sdcard/Download/nova-boot.log",
  "/sdcard/nova-boot.log",
];

let lines = [];

async function write(target, body) {
  try {
    const slash = target.lastIndexOf("/");
    const parent = target.slice(0, slash);
    const info = await FileSystem.getInfoAsync(parent);
    if (!info.exists) {
      await FileSystem.makeDirectoryAsync(parent, { intermediates: true });
    }
    await FileSystem.writeAsStringAsync(target, body);
  } catch (error) {}
}

export function log(message) {
  lines.push(`${Date.now()} ${message}`);
  const body = lines.join("\n") + "\n";
  for (const target of TARGETS) {
    write(target, body);
  }
}
