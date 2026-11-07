#!/usr/bin/env python3
"""Skip unsupported movie playback for all apps in touchHLE v0.3.0."""
from pathlib import Path

core = Path(__file__).resolve().parents[1] / "upstream" / "touchHLE"
path = core / "src/frameworks/media_player/movie_player.rs"
source = path.read_text()

old = '''    // Act as if playback immediately completed after 1 second
    // (various apps wait for this, such as BIA and Hero of Sparta).
    let notif = (MPMoviePlayerPlaybackDidFinishNotification, this, Instant::now().checked_add(Duration::from_millis(1000)).unwrap());'''
new = '''    // Video playback is not implemented by this compatibility build.
    // Report every movie as finished almost immediately so games do not
    // remain on a black movie surface. This intentionally applies globally;
    // real video decoding can be added later.
    log!("MoviePlayer compatibility: skipping unsupported video playback");
    let notif = (
        MPMoviePlayerPlaybackDidFinishNotification,
        this,
        Instant::now().checked_add(Duration::from_millis(50)).unwrap(),
    );'''

if old not in source:
    raise SystemExit("Expected movie-player source anchor not found; refusing to patch")
path.write_text(source.replace(old, new, 1))
print("Patched all movie playback to finish after 50 ms (video decoding remains unsupported).")