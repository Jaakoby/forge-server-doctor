# Forge Server Doctor — Free Edition

Your modded Minecraft server won't start. This tells you why.

```bash
python forge_doctor_free.py logs/latest.log
python forge_doctor_free.py crash-reports/crash-2026-10-01_12.34.56-server.txt
```

One file. No dependencies. Python 3.8+. Forge and NeoForge, 1.16–1.21.

## What the free edition checks

The six things that stop a server from starting, each with the actual fix
written out:

- **EULA not accepted**
- **Port already in use** — including voice-chat mods binding their own port,
  which is the same error with a different number
- **Wrong Java version** — with the class-file-version table, so `65.0`
  immediately reads as "this wants Java 21"
- **Out of memory** — realistic heap figures for modded packs, and how to tell
  a too-small heap from a genuine leak
- **World session lock** — including the case where you're boot-testing a
  server someone is still playing on, which looks like a failure but tests
  nothing
- **Duplicate mods** — the old jar you forgot to delete

It also reports your Minecraft version, loader version, Java version, heap size
and whether the server ever reached `Done`.

When nothing matches, it says so and tells you where to look by hand. It does
not invent a diagnosis to look useful.

## What it doesn't do

The free edition handles startup problems. It does **not** diagnose mod
conflicts, and it will not tell you which mod crashed you.

The full version adds 18 more failure modes — client-only code on a dedicated
server, mixin conflicts, missing dependencies, stale or partial jars, invalid
resource IDs, registry remapping, mod-rejection kicks, watchdog timeouts, and
Forge's own wrapper errors that hide the real cause — plus **culprit
attribution**: it walks the stack trace, skips Minecraft, Forge, the JDK and the
bundled libraries, and names the mod jar at fault.

<https://kaiven.gumroad.com/l/forge-server-doctor>

## Honest limits

It reads logs, not your mods. A native JVM crash leaves no Java trace to parse —
look for an `hs_err_pid` file instead. It can be wrong. Back up your world before
acting on anything that deletes configs or drops registry entries.

Free to use and to share. Not affiliated with Mojang, Microsoft, MinecraftForge
or NeoForged.
