# Jarvis demo: 60-second voice-over script

The guided demo in the local UI (`preview/demo.js`) walks through the whole tool in exactly
60 seconds. On screen, only the dot shows that Jarvis speaks (it ripples during each line); the
real voice is recorded in ElevenLabs afterwards and laid over the screen recording. The line
timings below are the same as `LINES` in `preview/demo.js`; change both together.

## Recording the video

1. Start the backend and open `http://localhost:3002/?demo=1`. Use a 1440×900 browser window.
2. **Timecode 0:00 = 0.9 s after the page loads** (the tour starts then; the dot starts its
   first line at 0:00.6). Trim the first 0.9 s of the recording, or shift the audio by 0.9 s.
3. Don't touch the mouse or keyboard: any click or key stops the tour. `D` restarts it.

The run is real: the "Online shop checkout" sample through the local converter. The spoken
numbers (4 / 2 / 3, 44%) are that sample's actual result.

## Voice

- **Character:** calm, articulate copilot. Warm, quietly confident, a little dry. Never salesy.
  Mid-low register, clear consonants, a slight smile in the voice.
- **Model:** Eleven v3, so the audio tags below work. With Multilingual v2, drop the tags
  and follow the "Direction" column.
- **Settings (start here):** Stability 45 %, Similarity 75 %, Style 25 %, Speaker boost on,
  Speed 1.0. Raise stability if lines vary too much between takes.
- **Generate each line separately** and place it at its start time. That keeps the sync exact
  even if a take runs a little short. Each line must end before the "Ends by" time.

## Script

| # | Start | Ends by | Slot | On screen | Line (with v3 audio tags) | Direction |
|---|---|---|---|---|---|---|
| 1 | 0:00.6 | 0:04.6 | 4.0 s | Start screen; the dot wakes up | `[warmly] Hi, I'm Jarvis. [short pause] Let's move your Datadog setup to Dash0.` | Friendly opener, relaxed. Small lift on "Dash0". |
| 2 | 0:05.2 | 0:09.6 | 4.4 s | Jarvis picks the "Online shop checkout" sample | `We'll start with this online shop: [short pause] a checkout dashboard and its alert.` | Matter-of-fact, guiding. Light stress on "checkout dashboard". |
| 3 | 0:11.0 | 0:17.8 | 6.8 s | Convert; the dial turns (read → translate → check) | `[confident] Now every query is translated by fixed rules. [short pause] No guessing: the same input always gives the same result.` | The key message. Slower, deliberate. Firm stop after "No guessing". |
| 4 | 0:19.2 | 0:25.0 | 5.8 s | Results board; the outcome summary is marked | `Done. [short pause] Four widgets moved one to one, two need a quick review, and three are blocked.` | Satisfied "Done.", then a clear, even list. No drama on "blocked". |
| 5 | 0:25.6 | 0:31.4 | 5.8 s | The blocked "Checkout error rate" row opens and is highlighted | `This one is blocked: its error metric has no mapping yet. [reassuring] Here's exactly what to add.` | Calm and helpful, like pointing at a screen. Lift on "exactly". |
| 6 | 0:32.2 | 0:38.8 | 6.6 s | In the open blocked item, the "Ask AI" button is marked twice (never clicked) | `[curious] Stuck? [short pause] Ask AI drafts a suggestion for any blocked item. [reassuring] You review it, nothing is applied automatically.` | "Stuck?" light, almost a smile. Middle sentence even and clear. Last part calm and trustworthy, slightly slower. |
| 7 | 0:41.0 | 0:44.6 | 3.6 s | "Your dashboards are ready." headline appears | `[proudly] And that's it. [pause] Your dashboards are ready.` | The payoff. Slow, a little proud, let it breathe. |
| 8 | 0:45.8 | 0:51.8 | 6.0 s | "What moved": donut at 44 % | `Forty-four percent moved one to one. [short pause] Everything else is clearly marked. [short pause] Nothing is hidden.` | Honest, steady. Slight emphasis on "Nothing is hidden". |
| 9 | 0:52.8 | 0:58.8 | 6.0 s | "All set." end view; the dot goes quiet | `Download your files, fix the three flagged items, then publish. [warmly] I'm right here if you need me.` | First half practical, second half warm and softer, trailing off. |

The dot settles into its passive state at 0:59.2; the video ends at 1:00.0.

### Plain text (copy into ElevenLabs line by line)

```
1  Hi, I'm Jarvis. Let's move your Datadog setup to Dash0.
2  We'll start with this online shop: a checkout dashboard and its alert.
3  Now every query is translated by fixed rules. No guessing: the same input always gives the same result.
4  Done. Four widgets moved one to one, two need a quick review, and three are blocked.
5  This one is blocked: its error metric has no mapping yet. Here's exactly what to add.
6  Stuck? Ask AI drafts a suggestion for any blocked item. You review it, nothing is applied automatically.
7  And that's it. Your dashboards are ready.
8  Forty-four percent moved one to one. Everything else is clearly marked. Nothing is hidden.
9  Download your files, fix the three flagged items, then publish. I'm right here if you need me.
```

## Outside the recording

- **Start tour** (header): Jarvis starts from the beginning and speaks every line in the
  ElevenLabs agent's voice (generated once, then cached). If a line runs longer than its slot,
  the rest of the tour waits for him. Click again, press Esc or click anywhere to stop.
- **First visit** (no `?demo=1`): the tour runs once by itself, then Jarvis goes passive.
- **Later visits:** Jarvis greets you ("Welcome back. Tap me whenever you want to talk it
  through.") and goes passive. The browser remembers the first visit (local storage); clear
  site data to see the first-visit tour again.
- **Talking to Jarvis:** click the dot. That starts the real ElevenLabs conversation
  (see `backend/README.md`); the dot follows your voice while listening and the agent's voice
  while speaking. Click again or press Esc to end.
