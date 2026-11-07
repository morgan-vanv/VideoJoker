# The VJ's music player — design

**Status:** v1 in progress (`feature/music-player`). Written 2026-10-28 by Morgan + Claude after a late-night planning chat.

## The one-word brief: *elegant*

VideoJoker's music player replaces [eara](https://eara.io) on Morgan's servers. Eara does almost everything,
but its UI and buttons feel clumsy, it has stability wobbles, and pasting a link sometimes needs two tries.
We don't need to out-feature it. We need to be the one that *feels* good: one card with the controls on it,
no spam, no surprises, and a VJ narrating the whole thing.

Guiding ideas:
- **One card, edited in place.** The now-playing card is the player. Pause, loop, shuffle update the card; they
  don't post new messages. When a song ends the card collapses into a one-line "Previously:" so old buttons
  never linger.
- **Links just work.** Paste anything: a YouTube video or playlist, a SoundCloud track or set, a Spotify
  track/album/playlist, or plain words. No autocomplete popup to eat your paste (that's eara's double-paste bug).
- **Say it in the VJ's voice.** Every line lives in `music/lines.py`. "The VJ loads the reel", "Intermission!",
  "The VJ ejects the tape. Movie over, comrades."
- **Controls for the audience.** Anyone in the VJ's voice channel can press the buttons; anyone else gets told
  which room the film is showing in.

## Architecture (decided)

**Pure Python**: yt-dlp + ffmpeg driven by discord.py's own voice support. No Lavalink. We considered it
(it's what eara-class bots use and it makes seek/filters trivial), but it's a Java black box in a second
container and the play loop is exactly the part worth learning.

```
cogs/music.py          slash commands + the "are you in my voice channel" checks   (thin)
music/queue.py         Track + Queue + LoopMode. Pure Python, no Discord, testable
music/sources.py       link/search → Tracks (yt-dlp), Spotify → "Artist - Title" → YouTube
music/player.py        GuildPlayer: voice connection + the loop that plays the queue
music/ui.py            now-playing card, queue embed, the buttons (NowPlayingView)
music/lines.py         the VJ's copy
```

How a `/play` flows:
1. `fetch_tracks()` turns the query into Track objects *fast*: playlists are read "flat" (titles only).
2. Tracks go in the Queue; the loop wakes up.
3. Right before a track plays, `resolve_stream()` asks yt-dlp for the real audio URL (they expire after a few
   hours, so resolving at play time is the only way a long queue stays healthy).
4. ffmpeg decodes the stream, `PCMVolumeTransformer` sets the volume, discord.py encodes Opus and sends it.
5. When the song ends discord.py calls back (from its audio thread; we hop back to the event loop), the loop
   advances by loop mode, and the card is retired and replaced.

Spotify: the Web API never gives audio, so a link becomes `Artist - Title` searches answered by YouTube.
Credentials are a free dev app (`SPOTIFY_CLIENT_ID/SECRET`). Known limit: new dev apps can't read Spotify's
own editorial playlists (they 404); user playlists, albums and tracks are fine.

Accounts that help (all optional env vars, see SETUP_GUIDE): a logged-in YouTube cookie file (Premium account)
dodges the "sign in to confirm you're not a bot" wall; a SoundCloud Go+ OAuth token unlocks HQ streams.

## v1 scope (this PR)

`/play [query] [play_next]`, `/join`, `/leave`, `/pause`, `/resume`, `/skip`, `/stop`, `/queue [page]`,
`/nowplaying`, `/volume`, `/loop`, `/shuffle`, `/remove`. YouTube + SoundCloud + Spotify + text search.
Now-playing card with Pause/Resume, Skip, Stop, Shuffle, Loop, Queue buttons. Idle for 5 minutes → VJ leaves.

## Later phases (each its own PR, in rough order)

1. **Effects** — `/effects` is still a stub. ffmpeg `-af` filters: nightcore (`asetrate`+`atempo`), bass boost
   (`bass=g=`), 8D (`apulsator`), slowed+reverb, vaporwave, plus one gag effect of our own. Changing an effect
   restarts the current track from its position (`-ss`), which also gives us…
2. **Seek** — `/seek`, and ⏪/⏩ 10s buttons on the card.
3. **Move / clear / play-now** — small queue commands eara has.
4. **Leave when alone** — pause when the voice channel empties, leave after a while; `/247` to opt out.
5. **Radio** — `/radio lofi|jazz|…`, a curated list of live streams in `core/constants.py`. Low-hanging fruit:
   live streams already play; this is just a menu.
6. **Autoplay** — when the queue runs out, play YouTube's "related" to the last track.
7. **DJ role** — `is_vip()`-style gate for stop/clear/volume; voteskip for everyone else.
8. **Fun goals (back burner)** — the VJ roasts whoever skips a song, narrates between tracks, "live" trailer
   voiceovers; `/lyrics` → karaoke someday.

## Testing

`music/queue.py` is pure Python and gets unit tests once the pytest foundation lands. Playback needs a real
Discord server: join a voice channel, `/play` a YouTube link, a Spotify playlist, a SoundCloud set, and some
words; press every button; let it sit idle 5 minutes.
