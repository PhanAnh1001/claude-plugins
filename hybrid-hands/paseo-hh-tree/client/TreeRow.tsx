import type { PluginTheme } from "@getpaseo/plugin";
import type { ReactNode } from "react";
import { View } from "react-native";

export const INDENT = 16;
export const SEPARATOR = " · ";
export const BULLET = "• ";

export interface TreeThemeProps {
  theme: PluginTheme;
  compact: boolean;
  now: number;
}

export function Row({
  depth,
  children,
}: {
  depth: number;
  children: ReactNode;
}) {
  return <View style={{ paddingLeft: depth * INDENT, paddingVertical: 2 }}>{children}</View>;
}
