const { execSync } = require("child_process");
const fs = require("fs");
const https = require("https");
const http = require("http");

const list = execSync(
  "eas build:list --platform android --limit 5 --non-interactive --json",
  { encoding: "utf8" }
);

const build = JSON.parse(list.trim()).find(
  (b) => b.status === "FINISHED" && b.artifacts && b.artifacts.applicationArchiveUrl
);
if (!build) throw new Error("No finished Android build with an APK found");

const url = build.artifacts.applicationArchiveUrl;
fs.mkdirSync("build", { recursive: true });
const out = "build/nova.apk";

function download(u, redirectsLeft) {
  if (redirectsLeft <= 0) throw new Error("Too many redirects");
  const mod = u.startsWith("https:") ? https : http;
  mod
    .get(u, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        const next = new URL(res.headers.location, u).toString();
        res.resume();
        download(next, redirectsLeft - 1);
        return;
      }
      if (res.statusCode !== 200) {
        throw new Error(`Download failed with HTTP ${res.statusCode}`);
      }
      const file = fs.createWriteStream(out);
      res.pipe(file);
      file.on("finish", () => file.close(() => console.log(`APK saved to ${out}`)));
      file.on("error", (err) => {
        throw err;
      });
    })
    .on("error", (err) => {
      throw err;
    });
}

download(url, 5);
