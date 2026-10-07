# Forge Server Doctor — Free Edition

Your modded Minecraft server won't start. This tells you why.

```bash
python forge_doctor_free.py logs/latest.log
python forge_doctor_free.py crash-reports/crash-2026-10-01_12.34.56-server.txt
```

One file. No dependencies. Python 3.8+. Forge and NeoForge, 1.16–1.21.

Or install it from PyPI and skip the download:

```bash
pip install forge-server-doctor
forge-doctor logs/latest.log
```

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

## Does it detect your error?

The free edition **names the mod jar on every one of these**. It prints the
diagnosis and fix for the six marked *yes*; for the rest it will name the mod
and say it does not recognise the error. Each row links to the full write-up,
which is free to read either way.

| Text in your log | What it means | Diagnosed by free edition |
|---|---|---|
| `for invalid dist DEDICATED_SERVER` | [Client-only code reached the dedicated server](https://jaakoby.github.io/fix/client-class-on-server.html) | names the mod only |
| `net.minecraftforge.fml.ModLoadingException` | [A client-only mod is installed on the server](https://jaakoby.github.io/fix/client-only-mod.html) | names the mod only |
| `Missing or unsupported mandatory dependencies` | [A mod is missing a dependency](https://jaakoby.github.io/fix/missing-dependency.html) | names the mod only |
| `DuplicateModsFoundException` | [The same mod is installed twice](https://jaakoby.github.io/fix/duplicate-mods.html) | yes |
| `org.spongepowered.asm.mixin.` | [A mixin failed to apply](https://jaakoby.github.io/fix/mixin-failure.html) | names the mod only |
| `MinecraftException: Failed to check session lock` | [The world folder is already in use](https://jaakoby.github.io/fix/world-lock.html) | yes |
| `has been compiled by a more recent version of the Java Runtime` | [Wrong Java version](https://jaakoby.github.io/fix/java-version.html) | yes |
| `java.lang.OutOfMemoryError:` | [Out of memory](https://jaakoby.github.io/fix/out-of-memory.html) | yes |
| `Perhaps a server is already running on that port` | [The port is already taken](https://jaakoby.github.io/fix/port-in-use.html) | yes |
| `You need to agree to the EULA` | [EULA not accepted](https://jaakoby.github.io/fix/eula.html) | yes |
| `NoClassDefFoundError: Could not initialize class` | [A class failed during static initialisation](https://jaakoby.github.io/fix/static-init.html) | names the mod only |
| `Forge Mod Loader could not load this save` | [World contains entries for mods that are gone](https://jaakoby.github.io/fix/registry-remap.html) | names the mod only |
| `which is not compatible` | [Mod built for a different loader version](https://jaakoby.github.io/fix/loader-version.html) | names the mod only |
| `Considering it to be crashed, server will forcibly shutdown` | [The server hung and the watchdog killed it](https://jaakoby.github.io/fix/watchdog.html) | names the mod only |
| `java.lang.NoSuchMethodError:` | [Mods compiled against mismatched versions](https://jaakoby.github.io/fix/nosuchmethod.html) | names the mod only |
| `com.electronwill.nightconfig.core.io.ParsingException` | [A config file is invalid](https://jaakoby.github.io/fix/config-crash.html) | names the mod only |
| `Connection closed - mismatched mod channel list` | [Players are being kicked for a mod mismatch](https://jaakoby.github.io/fix/mod-rejections.html) | names the mod only |
| `Parsing error loading recipe` | [A datapack or recipe failed to load](https://jaakoby.github.io/fix/datapack-recipe.html) | names the mod only |
| `ClassNotFoundException:` | [A mod is missing one of its own classes (stale or partial jar)](https://jaakoby.github.io/fix/own-class-missing.html) | names the mod only |
| `ResourceLocationException: Non` | [An invalid resource ID was loaded from config or a datapack](https://jaakoby.github.io/fix/bad-resource-location.html) | names the mod only |
| `Exception ticking` | [A mod crashed while ticking an entity or block](https://jaakoby.github.io/fix/ticking-entity-mod-bug.html) | names the mod only |
| `java.lang.Exception: Mod Loading has failed` | [Mod loading failed — the real cause is further down this report](https://jaakoby.github.io/fix/mod-loading-wrapper.html) | names the mod only |
| `java.lang.IllegalStateException: Failed to initialize server` | [Server failed to initialise — look for the Caused by](https://jaakoby.github.io/fix/server-init-wrapper.html) | names the mod only |
| `is not a valid mod file` | [A jar in mods/ isn't a valid mod](https://jaakoby.github.io/fix/missing-mod-file.html) | names the mod only |


## Asking for help somewhere

```bash
python forge_doctor_free.py --share crash-reports/crash-....txt
```

Prints a short Markdown block to paste into a forum or help thread: your
versions, the mod at fault, the diagnosis and the fix. People posting a
400-line crash report get ignored because nobody reads 400 lines — this is the
four things whoever answers actually needs.

The last line credits the tool. Delete it if you'd rather; it's one line.

## What it doesn't do

**Culprit attribution is in this free edition**, and it runs on every report
— including the ones where no rule matches, which is the most common case.
Forge annotates each stack frame with the jar it came from; this walks the
trace, skips Minecraft, Forge, the JDK and the bundled libraries, and names the
first mod jar left. That is usually the whole answer.

What the free edition does *not* do is diagnose the other 18 failure modes.
It will name the mod, then tell you it does not recognise the error.

The full version adds those 18 — client-only code on a dedicated server, mixin
conflicts, missing dependencies, stale or partial jars, invalid resource IDs,
registry remapping, mod-rejection kicks, watchdog timeouts, and Forge's own
wrapper errors that hide the real cause — each with the specific fix written
out, plus `--json` for start scripts.

Every one of those failure modes is also [written out in full, free to
read](https://jaakoby.github.io/fix/). You are paying for the tool to match
them in your log and hand you the fix, not for access to the knowledge.

<https://kaiven.gumroad.com/l/forge-server-doctor>

## How this was built

Built by Jakoby Tuckta with Claude, against a live 234-mod Forge server. The
code was written with Claude; the crash reports, the production server it was
tested on, and the calls about what shipped are mine. Every commit is tagged
`Co-Authored-By: Claude`.

The first version passed every test we wrote and then diagnosed three of eight
real crash reports — because the same author had written both the samples and
the patterns. It was rebuilt from thirteen genuine crash reports. That rebuild,
not who typed it, is why it works. [The full account of what the real data
corrected](https://jaakoby.github.io/how-this-was-built.html).

## Honest limits

It reads logs, not your mods. A native JVM crash leaves no Java trace to parse —
look for an `hs_err_pid` file instead. It can be wrong. Back up your world before
acting on anything that deletes configs or drops registry entries.

Free to use on any server you own or administer — see `LICENSE.txt`. Not
affiliated with Mojang, Microsoft, MinecraftForge or NeoForged.
