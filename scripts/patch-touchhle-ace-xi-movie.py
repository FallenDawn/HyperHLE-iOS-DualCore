#!/usr/bin/env python3
"""Instrument touchHLE v0.3.0 movie-player call paths and skip unsupported movies."""
from pathlib import Path

core = Path(__file__).resolve().parents[1] / "upstream" / "touchHLE"
path = core / "src/frameworks/media_player/movie_player.rs"
source = path.read_text()

replacements = [
    (
'''    log!(
        "TODO: [(MPMoviePlayerController*){:?} initWithContentURL:{:?} ({:?})]",
        this,
        url,
        ns_url::to_rust_path(env, url),
    );''',
'''    log!(
        "MoviePlayer TRACE: initWithContentURL player={:?} url={:?} path={:?}",
        this,
        url,
        ns_url::to_rust_path(env, url),
    );'''
    ),
    (
'''    State::get(env).pending_notifications.push_back(
        (MPMoviePlayerContentPreloadDidFinishNotification, this, Instant::now())
    );''',
'''    log!(
        "MoviePlayer TRACE: enqueue preload-finished player={:?}",
        this,
    );
    State::get(env).pending_notifications.push_back(
        (MPMoviePlayerContentPreloadDidFinishNotification, this, Instant::now())
    );'''
    ),
    (
'''- (id)view {
    nil // TODO
}

- (MPMoviePlaybackState)playbackState {
    MPMoviePlaybackStateStopped // TODO
}''',
'''- (id)view {
    log!("MoviePlayer TRACE: view player={:?} -> nil", this);
    nil // Video surface is not implemented in this compatibility build.
}

- (MPMoviePlaybackState)playbackState {
    log!(
        "MoviePlayer TRACE: playbackState player={:?} -> Stopped",
        this,
    );
    MPMoviePlaybackStateStopped // Real playback state is not implemented.
}'''
    ),
    (
'''- (())play {
    log!("TODO: [(MPMoviePlayerController*){:?} play]", this);''',
'''- (())play {
    log!("MoviePlayer TRACE: play player={:?}", this);'''
    ),
    (
'''    State::get(env).pending_notifications.push_back(notif);
}''',
'''    log!(
        "MoviePlayer TRACE: enqueue playback-finished player={:?} delay_ms=50",
        this,
    );
    State::get(env).pending_notifications.push_back(notif);
}'''
    ),
    (
'''- (())stop {
    log!("TODO: [(MPMoviePlayerController*){:?} stop]", this);''',
'''- (())stop {
    log!("MoviePlayer TRACE: stop player={:?}", this);'''
    ),
    (
'''    log!(
        "TODO: [(MPMoviePlayerViewController*){:?} initWithContentURL:{:?} ({:?})] -> nil",
        this,
        url,
        ns_url::to_rust_path(env, url),
    );''',
'''    log!(
        "MoviePlayer TRACE: MPMoviePlayerViewController initWithContentURL controller={:?} url={:?} path={:?} -> nil",
        this,
        url,
        ns_url::to_rust_path(env, url),
    );'''
    ),
    (
'''    for (name_str, object) in notifs_to_run {
        let name = ns_string::get_static_str(env, name_str);''',
'''    for (name_str, object) in notifs_to_run {
        log!(
            "MoviePlayer TRACE: dispatch notification name={} object={:?}",
            name_str,
            object,
        );
        let name = ns_string::get_static_str(env, name_str);'''
    ),
]

for old, new in replacements:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one anchor, found {count}: {old[:100]!r}")
    source = source.replace(old, new, 1)

old_finish = '''    // Act as if playback immediately completed after 1 second
    // (various apps wait for this, such as BIA and Hero of Sparta).
    let notif = (MPMoviePlayerPlaybackDidFinishNotification, this, Instant::now().checked_add(Duration::from_millis(1000)).unwrap());'''
new_finish = '''    // Video playback is not implemented by this compatibility build.
    // Complete movie requests quickly while preserving the normal notification path.
    log!("MoviePlayer compatibility: skipping unsupported video playback");
    let notif = (
        MPMoviePlayerPlaybackDidFinishNotification,
        this,
        Instant::now().checked_add(Duration::from_millis(50)).unwrap(),
    );'''
if source.count(old_finish) != 1:
    raise SystemExit("Expected original playback-finish scheduling anchor exactly once")
source = source.replace(old_finish, new_finish, 1)

path.write_text(source)
print("Patched movie-player runtime tracing and 50 ms unsupported-video completion.")
