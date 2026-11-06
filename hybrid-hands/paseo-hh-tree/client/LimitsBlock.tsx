import { Text, View } from "react-native";

import type { TreeLimit } from "../shared/tree";
import { isWeekLimit, limitLine } from "./format";
import type { TreeThemeProps } from "./TreeRow";

export function LimitsBlock({
  limits,
  theme,
  compact,
  now,
}: TreeThemeProps & { limits: TreeLimit[] }) {
  const weekly = limits.filter(isWeekLimit);
  if (!weekly.length) {
    return null;
  }
  return (
    <View style={{ marginBottom: 12 }}>
      <Text
        style={{
          color: theme.colors.foreground,
          fontSize: compact ? 13 : 14,
          fontWeight: "600",
        }}
      >
        Hạn mức
      </Text>
      {weekly.map((limit, index) => (
        <Text
          key={`${limit.plan}-${limit.window}-${index}`}
          style={{
            color: theme.colors.foregroundMuted,
            fontSize: compact ? 12 : 13,
            marginTop: 2,
          }}
        >
          {limitLine(limit, now)}
        </Text>
      ))}
    </View>
  );
}
