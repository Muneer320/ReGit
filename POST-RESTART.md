# GFR — Post-restart re-dispatch checkpoint

STANDING INTENT (from user, 2026-08-22):
> "I'd like a restart and then work again, do it. Since that will give us a much better and stronger base to start with."

## SITUATION
- Gateway (PID 1839) started at 10:32 UTC, so `delegation.model = kimi-k3` (written 17:44) was NEVER bound to the running process.
- Both prior delegations ran on `deepseek-v4-flash` (parent model), not kimi-k3.
- Flash run #1 (deleg_86669a3b) completed: `architecture-decision.md` (30,946 B) — decent draft, but authored on flash.
- Authoritative run (deleg_194da39c, the 37-section brief) was CANCELLED by the restart — it had only scaffolded empty dirs (backend/, frontend/, tests/, docs/, scripts/, shared/, data/).

## MODEL BINDING (verify after restart)
config.yaml `delegation.model` = `kimi-k3` (provider `opencode-go`, base `https://opencode.ai/zen/go/v1`). After restart, RUN THIS to confirm it's live:
```
hermes config | grep -i -A6 delegation
```
The running process must resolve `model: kimi-k3`. If it still shows flash, the restart did not pick up the change.

## RE-DISPATCH ON KIMI-K3 (authoritative brief)
After restart, dispatch ONE delegation with:
- goal: "Execute the STRICT PROTOCOL in /home/foaly/git-for-research/AUTHORITATIVE-BRIEF.md ... produce locked architecture + ownership plan + critical path + starting scaffold, write all artifacts to /home/foaly/git-for-research/."
- context: full self-contained brief path; no chat memory in subagent; verify files with stat before reporting.
- toolsets: terminal, file, web.
- (Exact full prompt is the deleg_194da39c goal — reuse verbatim.)

## SANITY OF PRIOR OUTPUT
- `architecture-decision.md` (flash) is a reasonable crosscheck but must NOT be copied as gospel. kimi-k3 run should supersede/overwrite it after the humans review.

## OWNERSHIP & CUT-OFF REMINDER
- Hardest engineering (version graph, merge, CRDT, provenance) owned by Muneer. AI scaffolds around his decisions.
- Two mandated demo moments (live merge conflict + live semantic diff) must be deterministic/scriptable.
- With restart time spent, recalibrate the 13h clock: document the reset offset when planning.