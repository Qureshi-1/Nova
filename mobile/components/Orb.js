import React, { useEffect, useRef } from "react";
import { Animated, Easing, StyleSheet } from "react-native";

const BASE_SIZE = 150;

const STATE_STYLE = {
  boot: { color: "#1A2233", glow: "#3A4A6E", kind: "pulse" },
  idle: { color: "#00E5FF", glow: "#7FF3FF", kind: "pulse" },
  listening: { color: "#1E6FFF", glow: "#7FBCFF", kind: "pulse" },
  thinking: { color: "#B026FF", glow: "#E3A8FF", kind: "rotate" },
  speaking: { color: "#00FFA3", glow: "#00FFA3", kind: "steady" },
  executing: { color: "#00FFA3", glow: "#00FFA3", kind: "steady" },
  error: { color: "#FF3B3B", glow: "#FF8A8A", kind: "shake" },
};

export default function Orb({ state = "idle" }) {
  const progress = useRef(new Animated.Value(0)).current;
  const shake = useRef(new Animated.Value(0)).current;
  const rotate = useRef(new Animated.Value(0)).current;
  const style = STATE_STYLE[state] || STATE_STYLE.idle;

  useEffect(() => {
    progress.setValue(0);
    shake.setValue(0);
    rotate.setValue(0);
    let loop = null;
    if (style.kind === "pulse") {
      loop = Animated.loop(
        Animated.sequence([
          Animated.timing(progress, {
            toValue: 1,
            duration: state === "listening" ? 320 : 1200,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
          Animated.timing(progress, {
            toValue: 0,
            duration: state === "listening" ? 320 : 1200,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: false,
          }),
        ])
      );
    } else if (style.kind === "rotate") {
      loop = Animated.loop(
        Animated.timing(rotate, {
          toValue: 1,
          duration: 1600,
          easing: Easing.linear,
          useNativeDriver: false,
        })
      );
    } else if (style.kind === "shake") {
      loop = Animated.loop(
        Animated.sequence([
          Animated.timing(shake, {
            toValue: 1,
            duration: 90,
            easing: Easing.linear,
            useNativeDriver: false,
          }),
          Animated.timing(shake, {
            toValue: -1,
            duration: 90,
            easing: Easing.linear,
            useNativeDriver: false,
          }),
          Animated.timing(shake, {
            toValue: 0,
            duration: 90,
            easing: Easing.linear,
            useNativeDriver: false,
          }),
        ])
      );
    }
    if (loop) {
      loop.start();
      return () => loop.stop();
    }
    return undefined;
  }, [progress, shake, rotate, state, style.kind]);

  const color = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [style.color, style.glow],
  });
  const scale = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.15],
  });
  const spin = rotate.interpolate({
    inputRange: [0, 1],
    outputRange: ["0deg", "360deg"],
  });
  const offsetX = shake.interpolate({
    inputRange: [-1, 1],
    outputRange: [-14, 14],
  });

  const inner = {
    width: BASE_SIZE,
    height: BASE_SIZE,
    borderRadius: BASE_SIZE / 2,
    backgroundColor: color,
  };
  if (style.kind === "pulse") inner.transform = [{ scale }];
  if (style.kind === "rotate") inner.transform = [{ rotate: spin }];
  if (style.kind === "shake") inner.transform = [{ translateX: offsetX }];

  return (
    <Animated.View style={[styles.orb, style.kind === "shake" ? { transform: [{ translateX: offsetX }] } : null]}>
      <Animated.View style={[styles.orbInner, inner]} />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  orb: {
    shadowColor: "#00E5FF",
    shadowOpacity: 0.9,
    shadowRadius: 40,
    shadowOffset: { width: 0, height: 0 },
    elevation: 16,
  },
  orbInner: {
    shadowColor: "#00E5FF",
    shadowOpacity: 0.9,
    shadowRadius: 40,
    shadowOffset: { width: 0, height: 0 },
    elevation: 16,
  },
});
