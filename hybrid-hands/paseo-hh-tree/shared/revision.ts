import { defineRpc } from "@getpaseo/plugin";
import { z } from "zod";

/** Client asks the cheap revision RPC this often; hh-tree.get runs only on change. */
export const REVISION_POLL_MS = 2_000;

export const revisionRpc = defineRpc({
  name: "hh-tree.revision",
  input: z.object({}),
  output: z.object({ revision: z.number() }),
});
