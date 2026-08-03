import React, { useCallback, useEffect, useRef, useState } from "react";
import { SafeAreaView, ScrollView, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import * as FileSystem from "expo-file-system";
import { useSpeechRecognitionEvent } from "expo-speech-recognition";

import { log } from "./services/bootlog";

log("App.js module scope");

if (global.ErrorUtils && global.ErrorUtils.setGlobalHandler) {
  const originalHandler = global.ErrorUtils.getGlobalHandler();
  global.ErrorUtils.setGlobalHandler((error, isFatal) => {
    try {
      log("FATAL JS: " + (error && error.message) + " | " + (error && error.stack));
    } catch (inner) {}
    originalHandler(error, isFatal);
  });
}

import ChatBubble from "./components/ChatBubble";
import Orb from "./components/Orb";
import { discoverBackend } from "./services/discovery";
import { ensurePermissions, hasStoragePermission } from "./services/permissions";
import { useSettingsStore } from "./services/settings";
import { connectNovaSocket, retryDelay } from "./services/websocket";
import { allModulesInstalled, installBrain } from "./services/downloads";
import { checkUpdate, CURRENT_VERSION, downloadApk, installApk } from "./services/update";
import {
  hasWakeWord,
  hapticFailure,
  hapticStart,
  hapticSuccess,
  isFrustrated,
  parseSetIp,
  requestMicPermission,
  sendText,
  speak,
  startSTT,
  stripWakeWord,
} from "./services/voice";

const LISTEN_WINDOW_MS = 30000;
const MAX_RECONNECT_ATTEMPTS = 10;
const IDLE_INITIATIVE_MS = 60000;
const UPDATE_RE = /^(?:check\s+(?:for\s+)?|update\s+check|latest\s+version\b)/i;
const BRAIN_RE = /(?:ai\s*brain|brain|python\s*runtime)\s*(?:download|install|lagao|kar)/i;
const YES_RE = /^(?:yes|yeah|yep|haan|han|kar do|karo|theek hai)$/i;
const NO_RE = /^(?:no|nope|nahi|mat karo|baad mein)$/i;

export default function App() {
  const darkMode = useSettingsStore((s) => s.darkMode);
  const fontScale = useSettingsStore((s) => s.fontScale);
  const model = useSettingsStore((s) => s.model);
  const mode = useSettingsStore((s) => s.mode);

  const [phase, setPhase] = useState("boot");
  const [connected, setConnected] = useState(false);
  const [progress, setProgress] = useState("");
  const [storageText, setStorageText] = useState("");
  const [history, setHistory] = useState([]);
  const [exchange, setExchange] = useState({
    command: "",
    response: "NOVA online, Captain.",
  });

  const phaseRef = useRef(phase);
  phaseRef.current = phase;

  const wsRef = useRef(null);
  const listenUntilRef = useRef(0);
  const speechBufRef = useRef("");
  const failedCountRef = useRef(0);
  const lastCommandRef = useRef("");
  const retriedRef = useRef(false);
  const connectAttemptRef = useRef(0);
  const stoppedRef = useRef(false);
  const initiativeTimerRef = useRef(null);
  const initiativeSpokenRef = useRef(false);
  const awaitingBrainRef = useRef(false);
  const updatePendingRef = useRef(false);
  const updateInfoRef = useRef(null);
  const brainDoneRef = useRef(false);
  const storageWarnedRef = useRef(false);

  const refreshStorage = useCallback(async () => {
    try {
      const free = await FileSystem.getFreeDiskStorageAsync();
      const gb = (free / 1024 / 1024 / 1024).toFixed(1);
      setStorageText(`${gb} GB free`);
    } catch (error) {
      setStorageText("");
    }
  }, []);

  const goIdle = useCallback(() => {
    if (stoppedRef.current) return;
    setPhase("idle");
    if (initiativeTimerRef.current) clearTimeout(initiativeTimerRef.current);
    if (!initiativeSpokenRef.current && lastCommandRef.current) {
      initiativeTimerRef.current = setTimeout(() => {
        if (!stoppedRef.current && !initiativeSpokenRef.current) {
          initiativeSpokenRef.current = true;
          hapticSuccess();
          setExchange((x) => ({ ...x, response: "Boss, kuch aur help chahiye?" }));
          speak("Boss, kuch aur help chahiye?", () => {
            if (!stoppedRef.current) startSTT();
          });
        }
      }, IDLE_INITIATIVE_MS);
    }
    speak("Going idle, Captain. Say Hey Nova to wake me up.", () => {
      if (!stoppedRef.current) startSTT();
    });
  }, []);

  const wake = useCallback(() => {
    if (stoppedRef.current) return;
    failedCountRef.current = 0;
    initiativeSpokenRef.current = false;
    if (initiativeTimerRef.current) clearTimeout(initiativeTimerRef.current);
    listenUntilRef.current = Date.now() + LISTEN_WINDOW_MS;
    speechBufRef.current = "";
    setPhase("listening");
    speak("Listening, Captain.", () => {
      if (!stoppedRef.current) startSTT();
    });
  }, []);

  const resumeListening = useCallback(() => {
    if (stoppedRef.current) return;
    if (Date.now() < listenUntilRef.current) {
      setPhase("listening");
      startSTT();
    } else {
      goIdle();
    }
  }, [goIdle]);

  const flashError = useCallback(() => {
    setPhase("error");
    setTimeout(() => {
      if (!stoppedRef.current) setPhase("speaking");
    }, 500);
  }, []);

  const startBrainInstall = useCallback(async () => {
    awaitingBrainRef.current = false;
    hapticStart();
    setPhase("executing");
    await speak("Theek hai, Captain. AI Brain download shuru. Thoda waqt lagega, main har baar bataungi.");
    let lastMilestone = -1;
    try {
      await installBrain(
        (pct) => {
          setProgress(`AI Brain download ${pct}%`);
          const milestone = Math.floor(pct / 25);
          if (milestone > lastMilestone) {
            lastMilestone = milestone;
            if (pct > 0) {
              speak(`AI Brain download ${pct}% completed, Captain.`);
            }
          }
        },
        (state) => {
          if (state === "extracting") {
            setProgress("AI Brain extract ho raha hai");
            speak("AI Brain extract ho raha hai, Captain.");
          }
        }
      );
      brainDoneRef.current = true;
      setProgress("");
      hapticSuccess();
      setPhase("speaking");
      setExchange((x) => ({ ...x, response: "AI Brain installed, Captain. Ab main full dimaag se kaam kar sakti hoon." }));
      await speak("AI Brain installed, Captain. Ab main full dimaag se kaam kar sakti hoon.");
      refreshStorage();
    } catch (error) {
      hapticFailure();
      setProgress("");
      flashError();
      setExchange((x) => ({ ...x, response: "Boss, AI Brain download abhi fail hua. Phir se try karte hain?" }));
      await speak("Boss, AI Brain download abhi fail hua. Phir se try karte hain?");
    }
    if (!stoppedRef.current) resumeListening();
  }, [flashError, refreshStorage]);

  const doUpdate = useCallback(async () => {
    updatePendingRef.current = false;
    const info = updateInfoRef.current;
    if (!info || !info.apkUrl) {
      await speak("Boss, update file nahi mili. GitHub Release pe check kar lijiye.");
      return;
    }
    hapticStart();
    setPhase("executing");
    let lastMilestone = -1;
    try {
      const uri = await downloadApk(info.apkUrl, (pct) => {
        setProgress(`Update download ${pct}%`);
        const milestone = Math.floor(pct / 25);
        if (milestone > lastMilestone) {
          lastMilestone = milestone;
          if (pct > 0) speak(`Update download ${pct}% completed, Captain.`);
        }
      });
      setProgress("");
      hapticSuccess();
      await speak("Update download complete. Install prompt aa raha hai, Captain.");
      const installed = await installApk(uri);
      if (!installed) {
        await speak("Boss, install prompt khul nahi paya. System settings se unknown sources allow kar ke dobara try karein.");
      }
    } catch (error) {
      hapticFailure();
      setProgress("");
      flashError();
      await speak("Boss, update download fail hua. Phir se try karte hain?");
    }
    if (!stoppedRef.current) resumeListening();
  }, [flashError]);

  const handleUpdateCommand = useCallback(async () => {
    hapticStart();
    setPhase("executing");
    setProgress("Update check ho raha hai");
    await speak("Update check kar rahi hoon, Captain.");
    const info = await checkUpdate();
    setProgress("");
    if (info.error) {
      hapticFailure();
      flashError();
      await speak("Boss, GitHub se baat nahi ho payi. Network check karein.");
      if (!stoppedRef.current) resumeListening();
      return;
    }
    if (!info.available) {
      hapticSuccess();
      setPhase("speaking");
      setExchange((x) => ({ ...x, response: `Sab latest hai, Captain. Version ${CURRENT_VERSION} chal raha hai.` }));
      await speak(`Sab latest hai, Captain. Version ${CURRENT_VERSION} chal raha hai.`);
      if (!stoppedRef.current) resumeListening();
      return;
    }
    updateInfoRef.current = info;
    updatePendingRef.current = true;
    hapticSuccess();
    setPhase("speaking");
    setExchange((x) => ({ ...x, response: `Captain, naya update available hai: ${info.version}. Download karun?` }));
    await speak(`Captain, naya update available hai: ${info.version}. Download karun?`);
  }, [flashError]);

  const onResult = useCallback(
    (data) => {
      if (stoppedRef.current) return;
      if (data.type === "progress") {
        setProgress(data.payload || "");
        return;
      }
      if (data.type === "notice") {
        hapticSuccess();
        setProgress("");
        setHistory((h) => [...h, { role: "assistant", text: data.payload || "" }]);
        setExchange((x) => ({ ...x, response: data.payload || "" }));
        speak(data.payload, () => {
          if (!stoppedRef.current) resumeListening();
        });
        return;
      }
      if (data.type === "error") {
        hapticFailure();
        setProgress("");
        flashError();
        setHistory((h) => [...h, { role: "assistant", text: "Boss, wo kaam abhi nahi ho paya." }]);
        speak("Boss, wo kaam abhi nahi ho paya. Ghabrana nahi, phir se try karte hain.", () => {
          if (!stoppedRef.current) resumeListening();
        });
        return;
      }
      if (data.type !== "result") return;
      setProgress("");
      const text = data.payload || "";
      useSettingsStore.getState().applyFromResponse(text);
      if (/^tool error/i.test(text)) {
        hapticFailure();
        flashError();
        speak("Sorry, Captain. Let me try again.");
        if (!retriedRef.current) {
          retriedRef.current = true;
          setTimeout(() => {
            retriedRef.current = false;
            if (!stoppedRef.current && lastCommandRef.current) {
              runCommand(lastCommandRef.current, true);
            }
          }, 1500);
        } else {
          retriedRef.current = false;
          setTimeout(() => {
            if (!stoppedRef.current) resumeListening();
          }, 2000);
        }
        return;
      }
      hapticSuccess();
      setPhase("speaking");
      setHistory((h) => [...h, { role: "assistant", text }]);
      setExchange((x) => ({ ...x, response: text }));
      speak(text, () => {
        if (!stoppedRef.current) resumeListening();
      });
    },
    [flashError, resumeListening]
  );

  const retryConnect = useCallback(() => {
    if (stoppedRef.current) return;
    const ip = useSettingsStore.getState().backendIp;
    if (!ip) return;
    connectAttemptRef.current += 1;
    const attempt = connectAttemptRef.current;
    const ws = connectNovaSocket(ip, {
      onOpen: () => {
        connectAttemptRef.current = 0;
        setConnected(true);
      },
      onClose: () => {
        setConnected(false);
        if (stoppedRef.current) return;
        if (attempt === 3) {
          speak("Server ko phir se jaga rahi hoon, Captain.");
        }
        if (connectAttemptRef.current < MAX_RECONNECT_ATTEMPTS) {
          setTimeout(retryConnect, retryDelay(connectAttemptRef.current));
        }
      },
      onError: () => {},
      onMessage: onResult,
    });
    wsRef.current = ws;
  }, [onResult]);

  const runCommand = useCallback(
    async (command, isRetry = false) => {
      if (stoppedRef.current) return;
      const clean = stripWakeWord(command);
      if (!clean) return;

      if (awaitingBrainRef.current) {
        if (YES_RE.test(clean)) {
          startBrainInstall();
          return;
        }
        if (NO_RE.test(clean)) {
          awaitingBrainRef.current = false;
          hapticSuccess();
          setPhase("speaking");
          await speak("Theek hai, Captain. Jab chaaho bolna, 'Nova, brain download'. Abhi bhi kuch karun?");
          if (!stoppedRef.current) resumeListening();
          return;
        }
      }

      if (updatePendingRef.current) {
        if (YES_RE.test(clean)) {
          doUpdate();
          return;
        }
        if (NO_RE.test(clean)) {
          updatePendingRef.current = false;
          hapticSuccess();
          setPhase("speaking");
          await speak("Theek hai, Captain. Update baad mein kar lenge.");
          if (!stoppedRef.current) resumeListening();
          return;
        }
      }

      if (UPDATE_RE.test(clean)) {
        handleUpdateCommand();
        return;
      }
      if (BRAIN_RE.test(clean)) {
        if (brainDoneRef.current || (await allModulesInstalled())) {
          brainDoneRef.current = true;
          hapticSuccess();
          setPhase("speaking");
          await speak("AI Brain pehle se installed hai, Captain.");
          if (!stoppedRef.current) resumeListening();
          return;
        }
        startBrainInstall();
        return;
      }

      if (!isRetry && isFrustrated(clean) && /(sorry|nahi mila|error|Termux|try again|let me try)/i.test(exchange.response)) {
        hapticSuccess();
        setPhase("speaking");
        await speak("Boss, suno. Main hoon na. Phir se try karte hain.");
        if (stoppedRef.current) return;
      }
      lastCommandRef.current = clean;
      setExchange((x) => ({ ...x, command: clean }));
      hapticStart();
      setPhase("executing");
      await speak("Working on it, Captain.");
      if (stoppedRef.current) return;

      const localIp = parseSetIp(clean);
      if (localIp) {
        useSettingsStore.getState().setBackendIp(localIp);
        hapticSuccess();
        const done = `Backend IP set to ${localIp}, Captain.`;
        setExchange((x) => ({ ...x, response: done }));
        setPhase("speaking");
        speak(done, () => {
          if (!stoppedRef.current) startSTT();
        });
        return;
      }

      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        hapticFailure();
        await speak("Sorry, Captain. Let me try again.");
        if (!isRetry) {
          retryConnect();
          setTimeout(() => runCommand(clean, true), 1500);
        } else {
          await speak(
            "Captain, I can't find the backend. Please ask Suhail or Qureshi to type the IP on my behalf."
          );
          goIdle();
        }
        return;
      }

      try {
        sendText(ws, clean);
      } catch (error) {
        hapticFailure();
        await speak("Sorry, Captain. Let me try again.");
        if (!isRetry) {
          retryConnect();
          setTimeout(() => runCommand(clean, true), 1500);
        } else {
          await speak(
            "Captain, I can't find the backend. Please ask Suhail or Qureshi to type the IP on my behalf."
          );
          goIdle();
        }
      }
    },
    [goIdle, retryConnect, startBrainInstall, doUpdate, handleUpdateCommand, flashError, exchange.response]
  );

  useSpeechRecognitionEvent("end", () => {
    if (stoppedRef.current) return;
    const now = phaseRef.current;
    if (now === "idle" || now === "listening") {
      setTimeout(() => {
        if (!stoppedRef.current) {
          const latest = phaseRef.current;
          if (latest === "idle" || latest === "listening") startSTT();
        }
      }, 250);
    }
  });

  useSpeechRecognitionEvent("result", (event) => {
    if (stoppedRef.current) return;
    const results = event.results || [];
    const transcript = (results[0] && results[0].transcript) || "";
    const isFinal = !!event.isFinal;
    const now = phaseRef.current;

    if (now === "idle") {
      if (isFinal || hasWakeWord(transcript)) wake();
      return;
    }
    if (now === "listening") {
      if (isFinal) {
        const command = (speechBufRef.current + " " + transcript).trim();
        speechBufRef.current = "";
        if (command) runCommand(command);
      } else {
        speechBufRef.current = transcript;
      }
    }
  });

  useSpeechRecognitionEvent("error", (event) => {
    if (stoppedRef.current) return;
    const code = (event && event.error) || "error";
    if (code === "no-speech" || code === "silence" || code === "nothing-heard") return;
    failedCountRef.current += 1;
    if (phaseRef.current === "listening") {
      if (failedCountRef.current >= 3) {
        failedCountRef.current = 0;
        speak("My ears are failing me today. Let me reset.", () => {
          if (!stoppedRef.current) startSTT();
        });
      } else {
        speak("I didn't quite catch that, Captain. Can you repeat?", () => {
          if (!stoppedRef.current) startSTT();
        });
      }
    }
  });

  useEffect(() => {
    log("App: rendered");
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        log("boot: start");
        await ensurePermissions(async () => {
          await speak("NOVA needs storage access to create folders and manage files for you, Captain.");
        });
        log("boot: permissions done");
        await requestMicPermission();
        log("boot: mic done");
        await useSettingsStore.getState().load();
        log("boot: settings done");
        refreshStorage();
        if (cancelled) return;
        await speak("NOVA online, Captain. Searching for the backend.");
        log("boot: online spoken");
        if (cancelled) return;
        const saved = useSettingsStore.getState().backendIp;
        const found = await discoverBackend(saved ? [saved] : []);
        log("boot: discovery done found=" + found);
        if (cancelled) return;
        if (found) {
          useSettingsStore.getState().setBackendIp(found);
          retryConnect();
          log("boot: connected ws");
        } else {
          await speak(
            "Captain, I can't find the backend. Please ask Suhail or Qureshi to type the IP on my behalf."
          );
        }
        if (cancelled) return;

        let brainReady = false;
        try {
          brainReady = await allModulesInstalled();
        } catch (error) {}
        brainDoneRef.current = brainReady;
        log("boot: brain check done=" + brainReady);
        if (cancelled) return;
        if (!brainReady) {
          awaitingBrainRef.current = true;
          await speak("Captain, AI Brain download karna padega, 1.5 GB. Karun?");
        } else {
          await speak("AI Brain ready hai, Captain. Main full power pe hoon.");
        }
        goIdle();
        log("boot: goIdle");
      } catch (error) {
        log("boot: EXCEPTION " + (error && error.message) + " | " + (error && error.stack));
      }
    })();
    return () => {
      cancelled = true;
      stoppedRef.current = true;
    };
  }, [goIdle, retryConnect, refreshStorage]);

  useEffect(() => {
    if (storageWarnedRef.current) return;
    storageWarnedRef.current = true;
    (async () => {
      const ok = await hasStoragePermission();
      if (!ok && phaseRef.current !== "boot") {
        await speak("Boss, storage access band ho gaya hai. Settings mein jaake All files access phir se allow kar dijiye.");
      }
    })();
  }, []);

  const theme = {
    bg: darkMode ? "#000000" : "#F2F6FF",
    fg: darkMode ? "#FFFFFF" : "#10182B",
    dim: darkMode ? "#8A93AD" : "#5A6480",
    accent: "#00E5FF",
  };
  const size = (n) => Math.round(n * fontScale);
  const pastFive = history.slice(-5).reverse();

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: theme.bg }]}>
      <StatusBar style={darkMode ? "light" : "dark"} />
      <View style={styles.header}>
        <Text style={[styles.title, { fontSize: size(26), color: theme.accent }]}>
          NOVA
        </Text>
        <Text
          style={[
            styles.status,
            { fontSize: size(13), color: connected ? theme.accent : theme.dim },
          ]}
        >
          {connected ? "connected" : "disconnected"}
        </Text>
      </View>
      <Text
        style={[
          styles.statusLine,
          { fontSize: size(12), color: theme.dim },
        ]}
      >
        {`Model: ${model} | Mode: ${mode} | ${storageText || "Storage: ..."} | v${CURRENT_VERSION}`}
      </Text>

      <View style={styles.orbWrap}>
        <Orb state={phase} />
        {progress ? (
          <Text
            style={[
              styles.progress,
              { fontSize: size(12), color: theme.dim },
            ]}
          >
            {progress}
          </Text>
        ) : null}
      </View>

      <ScrollView
        style={styles.chat}
        contentContainerStyle={styles.chatContent}
        showsVerticalScrollIndicator={false}
      >
        {exchange.command ? (
          <ChatBubble message={{ role: "user", text: exchange.command }} />
        ) : null}
        <ChatBubble message={{ role: "assistant", text: exchange.response }} />
        {pastFive.length > 0 ? (
          <View style={styles.history}>
            {pastFive.map((entry, index) => (
              <ChatBubble
                key={`${index}-${entry.text.slice(0, 12)}`}
                message={entry}
                small
              />
            ))}
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingTop: 12,
    paddingBottom: 4,
  },
  title: { fontWeight: "800", flex: 1 },
  status: {},
  statusLine: { paddingHorizontal: 20, paddingBottom: 6 },
  orbWrap: { alignItems: "center", paddingVertical: 12 },
  progress: { marginTop: 6, textAlign: "center", paddingHorizontal: 24 },
  chat: { flex: 1 },
  chatContent: { paddingHorizontal: 16, paddingBottom: 16 },
  history: {
    marginTop: 18,
    borderTopWidth: 1,
    borderTopColor: "#1C2436",
    paddingTop: 10,
  },
});
