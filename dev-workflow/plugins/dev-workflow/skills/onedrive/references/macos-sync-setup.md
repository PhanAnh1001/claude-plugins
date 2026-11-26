# OneDrive sync on macOS for `dw onedrive`

## Summary

- **When:** the tenant will not approve a Graph app (admin consent needed and not granted). Use a folder synced by
  the OneDrive app instead: no `client_id`, no sign-in token, plain file operations.
- **Steps:** (1) the user installs the app (`! brew install --cask onedrive`, needs the machine password), (2) signs
  in with the work account, (3) adds shared folders with "Add shortcut to My files", (4) `dw onedrive discover`,
  writes the alias in `.claude/dev-workflow.toml`, checks with `dw onedrive folders --check`, (5) uses
  `mkdir`/`put`/`ls`/`get`.
- **Agent limits:** the agent cannot run the installer (sudo needs a terminal) or the GUI sign-in; it asks the user.
- **Print this guide:** `dw onedrive guide` (works without any config).

## 1. When to use the synced-folder backend

- The company tenant requires admin consent for apps and nobody can grant it, so Graph sign-in fails (`AADSTS...`).
- The machine can run the OneDrive app and may keep a synced copy. Otherwise (servers, CI) use Graph.

## 2. Install

- `brew install --cask onedrive` runs a `.pkg` installer through sudo and asks for the machine password. The agent
  has no terminal for sudo, so the user types it in the prompt: `! brew install --cask onedrive`.
- Alternative: install "OneDrive" from the Mac App Store.

## 3. Sign in

1. Open OneDrive.app and sign in with the company (work or school) account; accept the default location.
2. On macOS 12.1+ OneDrive uses File Provider: the folder is `~/Library/CloudStorage/OneDrive-<Organization>/`
   (for example `OneDrive-Saltlux`) and Finder shows it under Locations in the sidebar.
3. If macOS asks, allow it in System Settings -> Privacy & Security, or General -> Login Items & Extensions ->
   File Provider.

## 4. Folders other people shared

- Open the sharing link in a browser and choose "Add shortcut to My files" (Vietnamese UI: "Thêm lối tắt vào Tệp
  của tôi"). The shortcut appears in the OneDrive root after sync (a few minutes).
- Writing needs Edit permission; with View permission the folder is read-only.
- Alternative: "Sync" on a SharePoint document library; it lands in
  `~/Library/CloudStorage/OneDrive-SharedLibraries-<Org>/...`.

## 5. Find the path and configure

```toml
# .claude/dev-workflow.toml
[onedrive.folders]
du-an = "~/Library/CloudStorage/OneDrive-<Org>/<Folder>"
```

1. `dw onedrive discover` lists sync roots and their first-level folders.
2. Write the chosen path as above.
3. `dw onedrive folders --check` prints the path and `exists`/`missing`.

## 6. Use

- `dw onedrive mkdir du-an:<path>`, `dw onedrive put <file> du-an:<path> --dry-run`, then without `--dry-run`;
  `dw onedrive ls du-an:`, `dw onedrive get du-an:<file> --out <local>`.
- Files On-Demand: a cloud-only file is downloaded when it is read.
- The app uploads written files itself. To be sure a file is up, check its Finder status icon (green check vs
  cloud) or the OneDrive icon in the menu bar.

## 7. Troubleshooting

| Symptom | Cause / action |
|---|---|
| No `~/Library/CloudStorage` | App not installed or not signed in |
| Shared folder missing | No "Add shortcut to My files" yet, or sync not finished |
| Write refused | Only View permission; ask the owner for Edit |
| File name rejected | OneDrive forbids `" * : < > ? \ |`; rename the file |
| Uninstall | Quit OneDrive, drag the app to Trash, or `brew uninstall --cask onedrive` |
