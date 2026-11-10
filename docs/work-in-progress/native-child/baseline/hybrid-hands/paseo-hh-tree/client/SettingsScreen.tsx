import type { PluginSurfaceProps } from "@getpaseo/plugin/client";
import { useSettings } from "@getpaseo/plugin/client";
import {
  Loading,
  ScrollView,
  SettingsAction,
  SettingsInput,
  SettingsSection,
} from "@getpaseo/plugin/client/ui";
import { useEffect, useState } from "react";
import { Text, View } from "react-native";

import { hhTreeSettings } from "../shared/settings";

const SETTING_HINT =
  "Đường dẫn tuyệt đối tới tệp hh-ps. Để trống để tự dò trong PATH hoặc thư mục plugin.";
const SETTING_PLACEHOLDER = "/đường/dẫn/tới/hh-ps";

export function SettingsScreen({
  theme,
  layout,
}: Pick<PluginSurfaceProps, "theme" | "layout">) {
  const settings = useSettings(hhTreeSettings);
  const savedPath = settings.status === "ready" ? settings.values.hhPsPath : "";
  const revision = settings.status === "ready" ? settings.revision : "";
  const [draft, setDraft] = useState(savedPath);

  useEffect(() => {
    if (revision) {
      setDraft(savedPath);
    }
  }, [revision, savedPath]);

  if (settings.status === "loading") {
    return <Loading />;
  }
  if (settings.status === "error" || settings.status === "invalid") {
    return (
      <View style={{ flex: 1, backgroundColor: theme.colors.surface0 }}>
        <Text
          style={{
            color: theme.colors.statusWarning,
            padding: layout.compact ? 16 : 24,
          }}
        >
          {settings.error}
        </Text>
      </View>
    );
  }

  const save = () => {
    void settings.save(
      { ...settings.values, hhPsPath: draft.trim() },
      settings.revision,
    );
  };

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.surface0 }}>
      <ScrollView contentContainerStyle={{ padding: layout.compact ? 16 : 24 }}>
        <SettingsSection title="Đường dẫn hh-ps" info={<Text>{SETTING_HINT}</Text>}>
          <SettingsInput
            label="Tệp hh-ps"
            initialValue={savedPath}
            onChangeText={setDraft}
            placeholder={SETTING_PLACEHOLDER}
            hint={SETTING_HINT}
            disabled={settings.saving}
          />
          <SettingsAction
            label="Đường dẫn hh-ps"
            actionLabel={settings.saving ? "Đang lưu…" : "Lưu"}
            onPress={save}
            disabled={settings.saving}
          />
        </SettingsSection>
        {settings.saveError ? (
          <Text style={{ color: theme.colors.statusWarning, marginTop: 12 }}>
            {settings.saveError}
          </Text>
        ) : null}
      </ScrollView>
    </View>
  );
}
