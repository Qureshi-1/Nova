import React from "react";
import { StyleSheet, Text, View } from "react-native";

export default function ChatBubble({ message, small = false }) {
  const isUser = message.role === "user";
  return (
    <View style={[styles.row, isUser ? styles.rowUser : styles.rowAssistant]}>
      <View
        style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant, small && styles.bubbleSmall]}
      >
        <Text
          style={[styles.text, small ? styles.textSmall : styles.textMain]}
        >
          {message.text}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { marginVertical: 5, flexDirection: "row" },
  rowUser: { justifyContent: "flex-end" },
  rowAssistant: { justifyContent: "flex-start" },
  bubble: {
    maxWidth: "86%",
    borderRadius: 18,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  bubbleSmall: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  bubbleUser: { backgroundColor: "#0E2A33", borderWidth: 1, borderColor: "#00E5FF" },
  bubbleAssistant: { backgroundColor: "#101318", borderWidth: 1, borderColor: "#1C2436" },
  text: { color: "#FFFFFF" },
  textMain: { fontSize: 24, lineHeight: 33 },
  textSmall: { fontSize: 14, lineHeight: 19, color: "#8A93AD" },
});
