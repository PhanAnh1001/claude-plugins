import { defineSettings } from "@getpaseo/plugin";
import { z } from "zod";

export const hhTreeSettings = defineSettings({
  id: "hh-tree",
  scope: "host",
  version: 1,
  schema: z.object({
    hhPsPath: z.string().default(""),
  }),
});

export type HhTreeSettingsSchema = typeof hhTreeSettings.schema;
