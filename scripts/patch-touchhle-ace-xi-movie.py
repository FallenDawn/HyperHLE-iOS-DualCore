#!/usr/bin/env python3
"""Fast-forward ACE-Xi unsupported intro movie in touchHLE v0.3.0."""
from pathlib import Path

core = Path(__file__).resolve().parents[1] / "upstream" / "touchHLE"
path = core / "src/frameworks/media_player/movie_player.rs"
source = path.read_text()

old = '''    // Act as if playback immediately completed after 1 second
    // (various apps wait for this, such as BIA and Hero of Sparta).
    let notif = (MPMoviePlayerPlaybackDidFinishNotification, this, Instant::now().checked_add(Duration::from_millis(1000)).unwrap());'''
new = '''    // ACE-Xi repeatedly requests an unsupported intro movie. Its GL surface
    // is cleared while the movie player is active, so fast-forward this
    // specific movie instead of leaving the game waiting on a black frame.
    // Keep the upstream one-second behavior for every other application.
    let content_url = env.objc.borrow::<MPMoviePlayerControllerHostObject>(this).content_url;
    let movie_path = ns_url::to_rust_path(env, content_url);
    let is_ace_xi_movie =
        format!("{:?}", movie_path).contains("updata-movie-ACEOP.mp4");
    let playback_delay = if is_ace_xi_movie {
        Duration::from_millis(100)
    } else {
        Duration::from_millis(1000)
    };
    if is_ace_xi_movie {
        log!("ACE-Xi compatibility: fast-forwarding unsupported movie playback");
    }
    let notif = (
        MPMoviePlayerPlaybackDidFinishNotification,
        this,
        Instant::now().checked_add(playback_delay).unwrap(),
    );'''

if old not in source:
    raise SystemExit("Expected movie-player source anchor not found; refusing to patch")
path.write_text(source.replace(old, new, 1))
print("Patched ACE-Xi movie playback delay to 100 ms; other apps remain at 1000 ms.")