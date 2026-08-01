# pulse-code (`pulse`) — quick tour for first-time users, updated for v1.1.0
# (dataset-level commands moved under `pulse source <name>`, and new sources
# beyond CDC WONDER — seer, cdc-open, wisqars, grasp, nssp, nis — were added).
# Sticks to offline/no-API-key commands so the recording is deterministic
# and doesn't depend on network access or a CDC WONDER cooldown.

Output pulse-demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1400
Set Height 800
Set Theme "Dracula"
Set TypingSpeed 35ms
Set Padding 20

Hide
Type "cd /home/momotaro/code/self/pulse-code && clear"
Enter
Show

Type `# pulse is a CLI for exploring CDC public health data — WONDER, SEER, PLACES, WISQARS, and more.`
Enter
Sleep 1.5s

Type "uv run pulse --help"
Enter
Sleep 2.5s

Type `# Start with topics — mortality, cancer, vaccination, etc. — spanning all seven sources.`
Enter
Sleep 1s

Type "uv run pulse topics"
Enter
Sleep 2s

Type `# Each source lives under "source". Let's zoom into WONDER's most current dataset.`
Enter
Sleep 1s

Type "uv run pulse source wonder info D176"
Enter
Sleep 2.5s

Type `# Not sure which dataset you need? Search by topic instead.`
Enter
Sleep 1s

Type `uv run pulse search "opioid overdose deaths by state"`
Enter
Sleep 2.5s

Type `# Every WONDER dataset comes with validated, ready-to-run example queries.`
Enter
Sleep 1s

Type "uv run pulse source wonder list-queries --dataset D176"
Enter
Sleep 3s

Type `# From here: "pulse source wonder run <file>" executes any of these against the live CDC API.`
Enter
Sleep 2s
