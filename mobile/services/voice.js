import * as Speech from "expo-speech";
import { Vibration } from "react-native";
import { ExpoSpeechRecognitionModule } from "expo-speech-recognition";

export const WAKE_RE = /(?:^|\s)(?:hey\s+|okay\s+|ok\s+)?nova(?:,|\s|$)/i;
const LEADING_WAKE_RE = /^\s*(?:hey\s+|okay\s+|ok\s+)?nova\b[,]?\s*/i;
export const SET_IP_RE = /\bset\s+(?:the\s+)?ip\s+(?:to\s+)?(\d{1,3}(?:\.\d{1,3}){3})\b/i;

export async function requestMicPermission() {
  try {
    const status = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
    return status && status.granted;
  } catch (error) {
    return false;
  }
}

export function startSTT() {
  try {
    ExpoSpeechRecognitionModule.stop();
  } catch (error) {}
  try {
    ExpoSpeechRecognitionModule.start({
      lang: "en-US",
      continuous: true,
      interimResults: true,
      addsPunctuation: false,
    });
  } catch (error) {}
}

export function stopSTT() {
  try {
    ExpoSpeechRecognitionModule.abort();
  } catch (error) {}
  try {
    ExpoSpeechRecognitionModule.stop();
  } catch (error) {}
}

export function speak(text, onDone = () => {}) {
  stopSTT();
  try {
    Speech.stop();
  } catch (error) {}
  if (!text) {
    onDone();
    return;
  }
  try {
    Speech.speak(text, {
      language: "en-US",
      rate: 0.95,
      pitch: 1.05,
      onDone,
      onStopped: onDone,
      onError: onDone,
    });
  } catch (error) {
    onDone();
  }
}

export function hapticStart() {
  Vibration.vibrate(100);
}

export function hapticSuccess() {
  Vibration.vibrate([0, 200, 100, 200]);
}

export function hapticFailure() {
  Vibration.vibrate(500);
}

export function hasWakeWord(text) {
  return WAKE_RE.test(text || "");
}

export function stripWakeWord(text) {
  return (text || "").replace(LEADING_WAKE_RE, "").trim();
}

export function parseSetIp(text) {
  const match = (text || "").match(SET_IP_RE);
  return match ? match[1] : null;
}

export function sendText(ws, text) {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    throw new Error("Backend not connected");
  }
  ws.send(JSON.stringify({ type: "voice_text", payload: text }));
}

const FRUSTRATION_RE =
  /(?:phir\s*se|again|repeat|dimaag|kaam\s+nahi|not\s+working|stupid|galat|wrong|slow|kya\s+ho\s+raha)/i;

export function isFrustrated(text) {
  return FRUSTRATION_RE.test(text || "");
}
