import type { PluginTheme } from "@getpaseo/plugin";
import { Text } from "react-native";
import { rowText, statusColor, type CompactItem } from "./compact";

export function ColoredRowText({ item, name, now, theme, compact, prefix = "" }: {
  item: CompactItem; name: string; now: number; theme: PluginTheme; compact: boolean; prefix?: string;
}) {
  const text = rowText(item, name, now);
  return <Text style={{ color: theme.colors.foreground, fontSize: compact ? 13 : 14 }}>
    {prefix}<Text style={{ color: statusColor(item, theme) }}>{text.slice(0, 1)}</Text>{text.slice(1)}
  </Text>;
}

export function ColoredSummary({ text, theme, compact }: { text: string; theme: PluginTheme; compact: boolean }) {
  return <Text style={{ color: theme.colors.foregroundMuted, fontSize: compact ? 13 : 14 }}>
    {text.split(/(\d+✓|\d+✗|●\d+|\?\d+)/).map((part, i) =>
      <Text key={i} style={{ color: part.includes("✓") ? theme.colors.statusSuccess : part.includes("✗") ? theme.colors.statusDanger : part.includes("●") ? statusColor({ status: "running" }, theme) : theme.colors.foregroundMuted }}>{part}</Text>)}
  </Text>;
}
