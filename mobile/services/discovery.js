import axios from "axios";
import * as Network from "expo-network";
import { log } from "./bootlog";

log("discovery.js loaded");

const PORT = 8000;
const SCAN_TIMEOUT_MS = 700;
const BATCH_SIZE = 20;

function deriveSubnet(ip) {
  if (!ip) return null;
  const parts = ip.split(".");
  if (parts.length !== 4) return null;
  return `${parts[0]}.${parts[1]}.${parts[2]}`;
}

async function probe(ip) {
  try {
    const res = await axios.get(`http://${ip}:${PORT}/health`, {
      timeout: SCAN_TIMEOUT_MS,
    });
    if (res.data && res.data.status === "ok") return ip;
  } catch (error) {}
  return null;
}

export async function discoverBackend(knownIps = []) {
  const candidates = [];
  const seen = new Set();
  const push = (ip) => {
    if (ip && !seen.has(ip)) {
      seen.add(ip);
      candidates.push(ip);
    }
  };

  for (const ip of knownIps) push(ip);
  push("127.0.0.1");

  let localIp = null;
  try {
    localIp = await Network.getIpAddressAsync();
  } catch (error) {}

  const subnet = deriveSubnet(localIp);
  if (subnet) {
    for (let i = 1; i <= 254; i++) push(`${subnet}.${i}`);
  }

  for (let i = 0; i < candidates.length; i += BATCH_SIZE) {
    const batch = candidates.slice(i, i + BATCH_SIZE);
    const results = await Promise.allSettled(batch.map((ip) => probe(ip)));
    const found = results.find((r) => r.status === "fulfilled" && r.value);
    if (found) return found.value;
  }
  return null;
}
