#!/bin/bash
# Display-width table helpers of the statusline plugin, sourced by statusline.sh (not run alone).
# Cells are separated by the ASCII unit separator (0x1f) and may carry ANSI colours: widths are
# counted after dropping the escapes, in characters (jq), so Vietnamese labels ("máy này") pad
# correctly even on bash 3.2, where ${#var} counts bytes outside a UTF-8 locale.
# No row starts with padding: Claude Code trims leading whitespace of status-line lines.

TABLE_US=$'\x1f'
TABLE_GAP="  "
TABLE_SEP=${SEP:-" | "}

join_cells() {
  # Join the arguments with the cell separator; empty cells are kept in place.
  local out="" first=1 cell
  for cell in "$@"; do
    if [ "$first" = "1" ]; then out=$cell; first=0
    else out="${out}${TABLE_US}${cell}"; fi
  done
  printf '%s' "$out"
}

table_width() {
  # Arg: one cell. Prints its visible width in characters.
  jq -Rn --arg s "$1" '$s | gsub("\u001b\\[[0-9;]*m"; "") | length'
}

table_pad() {
  # Args: cell target_width. Appends spaces after the cell (escapes included) up to the width.
  local cell=$1 width=$2 current
  current=$(table_width "$cell")
  if [ "$current" -lt "$width" ]; then
    printf '%s%*s' "$cell" "$((width - current))" ''
  else
    printf '%s' "$cell"
  fi
}

table_print() {
  # Reads one row per line, cells separated by 0x1f. Pads every cell that is followed by another
  # cell to its column width (ANSI excluded); the gap after the label column is plain spaces and
  # later boundaries use TABLE_SEP (" | ").
  local -a rows=() widths=() cells
  local line i last width out
  while IFS= read -r line; do
    rows+=("$line")
  done
  for line in "${rows[@]}"; do
    IFS=$TABLE_US read -r -a cells <<< "$line"
    last=-1
    for i in "${!cells[@]}"; do [ -n "${cells[$i]}" ] && last=$i; done
    for i in "${!cells[@]}"; do
      [ "$i" -lt "$last" ] || continue
      width=$(table_width "${cells[$i]}")
      [ "${widths[$i]:-0}" -lt "$width" ] && widths[$i]=$width
    done
  done
  for line in "${rows[@]}"; do
    IFS=$TABLE_US read -r -a cells <<< "$line"
    last=-1
    for i in "${!cells[@]}"; do [ -n "${cells[$i]}" ] && last=$i; done
    out=""
    for i in "${!cells[@]}"; do
      if [ "$i" -lt "$last" ]; then
        out+="$(table_pad "${cells[$i]}" "${widths[$i]:-0}")"
        if [ "$i" -eq 0 ]; then out+="$TABLE_GAP"; else out+="$TABLE_SEP"; fi
      else
        out+="${cells[$i]}"
      fi
    done
    printf '%s\n' "$out"
  done
}
