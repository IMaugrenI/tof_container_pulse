# Real-life user journey

## Goal

Start Pulse, notice a problem signal quickly, understand where to look, and leave the system unchanged.

## Normal journey

1. Run the platform-specific start command.
2. The container overview opens.
3. Look at **Running**, **Check**, **Needs attention**, and **Unknown**.
4. If **Needs attention** is zero, move through Hardware, Connections, Storage, Services and Security for a quick overview.
5. If a page shows **Check**, read the recommendation and decide whether it needs follow-up.
6. Close the browser when you are done.

**Successful end result:** you understand the current local state without Pulse changing the computer.

## Something needs attention

If the container page shows one item under **Needs attention**:

1. find the matching row
2. read the state and visible measurements
3. use the information to decide what to inspect with your normal system tools
4. do not expect Pulse to restart or repair the container automatically

Pulse is the view, not the control layer.

## Missing information

If a value is **Unknown** or **N/A**, first ask whether that signal is available on the current operating system or whether the underlying tool, such as Docker, is running.

A missing signal should not make the whole suite unusable.

## Stop and return later

A one-time run needs no stop command. Close the browser.

If you used watch mode, stop it with `Ctrl+C`. Run the normal start command again whenever you want a fresh view.
